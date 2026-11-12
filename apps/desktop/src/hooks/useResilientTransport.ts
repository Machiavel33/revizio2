/** Hook de transport résilient : trames numérotées + ACK + réémission après reconnexion. */

import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { API_BASE, tokenStore } from "../lib/api";

type Status = "idle" | "connecting" | "live" | "reconnecting" | "error";

interface ResilientChunk {
  chunk_seq: number;
  frames_b64: string[];
  chunk_end: string;
  sha256: string;
}

interface ResilientTransport {
  status: Status;
  finalText: string;
  error: string | null;
  start: (courseId: string, language?: string) => Promise<void>;
  stop: () => Promise<void>;
}

function b64ToArrayBuffer(b64: string): ArrayBuffer {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

export function useResilientTransport(): ResilientTransport {
  const [status, setStatus] = useState<Status>("idle");
  const [finalText, setFinalText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pumpRef = useRef<number | null>(null);
  const courseIdRef = useRef<string | null>(null);
  const languageRef = useRef("fr");
  const reconnectRef = useRef<number | null>(null);

  const sendChunk = useCallback((ws: WebSocket, chunk: ResilientChunk) => {
    for (const frame of chunk.frames_b64) {
      ws.send(b64ToArrayBuffer(frame));
    }
    ws.send(chunk.chunk_end);
  }, []);

  const connect = useCallback(
    (courseId: string, language: string) => {
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
          JSON.stringify({
            type: "init",
            protocol: "rvzf-v1",
            course_id: courseId,
            language,
            token,
          }),
        );
      };

      ws.onmessage = async (ev) => {
        try {
          const msg = JSON.parse(ev.data as string);
          if (msg.type === "session.ready") {
            setStatus("live");
            // Réémet les fragments non acquittés (après reconnexion)
            const pending = await invoke<number[]>("pending_resilient_chunks");
            for (const seq of pending) {
              const chunk = await invoke<ResilientChunk | null>("load_resilient_chunk", {
                chunkSeq: seq,
              });
              if (chunk) sendChunk(ws, chunk);
            }
          } else if (msg.type === "chunk_ack") {
            await invoke("ack_resilient_chunk", { chunkSeq: msg.chunk_seq });
            if (msg.text) setFinalText((prev) => (prev ? `${prev} ${msg.text}` : msg.text));
          } else if (msg.type === "error") {
            setError(msg.detail ?? msg.message ?? "Erreur transport");
          }
        } catch {
          /* ignore */
        }
      };

      ws.onerror = () => setError("Connexion WebSocket échouée");

      ws.onclose = () => {
        wsRef.current = null;
        // Reconnexion automatique si la session est encore active
        if (courseIdRef.current && status !== "error") {
          setStatus("reconnecting");
          reconnectRef.current = window.setTimeout(() => {
            if (courseIdRef.current) connect(courseIdRef.current, languageRef.current);
          }, 2000);
        }
      };
    },
    [sendChunk, status],
  );

  const start = useCallback(
    async (courseId: string, language = "fr") => {
      setError(null);
      setFinalText("");
      setStatus("connecting");
      courseIdRef.current = courseId;
      languageRef.current = language;

      // Démarre la session résiliente côté Rust (chunker + spool)
      await invoke<string>("start_resilient_session", { spoolRoot: "revizio-spool" });
      connect(courseId, language);

      // Pompe : récupère les échantillons du buffer audio, les pousse dans le chunker,
      // envoie les fragments produits.
      pumpRef.current = window.setInterval(async () => {
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        try {
          const samplesB64 = await invoke<string>("drain_resilient_samples");
          if (!samplesB64) return;
          const chunks = await invoke<ResilientChunk[]>("push_resilient_samples", {
            samplesB64,
          });
          for (const c of chunks) sendChunk(ws, c);
        } catch {
          /* ignore */
        }
      }, 250);
    },
    [connect, sendChunk],
  );

  const stop = useCallback(async () => {
    if (pumpRef.current) {
      window.clearInterval(pumpRef.current);
      pumpRef.current = null;
    }
    if (reconnectRef.current) {
      window.clearTimeout(reconnectRef.current);
      reconnectRef.current = null;
    }
    courseIdRef.current = null;
    try {
      const last = await invoke<ResilientChunk | null>("finish_resilient_session");
      const ws = wsRef.current;
      if (last && ws && ws.readyState === WebSocket.OPEN) sendChunk(ws, last);
      // Laisse le temps aux ACK, puis ferme
      await new Promise((r) => setTimeout(r, 1500));
      ws?.send(JSON.stringify({ type: "stop" }));
      ws?.close();
    } catch {
      /* ignore */
    }
    await invoke("close_resilient_session").catch(() => {});
    setStatus("idle");
  }, [sendChunk]);

  useEffect(() => {
    return () => {
      if (pumpRef.current) window.clearInterval(pumpRef.current);
      if (reconnectRef.current) window.clearTimeout(reconnectRef.current);
    };
  }, []);

  return { status, finalText, error, start, stop };
}
