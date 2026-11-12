//! Commandes Tauri exposées au front React.

use parking_lot::Mutex;
use tauri::State;
use uuid::Uuid;

use crate::audio::{
    self, encode_pcm16, encode_wav, InputDevice, RecordingHandle, TARGET_SAMPLE_RATE,
};
use crate::chunker::{Chunker, ChunkOut, Spool};

/// Session de transport résilient (chunker + spool).
pub struct ResilientSession {
    #[allow(dead_code)]
    pub session_id: Uuid,
    pub chunker: Chunker,
    pub spool: Spool,
}

/// État global de l'application (session d'enregistrement courante).
#[derive(Default)]
pub struct AppState {
    pub recording: Mutex<Option<RecordingHandle>>,
    pub resilient: Mutex<Option<ResilientSession>>,
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

// --- Transport résilient (protocole rvzf-v1) ---

#[derive(serde::Serialize)]
pub struct ResilientChunk {
    pub chunk_seq: u64,
    pub frames_b64: Vec<String>,
    pub chunk_end: String,
    pub sha256: String,
}

fn chunk_to_wire(c: &ChunkOut) -> ResilientChunk {
    use base64::Engine;
    ResilientChunk {
        chunk_seq: c.chunk_seq,
        frames_b64: c
            .frames
            .iter()
            .map(|f| base64::engine::general_purpose::STANDARD.encode(f))
            .collect(),
        chunk_end: c.chunk_end.clone(),
        sha256: c.sha256.clone(),
    }
}

/// Démarre une session de transport résilient (nouveau session_id + spool).
#[tauri::command]
pub fn start_resilient_session(
    spool_root: String,
    state: State<'_, AppState>,
) -> Result<String, String> {
    let mut guard = state.resilient.lock();
    if guard.is_some() {
        return Err("session résiliente déjà active".into());
    }
    let session_id = Uuid::new_v4();
    let spool = Spool::new(std::path::Path::new(&spool_root), session_id)
        .map_err(|e| e.to_string())?;
    *guard = Some(ResilientSession {
        session_id,
        chunker: Chunker::new(session_id),
        spool,
    });
    Ok(session_id.to_string())
}

/// Pousse des échantillons f32 (base64) dans le chunker, retourne les fragments prêts
/// (stockés dans le spool avant retour). Le front les envoie puis appelle ack.
#[tauri::command]
pub fn push_resilient_samples(
    samples_b64: String,
    state: State<'_, AppState>,
) -> Result<Vec<ResilientChunk>, String> {
    use base64::Engine;
    let mut guard = state.resilient.lock();
    let session = guard.as_mut().ok_or("aucune session résiliente")?;
    let raw = base64::engine::general_purpose::STANDARD
        .decode(samples_b64)
        .map_err(|e| e.to_string())?;
    // raw = f32 little-endian
    if raw.len() % 4 != 0 {
        return Err("samples f32 invalides".into());
    }
    let samples: Vec<f32> = raw
        .chunks_exact(4)
        .map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]]))
        .collect();
    let chunks = session.chunker.push(&samples);
    let mut out = Vec::with_capacity(chunks.len());
    for c in &chunks {
        session.spool.store(c).map_err(|e| e.to_string())?;
        out.push(chunk_to_wire(c));
    }
    Ok(out)
}

/// Termine la session : vide le dernier fragment partiel et le retourne.
#[tauri::command]
pub fn finish_resilient_session(state: State<'_, AppState>) -> Result<Option<ResilientChunk>, String> {
    let mut guard = state.resilient.lock();
    let session = guard.as_mut().ok_or("aucune session résiliente")?;
    match session.chunker.finish() {
        Some(c) => {
            session.spool.store(&c).map_err(|e| e.to_string())?;
            Ok(Some(chunk_to_wire(&c)))
        }
        None => Ok(None),
    }
}

/// Acquitte un fragment (efface du spool après ACK serveur).
#[tauri::command]
pub fn ack_resilient_chunk(chunk_seq: u64, state: State<'_, AppState>) -> Result<(), String> {
    let guard = state.resilient.lock();
    let session = guard.as_ref().ok_or("aucune session résiliente")?;
    session.spool.ack(chunk_seq).map_err(|e| e.to_string())
}

/// Liste les fragments non acquittés (à réémettre après reconnexion).
#[tauri::command]
pub fn pending_resilient_chunks(state: State<'_, AppState>) -> Result<Vec<u64>, String> {
    let guard = state.resilient.lock();
    let session = guard.as_ref().ok_or("aucune session résiliente")?;
    Ok(session.spool.pending())
}

/// Relit un fragment du spool pour réémission.
#[tauri::command]
pub fn load_resilient_chunk(
    chunk_seq: u64,
    state: State<'_, AppState>,
) -> Result<Option<ResilientChunk>, String> {
    let guard = state.resilient.lock();
    let session = guard.as_ref().ok_or("aucune session résiliente")?;
    let c = session.spool.load(chunk_seq).map_err(|e| e.to_string())?;
    Ok(c.as_ref().map(chunk_to_wire))
}

/// Ferme et nettoie la session résiliente.
#[tauri::command]
pub fn close_resilient_session(state: State<'_, AppState>) -> Result<(), String> {
    let mut guard = state.resilient.lock();
    if let Some(session) = guard.take() {
        session.spool.clear();
    }
    Ok(())
}

/// Récupère les échantillons f32 accumulés depuis le dernier appel (base64),
/// pour les pousser dans le chunker résilient. Non destructif (le WAV les garde).
#[tauri::command]
pub fn drain_resilient_samples(state: State<'_, AppState>) -> Result<String, String> {
    use base64::Engine;
    let guard = state.recording.lock();
    let handle = guard.as_ref().ok_or("aucun enregistrement en cours")?;
    let samples = handle.buffer.drain_resilient();
    let mut bytes = Vec::with_capacity(samples.len() * 4);
    for s in &samples {
        bytes.extend_from_slice(&s.to_le_bytes());
    }
    Ok(base64::engine::general_purpose::STANDARD.encode(&bytes))
}

/// Nettoie les spools orphelins (sessions crashées) de plus de 24h.
#[tauri::command]
pub fn cleanup_orphan_spools(spool_root: String) -> Result<u32, String> {
    let root = std::path::Path::new(&spool_root);
    if !root.exists() {
        return Ok(0);
    }
    let now = std::time::SystemTime::now();
    let mut removed = 0u32;
    if let Ok(entries) = std::fs::read_dir(root) {
        for e in entries.flatten() {
            let path = e.path();
            if !path.is_dir() {
                continue;
            }
            let old = e
                .metadata()
                .and_then(|m| m.modified())
                .ok()
                .and_then(|t| now.duration_since(t).ok())
                .map(|d| d.as_secs() > 24 * 3600)
                .unwrap_or(false);
            if old && std::fs::remove_dir_all(&path).is_ok() {
                removed += 1;
            }
        }
    }
    Ok(removed)
}
