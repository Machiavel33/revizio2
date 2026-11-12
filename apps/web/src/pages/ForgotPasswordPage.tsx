import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import Logo from "../components/Logo";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.forgotPassword(email);
      setSent(true);
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
          <h1 className="font-display text-2xl font-bold">Mot de passe oublié</h1>
        </div>

        {sent ? (
          <div className="space-y-4">
            <p className="rounded-md bg-[color:var(--accent-success)]/10 px-3 py-2 text-sm text-[color:var(--accent-success)]">
              Si un compte existe pour cet email, un lien de réinitialisation a été envoyé.
              Vérifiez votre boîte de réception.
            </p>
            <Link to="/login" className="btn-secondary w-full">
              Retour à la connexion
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <p className="text-sm text-[color:var(--text-secondary)]">
              Saisissez votre email. Nous vous enverrons un lien pour réinitialiser votre mot de
              passe.
            </p>
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
            {error && (
              <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
                {error}
              </p>
            )}
            <button type="submit" disabled={busy} className="btn-primary w-full">
              {busy ? "…" : "Envoyer le lien"}
            </button>
            <Link
              to="/login"
              className="block w-full text-center text-xs text-[color:var(--text-muted)] hover:text-[color:var(--accent-primary)]"
            >
              Retour à la connexion
            </Link>
          </form>
        )}
      </div>
    </div>
  );
}
