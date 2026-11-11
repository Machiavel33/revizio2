import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mic, Square, Loader2 } from "lucide-react";
import { audioBridge, bytesToWavBlob } from "../lib/audioBridge";
import { api } from "../lib/api";
import type { InputDevice } from "../lib/types";
import Waveform from "../components/Waveform";

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

  async function start() {
    setError(null);
    try {
      await audioBridge.start(device);
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
    } catch (e) {
      setError(String(e));
    }
  }

  async function stop() {
    stopTimers();
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
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <div>
        <h1 className="font-display text-3xl font-bold">Enregistrer un cours</h1>
        <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
          Choisissez votre micro, vérifiez le niveau, puis lancez l'enregistrement.
        </p>
      </div>

      <div className="card space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
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
      </div>

      <div className="card flex flex-col items-center gap-6 py-10">
        <div className="font-mono text-6xl font-medium tabular-nums tracking-tight">
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
            Enregistrement terminé, envoi et traitement…
          </div>
        )}
      </div>

      {error && (
        <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-4 py-3 text-sm text-[color:var(--accent-danger)]">
          {error}
        </p>
      )}
    </div>
  );
}
