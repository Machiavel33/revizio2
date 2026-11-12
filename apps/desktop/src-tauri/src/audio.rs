//! Pipeline audio : capture micro (cpal), downmix mono, resampling 16 kHz,
//! dé-bruitage RNNoise, détection d'activité vocale (VAD énergie adaptatif),
//! et émission de chunks pour la transcription live.
//!
//! Chaîne : Micro → cpal (PCM) → downmix mono → resample 16 kHz
//!          → RNNoise (dé-bruitage) → VAD (gate silence) → buffer + chunks.

use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use nnnoiseless::DenoiseState;
use parking_lot::Mutex;
use rubato::{
    Resampler, SincFixedIn, SincInterpolationParameters, SincInterpolationType, WindowFunction,
};
use thiserror::Error;

pub const TARGET_SAMPLE_RATE: u32 = 16_000;
/// Taille d'un chunk de streaming (en échantillons à 16 kHz) ≈ 100 ms.
pub const STREAM_CHUNK_SAMPLES: usize = 1_600;
/// Taille de frame RNNoise (fixe, 10 ms à 48 kHz = 480 échantillons).
const RNNOISE_FRAME: usize = 480;

#[derive(Debug, Error)]
pub enum AudioError {
    #[error("aucun périphérique d'entrée disponible")]
    NoInputDevice,
    #[error("erreur cpal: {0}")]
    Cpal(String),
    #[error("format audio non supporté: {0}")]
    UnsupportedFormat(String),
    #[error("erreur de resampling: {0}")]
    Resample(String),
}

/// Description d'un périphérique d'entrée exposée au front.
#[derive(Debug, Clone, serde::Serialize)]
pub struct InputDevice {
    pub name: String,
    pub is_default: bool,
}

/// État partagé du niveau audio (0..=1) pour la waveform temps réel.
#[derive(Default)]
pub struct LevelMeter {
    pub level: AtomicU32, // f32 bits stockés en u32
}

impl LevelMeter {
    pub fn set(&self, value: f32) {
        self.level.store(value.to_bits(), Ordering::Relaxed);
    }
    pub fn get(&self) -> f32 {
        f32::from_bits(self.level.load(Ordering::Relaxed))
    }
}

/// Seuil VAD partagé (RMS en dessous duquel on considère du silence).
#[derive(Default)]
pub struct VadConfig {
    pub threshold: AtomicU32, // f32 bits
}

impl VadConfig {
    pub fn set(&self, value: f32) {
        self.threshold.store(value.to_bits(), Ordering::Relaxed);
    }
    pub fn get(&self) -> f32 {
        f32::from_bits(self.threshold.load(Ordering::Relaxed))
    }
}

/// Buffer partagé qui accumule les frames mono 16 kHz (post-VAD).
#[derive(Default)]
pub struct AudioBuffer {
    pub samples: Mutex<Vec<f32>>,
    /// Curseur de consommation pour le transport résilient (non destructif).
    pub resilient_cursor: Mutex<usize>,
}

impl AudioBuffer {
    pub fn push(&self, frame: &[f32]) {
        self.samples.lock().extend_from_slice(frame);
    }
    pub fn take(&self) -> Vec<f32> {
        std::mem::take(&mut *self.samples.lock())
    }
    pub fn len(&self) -> usize {
        self.samples.lock().len()
    }
    /// Retourne les échantillons accumulés depuis le dernier drain résilient,
    /// sans les retirer (le WAV final les conserve).
    pub fn drain_resilient(&self) -> Vec<f32> {
        let samples = self.samples.lock();
        let mut cursor = self.resilient_cursor.lock();
        let start = (*cursor).min(samples.len());
        let out = samples[start..].to_vec();
        *cursor = samples.len();
        out
    }
}

/// File de chunks de streaming (post-VAD) consommée par le front via events.
#[derive(Default)]
pub struct StreamQueue {
    pub chunks: Mutex<Vec<Vec<f32>>>,
}

impl StreamQueue {
    pub fn push(&self, chunk: Vec<f32>) {
        self.chunks.lock().push(chunk);
    }
    pub fn drain(&self) -> Vec<Vec<f32>> {
        std::mem::take(&mut *self.chunks.lock())
    }
}

/// Liste les périphériques d'entrée disponibles.
pub fn list_input_devices() -> Result<Vec<InputDevice>, AudioError> {
    let host = cpal::default_host();
    let default_name = host
        .default_input_device()
        .and_then(|d| d.name().ok())
        .unwrap_or_default();

    let mut devices = Vec::new();
    let inputs = host
        .input_devices()
        .map_err(|e| AudioError::Cpal(e.to_string()))?;
    for dev in inputs {
        if let Ok(name) = dev.name() {
            devices.push(InputDevice {
                is_default: name == default_name,
                name,
            });
        }
    }
    if devices.is_empty() {
        return Err(AudioError::NoInputDevice);
    }
    Ok(devices)
}

/// Handle d'une session d'enregistrement active.
pub struct RecordingHandle {
    stop_flag: Arc<AtomicBool>,
    stream: cpal::Stream,
    pub buffer: Arc<AudioBuffer>,
    pub meter: Arc<LevelMeter>,
    pub vad: Arc<VadConfig>,
    pub stream_queue: Arc<StreamQueue>,
    pub source_rate: u32,
}

unsafe impl Send for RecordingHandle {}

impl RecordingHandle {
    pub fn stop(&self) {
        self.stop_flag.store(true, Ordering::SeqCst);
        let _ = self.stream.pause();
    }
}

/// État de traitement partagé entre le callback audio et les helpers.
struct Processor {
    buffer: Arc<AudioBuffer>,
    meter: Arc<LevelMeter>,
    vad: Arc<VadConfig>,
    stream_queue: Arc<StreamQueue>,
    resampler: Arc<Mutex<SincFixedIn<f32>>>,
    denoiser: Arc<Mutex<Box<DenoiseState<'static>>>>,
    /// Accumulateur pour former des frames RNNoise de 480 échantillons.
    rnnoise_acc: Vec<f32>,
    /// Accumulateur pour former des chunks de streaming de 1600 échantillons.
    stream_acc: Vec<f32>,
}

impl Processor {
    fn process(&mut self, data: &[f32], channels: usize) {
        if data.is_empty() || channels == 0 {
            return;
        }
        // 1. Downmix mono
        let frames = data.len() / channels;
        let mut mono = Vec::with_capacity(frames);
        for i in 0..frames {
            let mut sum = 0.0f32;
            for c in 0..channels {
                sum += data[i * channels + c];
            }
            mono.push(sum / channels as f32);
        }

        // 2. Resampling vers 16 kHz
        let resampled = {
            let mut rs = self.resampler.lock();
            match rs.process(&[mono], None) {
                Ok(out) => out.into_iter().next().unwrap_or_default(),
                Err(_) => return,
            }
        };
        if resampled.is_empty() {
            return;
        }

        // 3. RNNoise : traite par frames de 480 échantillons
        self.rnnoise_acc.extend_from_slice(&resampled);
        let mut denoised = Vec::with_capacity(resampled.len());
        while self.rnnoise_acc.len() >= RNNOISE_FRAME {
            let frame: Vec<f32> = self.rnnoise_acc.drain(..RNNOISE_FRAME).collect();
            let mut out = vec![0.0f32; RNNOISE_FRAME];
            {
                let mut d = self.denoiser.lock();
                d.process_frame(&mut out, &frame);
            }
            denoised.extend_from_slice(&out);
        }
        if denoised.is_empty() {
            return;
        }

        // 4. Niveau RMS (post-denoise) pour la waveform
        let rms = (denoised.iter().map(|s| s * s).sum::<f32>() / denoised.len() as f32).sqrt();
        self.meter.set(rms.min(1.0));

        // 5. VAD : gate silence sous le seuil
        let threshold = self.vad.get();
        if rms < threshold {
            return;
        }

        // 6. Buffer complet (pour l'upload batch)
        self.buffer.push(&denoised);

        // 7. Chunks de streaming (100 ms)
        self.stream_acc.extend_from_slice(&denoised);
        while self.stream_acc.len() >= STREAM_CHUNK_SAMPLES {
            let chunk: Vec<f32> = self.stream_acc.drain(..STREAM_CHUNK_SAMPLES).collect();
            self.stream_queue.push(chunk);
        }
    }
}

/// Démarre la capture depuis un périphérique (nom optionnel = défaut).
pub fn start_recording(
    device_name: Option<String>,
    vad_threshold: f32,
) -> Result<RecordingHandle, AudioError> {
    let host = cpal::default_host();
    let device = match device_name {
        Some(name) => host
            .input_devices()
            .map_err(|e| AudioError::Cpal(e.to_string()))?
            .find(|d| d.name().map(|n| n == name).unwrap_or(false))
            .ok_or(AudioError::NoInputDevice)?,
        None => host
            .default_input_device()
            .ok_or(AudioError::NoInputDevice)?,
    };

    let config = device
        .default_input_config()
        .map_err(|e| AudioError::Cpal(e.to_string()))?;
    let source_rate = config.sample_rate().0;
    let channels = config.channels() as usize;

    let buffer = Arc::new(AudioBuffer::default());
    let meter = Arc::new(LevelMeter::default());
    let vad = Arc::new(VadConfig::default());
    vad.set(vad_threshold);
    let stream_queue = Arc::new(StreamQueue::default());
    let stop_flag = Arc::new(AtomicBool::new(false));

    let resampler = Arc::new(Mutex::new(build_resampler(source_rate, TARGET_SAMPLE_RATE)?));
    let denoiser = Arc::new(Mutex::new(DenoiseState::new()));

    let processor = Arc::new(Mutex::new(Processor {
        buffer: buffer.clone(),
        meter: meter.clone(),
        vad: vad.clone(),
        stream_queue: stream_queue.clone(),
        resampler,
        denoiser,
        rnnoise_acc: Vec::new(),
        stream_acc: Vec::new(),
    }));

    let stop_clone = stop_flag.clone();
    let proc_clone = processor.clone();
    let err_fn = |err| log::error!("erreur stream audio: {err}");

    let stream = match config.sample_format() {
        cpal::SampleFormat::F32 => device.build_input_stream(
            &config.into(),
            move |data: &[f32], _| {
                if stop_clone.load(Ordering::SeqCst) {
                    return;
                }
                proc_clone.lock().process(data, channels);
            },
            err_fn,
            None,
        ),
        cpal::SampleFormat::I16 => device.build_input_stream(
            &config.into(),
            move |data: &[i16], _| {
                if stop_clone.load(Ordering::SeqCst) {
                    return;
                }
                let f: Vec<f32> = data.iter().map(|&s| s as f32 / i16::MAX as f32).collect();
                proc_clone.lock().process(&f, channels);
            },
            err_fn,
            None,
        ),
        other => return Err(AudioError::UnsupportedFormat(format!("{other:?}"))),
    }
    .map_err(|e| AudioError::Cpal(e.to_string()))?;

    stream
        .play()
        .map_err(|e| AudioError::Cpal(e.to_string()))?;

    Ok(RecordingHandle {
        stop_flag,
        stream,
        buffer,
        meter,
        vad,
        stream_queue,
        source_rate,
    })
}

fn build_resampler(from: u32, to: u32) -> Result<SincFixedIn<f32>, AudioError> {
    let params = SincInterpolationParameters {
        sinc_len: 128,
        f_cutoff: 0.95,
        interpolation: SincInterpolationType::Linear,
        oversampling_factor: 128,
        window: WindowFunction::BlackmanHarris2,
    };
    let ratio = to as f64 / from as f64;
    SincFixedIn::<f32>::new(ratio, 2.0, params, 1024, 1)
        .map_err(|e| AudioError::Resample(e.to_string()))
}

/// Encode un buffer PCM f32 mono 16 kHz en WAV (16-bit) pour l'upload batch.
pub fn encode_wav(samples: &[f32], sample_rate: u32) -> Result<Vec<u8>, AudioError> {
    let mut cursor = std::io::Cursor::new(Vec::new());
    {
        let spec = hound::WavSpec {
            channels: 1,
            sample_rate,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let mut writer =
            hound::WavWriter::new(&mut cursor, spec).map_err(|e| AudioError::Cpal(e.to_string()))?;
        for &s in samples {
            let v = (s.clamp(-1.0, 1.0) * i16::MAX as f32) as i16;
            writer
                .write_sample(v)
                .map_err(|e| AudioError::Cpal(e.to_string()))?;
        }
        writer
            .finalize()
            .map_err(|e| AudioError::Cpal(e.to_string()))?;
    }
    Ok(cursor.into_inner())
}

/// Encode un chunk PCM f32 en PCM 16-bit little-endian (pour le streaming WS).
pub fn encode_pcm16(samples: &[f32]) -> Vec<u8> {
    let mut out = Vec::with_capacity(samples.len() * 2);
    for &s in samples {
        let v = (s.clamp(-1.0, 1.0) * i16::MAX as f32) as i16;
        out.extend_from_slice(&v.to_le_bytes());
    }
    out
}
