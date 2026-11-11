import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mic, Square, Loader2, SlidersHorizontal, Radio } from "lucide-react";
import { audioBridge, bytesToWavBlob } from "../lib/audioBridge";
import { api } from "../lib/api";
import type { InputDevice } from "../lib/types";
import Waveform from "../components/Waveform";
import { useLiveTranscription } from "../hooks/useLiveTranscription";

type Phase = "idle" | "recording" | "saving";

export default function RecordPage() {
  const navigate = useNavigate();
  const [devices, setDevices] = useState<InputDevice[]>([]);
  const [device, setDevice] = useState<string | undefined>(undefined);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [level, setLevel] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const [vadThreshold, setVadThreshold] = useState(0.012);
  const [calibrating, setCalibrating] = useState(false);
  const [calibration, setCalibration] = useState<string | null>(null);

  const live = useLiveTranscription();

  const levelTimer = useRef<number | null>(null);
  const clockTimer = useRef<number | null>(null);

  useEffect(() => {
    audioBridge
      .listDevices()
      .then((d) => {
        setDevices(d);
        const def = d.find((x) => x.is_default);
        setDevice(def?.name ?? d[0]?.name);
      })
      .catch((e) => setError(String(e)));
    return () => stopTimers();
  }, []);

  function stopTimers() {
    if (levelTimer.current) window.clearInterval(levelTimer.current);
    if (clockTimer.current) window.clearInterval(clockTimer.current);
    levelTimer.current = null;
    clockTimer.current = null;
  }

  async function calibrate() {
    setCalibrating(true);
    setCalibration(null);
    setError(null);
    try {
      const res = await audioBridge.calibrate(device, 2000);
      setVadThreshold(res.suggested_threshold);
      setCalibration(
        `Bruit ambiant : ${(res.ambient_rms * 100).toFixed(1)}% — seuil VAD réglé à ${(
          res.suggested_threshold * 100
        ).toFixed(1)}%`,
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setCalibrating(false);
    }
  }

  async function start() {
    setError(null);
    try {
      await audioBridge.start(device, vadThreshold);
      setPhase("recording");
      setElapsed(0);
      levelTimer.current = window.setInterval(async () => {
        try {
          setLevel(await audioBridge.getLevel());
        } catch {
          /* ignore */
        }
      }, 80);
      clockTimer.current = window.setInterval(() => setElapsed((e) => e + 1), 1000);
      // Démarre la transcription live (best-effort : si pas de clé Deepgram, erreur non bloquante)
      void live.start("fr");
    } catch (e) {
      setError(String(e));
    }
  }

  async function stop() {
    stopTimers();
    live.stop();
    setPhase("saving");
    setLevel(0);
    try {
      const bytes = await audioBridge.stop();
      const blob = bytesToWavBlob(bytes);
      const course = await api.createCourse(
        title || "Cours sans titre",
        subject || undefined,
      );
      await api.uploadAudio(course.id, blob, "cours.wav");
      await api.processCourse(course.id);
      navigate(`/courses/${course.id}`);
    } catch (e) {
      setError(String(e));
      setPhase("idle");
    }
  }

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-8">
      <div>
        <h1 className="font-display text-3xl font-bold">Enregistrer un cours</h1>
        <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
          Calibrez votre micro, vérifiez le niveau, puis lancez l'enregistrement.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Colonne gauche : config + enregistrement */}
        <div className="space-y-4">
          <div className="card space-y-4">
            <div>
              <label className="label">Titre du cours</label>
              <input
                className="input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Droit constitutionnel — séance 3"
                disabled={phase !== "idle"}
              />
            </div>
            <div>
              <label className="label">Matière (optionnel)</label>
              <input
                className="input"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Droit"
                disabled={phase !== "idle"}
              />
            </div>
            <div>
              <label className="label">Microphone</label>
              <select
                className="input"
                value={device ?? ""}
                onChange={(e) => setDevice(e.target.value)}
                disabled={phase !== "idle"}
              >
                {devices.map((d) => (
                  <option key={d.name} value={d.name}>
                    {d.name} {d.is_default ? "(défaut)" : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Calibration */}
            <div className="rounded-md bg-[color:var(--bg-inset)] p-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
                  <SlidersHorizontal size={15} />
                  Seuil anti-bruit (VAD)
                </span>
                <span className="font-mono text-xs text-[color:var(--accent-primary)]">
                  {(vadThreshold * 100).toFixed(1)}%
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={0.2}
                step={0.001}
                value={vadThreshold}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setVadThreshold(v);
                  if (phase === "recording") void audioBridge.setVadThreshold(v);
                }}
                className="mt-2 w-full accent-[color:var(--accent-primary)]"
              />
              <button
                onClick={calibrate}
                disabled={calibrating || phase !== "idle"}
                className="btn-secondary mt-2 w-full py-2 text-xs"
              >
                {calibrating ? "Mesure du bruit ambiant…" : "Calibrer automatiquement"}
              </button>
              {calibration && (
                <p className="mt-2 text-xs text-[color:var(--accent-success)]">{calibration}</p>
              )}
            </div>
          </div>

          <div className="card flex flex-col items-center gap-5 py-8">
            <div className="font-mono text-5xl font-medium tabular-nums tracking-tight">
              {mm}:{ss}
            </div>
            <Waveform level={level} active={phase === "recording"} />

            {phase === "idle" && (
              <button onClick={start} className="btn-primary px-8 py-3 text-base">
                <Mic size={20} />
                Démarrer l'enregistrement
              </button>
            )}
            {phase === "recording" && (
              <button
                onClick={stop}
                className="rec-pulse inline-flex items-center gap-2 rounded-md bg-[color:var(--accent-danger)] px-8 py-3 text-base font-semibold text-white"
              >
                <Square size={18} fill="currentColor" />
                Arrêter et générer la fiche
              </button>
            )}
            {phase === "saving" && (
              <div className="flex items-center gap-2 text-[color:var(--text-secondary)]">
                <Loader2 size={18} className="animate-spin" />
                Envoi et traitement…
              </div>
            )}
          </div>
        </div>

        {/* Colonne droite : transcription live */}
        <div className="card flex flex-col">
          <div className="mb-3 flex items-center gap-2">
            <Radio
              size={16}
              className={
                live.status === "live"
                  ? "text-[color:var(--accent-success)]"
                  : "text-[color:var(--text-muted)]"
              }
            />
            <h2 className="font-display text-lg font-semibold">Transcription live</h2>
            <span className="ml-auto text-xs text-[color:var(--text-muted)]">
              {live.status === "live"
                ? "en direct"
                : live.status === "connecting"
                  ? "connexion…"
                  : live.status === "error"
                    ? "indisponible"
                    : "en attente"}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto rounded-md bg-[color:var(--bg-inset)] p-4 text-sm leading-relaxed">
            {live.finalText || live.partialText ? (
              <p className="text-[color:var(--text-secondary)]">
                {live.finalText}{" "}
                <span className="text-[color:var(--text-muted)]">{live.partialText}</span>
              </p>
            ) : (
              <p className="text-[color:var(--text-muted)]">
                {live.status === "error"
                  ? live.error ?? "Transcription live indisponible (clé Deepgram requise)."
                  : "Le texte apparaîtra ici pendant l'enregistrement."}
              </p>
            )}
          </div>
        </div>
      </div>

      {error && (
        <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-4 py-3 text-sm text-[color:var(--accent-danger)]">
          {error}
        </p>
      )}
    </div>
  );
}
