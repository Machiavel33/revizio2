/** Hook de transcription streaming temps réel (sherpa-onnx via le service STT).
 *
 * Envoie des trames PCM16 mono 16 kHz (4000 échantillons = 250 ms) au backend
 * (`/api/ws/stream`), qui relaie au service STT sherpa-onnx. Reçoit des
 * partial/final sub-seconde. Les chunks audio du pipeline Rust (1600 échantillons
 * = 100 ms) sont réassemblés en trames de 4000 avant envoi.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, tokenStore } from "../lib/api";
import { audioBridge, base64ToPcm16 } from "../lib/audioBridge";

type Status = "idle" | "connecting" | "live" | "error";

interface StreamingTranscription {
  status: Status;
  finalText: string;
  partialText: string;
  error: string | null;
  start: (courseId: string, language?: string) => Promise<void>;
  stop: () => void;
}

const FRAME_SAMPLES = 4000; // 250 ms à 16 kHz (protocole STT)
const FRAME_BYTES = FRAME_SAMPLES * 2;

export function useStreamingTranscription(): StreamingTranscription {
  const [status, setStatus] = useState<Status>("idle");
  const [finalText, setFinalText] = useState("");
  const [partialText, setPartialText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pumpRef = useRef<number | null>(null);
  const pendingRef = useRef<Uint8Array>(new Uint8Array(0));

  const stop = useCallback(() => {
    if (pumpRef.current) {
      window.clearInterval(pumpRef.current);
      pumpRef.current = null;
    }
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: "stop" }));
        wsRef.current.close();
      } catch {
        /* ignore */
      }
      wsRef.current = null;
    }
    pendingRef.current = new Uint8Array(0);
    setStatus("idle");
    setPartialText("");
  }, []);

  const start = useCallback(
    async (courseId: string, language = "fr") => {
      setError(null);
      setStatus("connecting");
      setFinalText("");
      setPartialText("");
      pendingRef.current = new Uint8Array(0);

      const token = tokenStore.access;
      if (!token) {
        setError("Non authentifié");
        setStatus("error");
        return;
      }

      const wsUrl = API_BASE.replace(/^http/, "ws") + "/api/ws/stream";
      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({ type: "init", course_id: courseId, language, token }),
        );
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string);
          if (msg.type === "ready") {
            setStatus("live");
          } else if (msg.type === "partial") {
            setPartialText(msg.text ?? "");
          } else if (msg.type === "final") {
            setFinalText((prev) => (prev ? `${prev} ${msg.text}` : msg.text));
            setPartialText("");
          } else if (msg.type === "error") {
            setError(msg.message ?? "Erreur de transcription");
            setStatus("error");
          }
        } catch {
          /* ignore */
        }
      };

      ws.onerror = () => {
        setError("Connexion streaming échouée");
        setStatus("error");
      };

      ws.onclose = () => {
        if (status !== "error") setStatus("idle");
      };

      // Pompe : récupère les chunks PCM16 (1600 éch.) du pipeline Rust, les
      // réassemble en trames de 4000 échantillons, et les envoie.
      pumpRef.current = window.setInterval(async () => {
        if (ws.readyState !== WebSocket.OPEN) return;
        try {
          const chunks = await audioBridge.drainStreamChunks();
          for (const b64 of chunks) {
            const incoming = new Uint8Array(base64ToPcm16(b64));
            // Concatène avec le reliquat
            const merged = new Uint8Array(pendingRef.current.length + incoming.length);
            merged.set(pendingRef.current, 0);
            merged.set(incoming, pendingRef.current.length);
            // Envoie les trames complètes de 4000 échantillons
            let offset = 0;
            while (merged.length - offset >= FRAME_BYTES) {
              ws.send(merged.slice(offset, offset + FRAME_BYTES).buffer);
              offset += FRAME_BYTES;
            }
            pendingRef.current = merged.slice(offset);
          }
        } catch {
          /* ignore */
        }
      }, 100);
    },
    [status],
  );

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { status, finalText, partialText, error, start, stop };
}
