//! Commandes Tauri exposées au front React.

use parking_lot::Mutex;
use tauri::State;

use crate::audio::{
    self, encode_pcm16, encode_wav, InputDevice, RecordingHandle, TARGET_SAMPLE_RATE,
};

/// État global de l'application (session d'enregistrement courante).
#[derive(Default)]
pub struct AppState {
    pub recording: Mutex<Option<RecordingHandle>>,
}

#[derive(serde::Serialize)]
pub struct StartResult {
    pub source_rate: u32,
    pub target_rate: u32,
}

#[derive(serde::Serialize)]
pub struct CalibrationResult {
    pub ambient_rms: f32,
    pub suggested_threshold: f32,
}

#[tauri::command]
pub fn list_input_devices() -> Result<Vec<InputDevice>, String> {
    audio::list_input_devices().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn start_recording(
    device_name: Option<String>,
    vad_threshold: Option<f32>,
    state: State<'_, AppState>,
) -> Result<StartResult, String> {
    let mut guard = state.recording.lock();
    if guard.is_some() {
        return Err("un enregistrement est déjà en cours".into());
    }
    // Seuil par défaut : 0.012 (RMS) — assez bas pour capter une voix, assez
    // haut pour ignorer le bruit de fond diffus d'une salle.
    let threshold = vad_threshold.unwrap_or(0.012);
    let handle = audio::start_recording(device_name, threshold).map_err(|e| e.to_string())?;
    let result = StartResult {
        source_rate: handle.source_rate,
        target_rate: TARGET_SAMPLE_RATE,
    };
    *guard = Some(handle);
    Ok(result)
}

/// Retourne le niveau audio courant (0..=1) pour la waveform.
#[tauri::command]
pub fn get_level(state: State<'_, AppState>) -> f32 {
    let guard = state.recording.lock();
    guard.as_ref().map(|h| h.meter.get()).unwrap_or(0.0)
}

/// Ajuste le seuil VAD à chaud pendant l'enregistrement.
#[tauri::command]
pub fn set_vad_threshold(threshold: f32, state: State<'_, AppState>) {
    let guard = state.recording.lock();
    if let Some(h) = guard.as_ref() {
        h.vad.set(threshold.clamp(0.0, 1.0));
    }
}

/// Récupère les chunks de streaming accumulés (PCM16 base64) depuis le dernier appel.
/// Le front les envoie au backend via WebSocket pour la transcription live.
#[tauri::command]
pub fn drain_stream_chunks(state: State<'_, AppState>) -> Vec<String> {
    let guard = state.recording.lock();
    match guard.as_ref() {
        Some(h) => h
            .stream_queue
            .drain()
            .into_iter()
            .map(|chunk| {
                use base64::Engine;
                base64::engine::general_purpose::STANDARD.encode(encode_pcm16(&chunk))
            })
            .collect(),
        None => Vec::new(),
    }
}

/// Arrête l'enregistrement et retourne le WAV encodé.
#[tauri::command]
pub fn stop_recording(state: State<'_, AppState>) -> Result<Vec<u8>, String> {
    let mut guard = state.recording.lock();
    let handle = guard.take().ok_or("aucun enregistrement en cours")?;
    handle.stop();
    let samples = handle.buffer.take();
    encode_wav(&samples, TARGET_SAMPLE_RATE).map_err(|e| e.to_string())
}

/// Durée approximative de l'enregistrement courant en secondes.
#[tauri::command]
pub fn recording_duration(state: State<'_, AppState>) -> f64 {
    let guard = state.recording.lock();
    match guard.as_ref() {
        Some(h) => h.buffer.len() as f64 / TARGET_SAMPLE_RATE as f64,
        None => 0.0,
    }
}

/// Indique si un enregistrement est en cours.
#[tauri::command]
pub fn is_recording(state: State<'_, AppState>) -> bool {
    state.recording.lock().is_some()
}

/// Calibre le micro : mesure le bruit ambiant pendant `duration_ms` et suggère
/// un seuil VAD (bruit ambiant + marge). Bloque le thread appelant.
#[tauri::command]
pub fn calibrate_microphone(
    device_name: Option<String>,
    duration_ms: Option<u64>,
) -> Result<CalibrationResult, String> {
    let duration = duration_ms.unwrap_or(2000);
    let handle = audio::start_recording(device_name, 0.0).map_err(|e| e.to_string())?;
    std::thread::sleep(std::time::Duration::from_millis(duration));

    // Échantillonne le niveau pendant la fenêtre
    let mut samples = Vec::new();
    let steps = 20;
    for _ in 0..steps {
        std::thread::sleep(std::time::Duration::from_millis(duration / steps));
        samples.push(handle.meter.get());
    }
    handle.stop();

    let ambient = if samples.is_empty() {
        0.0
    } else {
        samples.iter().sum::<f32>() / samples.len() as f32
    };
    // Seuil = bruit ambiant + marge (min 0.008, max 0.2)
    let suggested = (ambient * 2.5).clamp(0.008, 0.2);

    Ok(CalibrationResult {
        ambient_rms: ambient,
        suggested_threshold: suggested,
    })
}
