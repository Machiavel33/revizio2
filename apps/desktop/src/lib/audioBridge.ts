/** Pont vers les commandes Rust (Tauri). */

import { invoke } from "@tauri-apps/api/core";
import type { InputDevice } from "./types";

export interface StartResult {
  source_rate: number;
  target_rate: number;
}

export const audioBridge = {
  listDevices: () => invoke<InputDevice[]>("list_input_devices"),
  start: (deviceName?: string) =>
    invoke<StartResult>("start_recording", { deviceName: deviceName ?? null }),
  stop: () => invoke<number[]>("stop_recording"),
  getLevel: () => invoke<number>("get_level"),
  duration: () => invoke<number>("recording_duration"),
  isRecording: () => invoke<boolean>("is_recording"),
};

/** Convertit le tableau d'octets renvoyé par Rust en Blob WAV. */
export function bytesToWavBlob(bytes: number[]): Blob {
  return new Blob([new Uint8Array(bytes)], { type: "audio/wav" });
}
