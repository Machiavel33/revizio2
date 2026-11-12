//! Revizio desktop — point d'entrée bibliothèque Tauri.

mod audio;
mod chunker;
mod commands;
mod protocol;

use commands::AppState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            commands::list_input_devices,
            commands::start_recording,
            commands::stop_recording,
            commands::get_level,
            commands::set_vad_threshold,
            commands::drain_stream_chunks,
            commands::recording_duration,
            commands::is_recording,
            commands::calibrate_microphone,
            commands::start_resilient_session,
            commands::drain_resilient_samples,
            commands::push_resilient_samples,
            commands::finish_resilient_session,
            commands::ack_resilient_chunk,
            commands::pending_resilient_chunks,
            commands::load_resilient_chunk,
            commands::close_resilient_session,
            commands::cleanup_orphan_spools,
        ])
        .run(tauri::generate_context!())
        .expect("erreur au lancement de Revizio");
}
