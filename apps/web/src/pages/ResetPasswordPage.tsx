import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import Logo from "../components/Logo";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="card w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <Logo size={40} />
          <h1 className="font-display text-2xl font-bold">Nouveau mot de passe</h1>
        </div>

        {!token ? (
          <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
            Lien invalide (token manquant).
          </p>
        ) : done ? (
          <div className="space-y-4">
            <p className="rounded-md bg-[color:var(--accent-success)]/10 px-3 py-2 text-sm text-[color:var(--accent-success)]">
              Mot de passe réinitialisé. Vous pouvez vous connecter.
            </p>
            <Link to="/login" className="btn-primary w-full">
              Se connecter
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label">Nouveau mot de passe</label>
              <input
                className="input"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            {error && (
              <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
                {error}
              </p>
            )}
            <button type="submit" disabled={busy} className="btn-primary w-full">
              {busy ? "…" : "Réinitialiser"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
