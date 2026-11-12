import { useEffect, useState } from "react";
import { Cpu, KeyRound } from "lucide-react";
import { api } from "../lib/api";

export default function KeyModeSection() {
  const [mode, setMode] = useState<string | null>(null);
  const [platformAvailable, setPlatformAvailable] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const res = await api.getKeyMode();
      setMode(res.key_mode);
      setPlatformAvailable(res.platform_available);
    } catch {
      setMode("byok");
    }
  }
  useEffect(() => {
    void load();
  }, []);

  async function choose(next: string) {
    setError(null);
    setBusy(true);
    try {
      const res = await api.setKeyMode(next);
      setMode(res.key_mode);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const hasPlatform = platformAvailable.length > 0;

  return (
    <div className="card mt-6 space-y-4">
      <div className="flex items-center gap-2 text-[color:var(--accent-primary)]">
        <Cpu size={18} />
        <h2 className="font-display text-lg font-semibold">Source des clés IA</h2>
      </div>
      <p className="text-sm text-[color:var(--text-secondary)]">
        Choisissez d'utiliser vos propres clés API (BYOK) ou les clés fournies par la
        plateforme.
      </p>

      {error && (
        <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
          {error}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <button
          onClick={() => choose("byok")}
          disabled={busy || mode === "byok"}
          className={`rounded-md border p-4 text-left transition-colors ${
            mode === "byok"
              ? "border-[color:var(--accent-primary)] bg-[color:var(--accent-primary)]/5"
              : "border-[color:var(--border-subtle)] hover:border-[color:var(--border-glow)]"
          }`}
        >
          <div className="flex items-center gap-2 font-medium">
            <KeyRound size={16} /> Mes propres clés (BYOK)
          </div>
          <p className="mt-1 text-xs text-[color:var(--text-secondary)]">
            Vous fournissez vos clés OpenAI / Anthropic / Deepgram.
          </p>
        </button>

        <button
          onClick={() => choose("platform")}
          disabled={busy || mode === "platform" || !hasPlatform}
          className={`rounded-md border p-4 text-left transition-colors ${
            mode === "platform"
              ? "border-[color:var(--accent-primary)] bg-[color:var(--accent-primary)]/5"
              : "border-[color:var(--border-subtle)] hover:border-[color:var(--border-glow)]"
          } ${!hasPlatform ? "cursor-not-allowed opacity-50" : ""}`}
        >
          <div className="flex items-center gap-2 font-medium">
            <Cpu size={16} /> Clés de la plateforme
          </div>
          <p className="mt-1 text-xs text-[color:var(--text-secondary)]">
            {hasPlatform
              ? `Utilise les clés fournies (${platformAvailable.join(", ")}).`
              : "Aucune clé plateforme disponible pour l'instant."}
          </p>
        </button>
      </div>
    </div>
  );
}
