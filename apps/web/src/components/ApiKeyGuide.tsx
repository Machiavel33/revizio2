import { useState } from "react";
import { HelpCircle, ChevronDown } from "lucide-react";

export default function ApiKeyGuide() {
  const [open, setOpen] = useState(false);

  return (
    <div className="card mt-6">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 text-left"
      >
        <HelpCircle size={18} className="text-[color:var(--accent-primary)]" />
        <h2 className="font-display text-lg font-semibold">
          Comment obtenir une clé API ? (guide)
        </h2>
        <ChevronDown
          size={18}
          className={`ml-auto text-[color:var(--text-muted)] transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="mt-4 space-y-4 text-sm text-[color:var(--text-secondary)]">
          <div className="rounded-md border border-[color:var(--accent-warning)]/30 bg-[color:var(--accent-warning)]/5 p-3">
            <p className="font-medium text-[color:var(--accent-warning)]">
              ⚠️ Un abonnement ChatGPT Plus / Claude Pro ne donne PAS accès à l'API.
            </p>
            <p className="mt-1 text-xs">
              L'API est facturée séparément (à l'usage) par OpenAI et Anthropic. Un compte
              ChatGPT Plus ne permet pas de générer de clé API. Si tu n'as pas de clé API,
              utilise simplement le mode « Clés de la plateforme » (aucune config requise).
            </p>
          </div>

          <div>
            <p className="mb-1 font-medium text-[color:var(--text-primary)]">
              OpenAI (transcription + fiches)
            </p>
            <ol className="list-decimal space-y-1 pl-5 text-xs">
              <li>
                Va sur <span className="font-mono">platform.openai.com</span> et connecte-toi.
              </li>
              <li>
                Menu <strong>API keys</strong> → <strong>Create new secret key</strong>.
              </li>
              <li>Copie la clé (elle commence par <span className="font-mono">sk-</span>).</li>
              <li>Colle-la dans le champ ci-dessus, provider « OpenAI ».</li>
              <li>
                Ajoute un moyen de paiement dans <strong>Billing</strong> (l'API est payante à
                l'usage, quelques centimes par cours).
              </li>
            </ol>
          </div>

          <div>
            <p className="mb-1 font-medium text-[color:var(--text-primary)]">
              Anthropic (génération de fiches)
            </p>
            <ol className="list-decimal space-y-1 pl-5 text-xs">
              <li>
                Va sur <span className="font-mono">console.anthropic.com</span>.
              </li>
              <li>
                <strong>API Keys</strong> → <strong>Create Key</strong>.
              </li>
              <li>Copie la clé (<span className="font-mono">sk-ant-...</span>) et colle-la.</li>
            </ol>
          </div>

          <div>
            <p className="mb-1 font-medium text-[color:var(--text-primary)]">
              Deepgram (transcription live, optionnel)
            </p>
            <ol className="list-decimal space-y-1 pl-5 text-xs">
              <li>
                Va sur <span className="font-mono">console.deepgram.com</span>.
              </li>
              <li>
                <strong>API Keys</strong> → crée une clé et colle-la.
              </li>
            </ol>
          </div>

          <p className="text-xs text-[color:var(--text-muted)]">
            Tes clés sont chiffrées (AES-256-GCM) et ne sont jamais affichées en clair après
            l'enregistrement.
          </p>
        </div>
      )}
    </div>
  );
}
