//! Commandes Tauri exposées au front React.

use parking_lot::Mutex;
use tauri::State;

use crate::audio::{self, encode_wav, InputDevice, RecordingHandle, TARGET_SAMPLE_RATE};

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

#[tauri::command]
pub fn list_input_devices() -> Result<Vec<InputDevice>, String> {
    audio::list_input_devices().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn start_recording(
    device_name: Option<String>,
    state: State<'_, AppState>,
) -> Result<StartResult, String> {
    let mut guard = state.recording.lock();
    if guard.is_some() {
        return Err("un enregistrement est déjà en cours".into());
    }
    let handle = audio::start_recording(device_name).map_err(|e| e.to_string())?;
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

/// Arrête l'enregistrement et retourne le WAV encodé (base64 non nécessaire :
/// on renvoie les octets bruts via Vec<u8>, sérialisé en tableau JSON).
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
