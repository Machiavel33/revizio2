//! Pipeline audio : capture micro (cpal), downmix mono, resampling 16 kHz,
//! détection d'activité vocale (VAD énergie) et calcul du niveau pour la waveform.
//!
//! Le flux produit des frames PCM f32 mono 16 kHz prêtes à être encodées
//! (WAV pour l'upload batch, ou chunks pour le streaming).

use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use parking_lot::Mutex;
use rubato::{
    Resampler, SincFixedIn, SincInterpolationParameters, SincInterpolationType, WindowFunction,
};
use thiserror::Error;

pub const TARGET_SAMPLE_RATE: u32 = 16_000;

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

/// Buffer partagé qui accumule les frames mono 16 kHz.
#[derive(Default)]
pub struct AudioBuffer {
    pub samples: Mutex<Vec<f32>>,
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
    pub source_rate: u32,
}

// cpal::Stream n'est pas Send sur toutes les plateformes ; on encapsule
// l'usage dans le thread Tauri principal via Mutex côté commandes.
unsafe impl Send for RecordingHandle {}

impl RecordingHandle {
    pub fn stop(&self) {
        self.stop_flag.store(true, Ordering::SeqCst);
        let _ = self.stream.pause();
    }
}

/// Démarre la capture depuis un périphérique (nom optionnel = défaut).
pub fn start_recording(device_name: Option<String>) -> Result<RecordingHandle, AudioError> {
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
    let stop_flag = Arc::new(AtomicBool::new(false));

    // Resampler vers 16 kHz mono
    let resampler = build_resampler(source_rate, TARGET_SAMPLE_RATE)?;
    let resampler = Arc::new(Mutex::new(resampler));

    let buf_clone = buffer.clone();
    let meter_clone = meter.clone();
    let stop_clone = stop_flag.clone();

    let err_fn = |err| log::error!("erreur stream audio: {err}");

    let stream = match config.sample_format() {
        cpal::SampleFormat::F32 => device.build_input_stream(
            &config.into(),
            move |data: &[f32], _| {
                if stop_clone.load(Ordering::SeqCst) {
                    return;
                }
                process_input(data, channels, &buf_clone, &meter_clone, &resampler);
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
                process_input(&f, channels, &buf_clone, &meter_clone, &resampler);
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

/// Downmix multi-canal -> mono, met à jour le niveau, resample vers 16 kHz.
fn process_input(
    data: &[f32],
    channels: usize,
    buffer: &Arc<AudioBuffer>,
    meter: &Arc<LevelMeter>,
    resampler: &Arc<Mutex<SincFixedIn<f32>>>,
) {
    if data.is_empty() || channels == 0 {
        return;
    }
    // Downmix
    let frames = data.len() / channels;
    let mut mono = Vec::with_capacity(frames);
    for i in 0..frames {
        let mut sum = 0.0f32;
        for c in 0..channels {
            sum += data[i * channels + c];
        }
        mono.push(sum / channels as f32);
    }

    // Niveau RMS pour la waveform
    let rms = (mono.iter().map(|s| s * s).sum::<f32>() / mono.len() as f32).sqrt();
    meter.set(rms.min(1.0));

    // Resampling vers 16 kHz
    let mut rs = resampler.lock();
    if let Ok(out) = rs.process(&[mono], None) {
        if let Some(channel) = out.first() {
            buffer.push(channel);
        }
    }
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
