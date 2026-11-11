//! Revizio desktop — point d'entrée bibliothèque Tauri.

mod audio;
mod commands;

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
            commands::recording_duration,
            commands::is_recording,
        ])
        .run(tauri::generate_context!())
        .expect("erreur au lancement de Revizio");
}
