import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import Logo from "../components/Logo";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="card w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <Logo size={40} />
          <div>
            <h1 className="font-display text-2xl font-bold">Revizio</h1>
            <p className="text-sm text-[color:var(--text-secondary)]">
              Vos cours, transcrits et révisés.
            </p>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === "register" && (
            <div>
              <label className="label">Nom</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
          )}
          <div>
            <label className="label">Email</label>
            <input
              className="input"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="etudiant@exemple.fr"
            />
          </div>
          <div>
            <label className="label">Mot de passe</label>
            <input
              className="input"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
              {error}
            </p>
          )}
          <button type="submit" disabled={busy} className="btn-primary w-full">
            {busy ? "…" : mode === "login" ? "Se connecter" : "Créer un compte"}
          </button>
        </form>

        <button
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="mt-4 w-full text-center text-sm text-[color:var(--text-secondary)] hover:text-[color:var(--accent-primary)]"
        >
          {mode === "login" ? "Pas de compte ? S'inscrire" : "Déjà un compte ? Se connecter"}
        </button>

        {mode === "login" && (
          <Link
            to="/forgot-password"
            className="mt-2 block w-full text-center text-xs text-[color:var(--text-muted)] hover:text-[color:var(--accent-primary)]"
          >
            Mot de passe oublié ?
          </Link>
        )}
      </div>
    </div>
  );
}
