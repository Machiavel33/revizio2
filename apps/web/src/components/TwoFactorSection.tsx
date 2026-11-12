import { useEffect, useState } from "react";
import { ShieldCheck, ShieldOff, Copy } from "lucide-react";
import { api } from "../lib/api";

export default function TwoFactorSection() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [uri, setUri] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const s = await api.totpStatus();
      setEnabled(s.enabled);
    } catch {
      setEnabled(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);

  async function startSetup() {
    setError(null);
    setBusy(true);
    try {
      const res = await api.totpSetup();
      setSecret(res.secret);
      setUri(res.provisioning_uri);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function confirmEnable() {
    setError(null);
    setBusy(true);
    try {
      const res = await api.totpEnable(code);
      setBackupCodes(res.backup_codes);
      setEnabled(true);
      setSecret(null);
      setUri(null);
      setCode("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setError(null);
    setBusy(true);
    try {
      await api.totpDisable(code);
      setEnabled(false);
      setCode("");
      setBackupCodes(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card mt-6 space-y-4">
      <div className="flex items-center gap-2 text-[color:var(--accent-primary)]">
        {enabled ? <ShieldCheck size={18} /> : <ShieldOff size={18} />}
        <h2 className="font-display text-lg font-semibold">Double authentification (2FA)</h2>
        <span
          className={`ml-auto text-xs ${enabled ? "text-[color:var(--accent-success)]" : "text-[color:var(--text-muted)]"}`}
        >
          {enabled === null ? "…" : enabled ? "activée" : "désactivée"}
        </span>
      </div>

      <p className="text-sm text-[color:var(--text-secondary)]">
        Facultatif. Protège votre compte avec une application d'authentification (Google
        Authenticator, Authy, 1Password).
      </p>

      {error && (
        <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
          {error}
        </p>
      )}

      {!enabled && !secret && (
        <button onClick={startSetup} disabled={busy} className="btn-secondary">
          Activer la 2FA
        </button>
      )}

      {secret && !enabled && (
        <div className="space-y-3 rounded-md bg-[color:var(--bg-inset)] p-4">
          <p className="text-sm text-[color:var(--text-secondary)]">
            Ajoutez ce secret dans votre application, puis saisissez le code à 6 chiffres.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 break-all rounded bg-[color:var(--bg-elevated)] px-2 py-1.5 font-mono text-xs">
              {secret}
            </code>
            <button
              onClick={() => navigator.clipboard?.writeText(secret)}
              className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-[color:var(--accent-primary)]"
              aria-label="Copier"
            >
              <Copy size={16} />
            </button>
          </div>
          {uri && (
            <p className="break-all text-xs text-[color:var(--text-muted)]">{uri}</p>
          )}
          <div className="flex gap-2">
            <input
              className="input"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="123456"
              maxLength={6}
            />
            <button onClick={confirmEnable} disabled={busy || code.length !== 6} className="btn-primary">
              Confirmer
            </button>
          </div>
        </div>
      )}

      {backupCodes && (
        <div className="rounded-md border border-[color:var(--accent-warning)]/30 bg-[color:var(--accent-warning)]/5 p-4">
          <p className="mb-2 text-sm font-medium text-[color:var(--accent-warning)]">
            Codes de secours (à conserver, affichés une seule fois)
          </p>
          <div className="grid grid-cols-2 gap-1 font-mono text-xs text-[color:var(--text-secondary)]">
            {backupCodes.map((c) => (
              <span key={c}>{c}</span>
            ))}
          </div>
        </div>
      )}

      {enabled && (
        <div className="flex gap-2">
          <input
            className="input"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Code TOTP ou code de secours"
          />
          <button onClick={disable} disabled={busy || !code} className="btn-secondary">
            Désactiver
          </button>
        </div>
      )}
    </div>
  );
}
