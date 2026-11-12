import { useEffect, useState } from "react";
import { KeyRound, Trash2, Plus, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import type { ApiKey } from "../lib/types";
import TwoFactorSection from "../components/TwoFactorSection";
import KeyModeSection from "../components/KeyModeSection";
import ApiKeyGuide from "../components/ApiKeyGuide";

const PROVIDERS = [
  { id: "openai", label: "OpenAI", hint: "sk-…" },
  { id: "anthropic", label: "Anthropic (Claude)", hint: "sk-ant-…" },
  { id: "deepgram", label: "Deepgram", hint: "clé API Deepgram" },
];

export default function SettingsPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [provider, setProvider] = useState("openai");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setKeys(await api.listKeys());
  }
  useEffect(() => {
    void load();
  }, []);

  async function add() {
    setError(null);
    setBusy(true);
    try {
      await api.createKey(provider, value, true);
      setValue("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await api.deleteKey(id);
    await load();
  }

  async function rotate(k: ApiKey) {
    const value = window.prompt(`Nouvelle clé ${k.provider} (remplace ${k.key_hint}) :`);
    if (!value) return;
    setError(null);
    try {
      await api.rotateKey(k.id, k.provider, value);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const current = PROVIDERS.find((p) => p.id === provider);

  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="font-display text-3xl font-bold">Réglages</h1>
      <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
        Connectez vos propres clés API (BYOK). Elles sont chiffrées et ne quittent jamais le
        serveur en clair.
      </p>

      <div className="card mt-6 space-y-4">
        <div className="flex items-center gap-2 text-[color:var(--accent-primary)]">
          <KeyRound size={18} />
          <h2 className="font-display text-lg font-semibold">Clés API</h2>
        </div>

        <div className="grid gap-3 sm:grid-cols-[1fr_2fr_auto]">
          <select className="input" value={provider} onChange={(e) => setProvider(e.target.value)}>
            {PROVIDERS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
          <input
            className="input"
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={current?.hint}
          />
          <button onClick={add} disabled={busy || !value} className="btn-primary">
            <Plus size={16} />
            Ajouter
          </button>
        </div>

        {error && (
          <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
            {error}
          </p>
        )}

        <div className="space-y-2">
          {keys.length === 0 ? (
            <p className="text-sm text-[color:var(--text-muted)]">Aucune clé configurée.</p>
          ) : (
            keys.map((k) => (
              <div
                key={k.id}
                className="flex items-center justify-between rounded-md bg-[color:var(--bg-inset)] px-3 py-2.5"
              >
                <div className="flex items-center gap-3">
                  <span className="rounded bg-[color:var(--bg-elevated)] px-2 py-0.5 text-xs font-medium uppercase text-[color:var(--accent-primary)]">
                    {k.provider}
                  </span>
                  <span className="font-mono text-sm text-[color:var(--text-secondary)]">
                    {k.key_hint}
                  </span>
                  {k.is_default && (
                    <span className="text-xs text-[color:var(--accent-success)]">défaut</span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => rotate(k)}
                    className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-[color:var(--accent-primary)]"
                    aria-label="Rotation"
                    title="Rotation de la clé"
                  >
                    <RefreshCw size={16} />
                  </button>
                  <button
                    onClick={() => remove(k.id)}
                    className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-[color:var(--accent-danger)]"
                    aria-label="Supprimer"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <KeyModeSection />
      <ApiKeyGuide />
      <TwoFactorSection />
    </div>
  );
}
