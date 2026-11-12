/** Hook de transcription live : WS vers le backend + envoi des chunks audio. */

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, tokenStore } from "../lib/api";
import { audioBridge, base64ToPcm16 } from "../lib/audioBridge";

type Status = "idle" | "connecting" | "live" | "error";

interface LiveTranscription {
  status: Status;
  finalText: string;
  partialText: string;
  error: string | null;
  start: (courseId: string, language?: string) => Promise<void>;
  stop: () => void;
}

export function useLiveTranscription(): LiveTranscription {
  const [status, setStatus] = useState<Status>("idle");
  const [finalText, setFinalText] = useState("");
  const [partialText, setPartialText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pumpRef = useRef<number | null>(null);

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
    setStatus("idle");
    setPartialText("");
  }, []);

  const start = useCallback(
    async (courseId: string, language = "fr") => {
      setError(null);
      setStatus("connecting");
      setFinalText("");
      setPartialText("");

      const token = tokenStore.access;
      if (!token) {
        setError("Non authentifié");
        setStatus("error");
        return;
      }

      const wsUrl = API_BASE.replace(/^http/, "ws") + "/api/ws/transcribe";
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
        setError("Connexion WebSocket échouée");
        setStatus("error");
      };

      ws.onclose = () => {
        if (status !== "error") setStatus("idle");
      };

      // Pompe : envoie les chunks audio accumulés côté Rust vers le backend
      pumpRef.current = window.setInterval(async () => {
        if (ws.readyState !== WebSocket.OPEN) return;
        try {
          const chunks = await audioBridge.drainStreamChunks();
          for (const b64 of chunks) {
            ws.send(base64ToPcm16(b64));
          }
        } catch {
          /* ignore */
        }
      }, 200);
    },
    [status],
  );

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { status, finalText, partialText, error, start, stop };
}
