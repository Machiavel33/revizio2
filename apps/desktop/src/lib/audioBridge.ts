/** Pont vers les commandes Rust (Tauri). */

import { invoke } from "@tauri-apps/api/core";
import type { InputDevice } from "./types";

export interface StartResult {
  source_rate: number;
  target_rate: number;
}

export interface CalibrationResult {
  ambient_rms: number;
  suggested_threshold: number;
}

export const audioBridge = {
  listDevices: () => invoke<InputDevice[]>("list_input_devices"),
  start: (deviceName?: string, vadThreshold?: number) =>
    invoke<StartResult>("start_recording", {
      deviceName: deviceName ?? null,
      vadThreshold: vadThreshold ?? null,
    }),
  stop: () => invoke<number[]>("stop_recording"),
  getLevel: () => invoke<number>("get_level"),
  setVadThreshold: (threshold: number) =>
    invoke<void>("set_vad_threshold", { threshold }),
  drainStreamChunks: () => invoke<string[]>("drain_stream_chunks"),
  duration: () => invoke<number>("recording_duration"),
  isRecording: () => invoke<boolean>("is_recording"),
  calibrate: (deviceName?: string, durationMs?: number) =>
    invoke<CalibrationResult>("calibrate_microphone", {
      deviceName: deviceName ?? null,
      durationMs: durationMs ?? null,
    }),
};

/** Convertit le tableau d'octets renvoyé par Rust en Blob WAV. */
export function bytesToWavBlob(bytes: number[]): Blob {
  return new Blob([new Uint8Array(bytes)], { type: "audio/wav" });
}

/** Décode un chunk base64 PCM16 en ArrayBuffer. */
export function base64ToPcm16(b64: string): ArrayBuffer {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}
