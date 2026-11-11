import { useState } from "react";
import { Download, BookOpen, Lightbulb, HelpCircle, Layers } from "lucide-react";
import type { StudySheet } from "../lib/types";
import { exportSheetToPdf } from "../lib/pdf";

export default function StudySheetView({ sheet }: { sheet: StudySheet }) {
  const c = sheet.content;
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    setExporting(true);
    try {
      await exportSheetToPdf(sheet);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-2xl font-bold">Fiche de révision</h2>
        <button onClick={handleExport} disabled={exporting} className="btn-secondary">
          <Download size={16} />
          {exporting ? "Export…" : "Exporter en PDF"}
        </button>
      </div>

      <section className="card">
        <div className="mb-3 flex items-center gap-2 text-[color:var(--accent-primary)]">
          <BookOpen size={18} />
          <h3 className="font-display text-lg font-semibold">Résumé</h3>
        </div>
        <p className="leading-relaxed text-[color:var(--text-secondary)]">{c.summary}</p>
        <p className="mt-3 text-xs text-[color:var(--text-muted)]">
          Temps de révision estimé : {c.estimated_review_time_min} min
        </p>
      </section>

      {c.key_concepts.length > 0 && (
        <section className="card">
          <div className="mb-4 flex items-center gap-2 text-[color:var(--accent-secondary)]">
            <Lightbulb size={18} />
            <h3 className="font-display text-lg font-semibold">Notions clés</h3>
          </div>
          <dl className="space-y-3">
            {c.key_concepts.map((k, i) => (
              <div key={i} className="rounded-md bg-[color:var(--bg-inset)] p-3">
                <dt className="font-medium text-[color:var(--text-primary)]">{k.term}</dt>
                <dd className="mt-1 text-sm text-[color:var(--text-secondary)]">{k.definition}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {c.sections.map((s, i) => (
        <section key={i} className="card">
          <h3 className="mb-3 font-display text-lg font-semibold">{s.heading}</h3>
          <ul className="space-y-2">
            {s.points.map((p, j) => (
              <li key={j} className="flex gap-2 text-sm text-[color:var(--text-secondary)]">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[color:var(--accent-primary)]" />
                {p}
              </li>
            ))}
          </ul>
        </section>
      ))}

      {c.flashcards.length > 0 && (
        <section className="card">
          <div className="mb-4 flex items-center gap-2 text-[color:var(--accent-success)]">
            <Layers size={18} />
            <h3 className="font-display text-lg font-semibold">Flashcards</h3>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {c.flashcards.map((f, i) => (
              <Flashcard key={i} question={f.question} answer={f.answer} />
            ))}
          </div>
        </section>
      )}

      {c.review_questions.length > 0 && (
        <section className="card">
          <div className="mb-4 flex items-center gap-2 text-[color:var(--accent-warning)]">
            <HelpCircle size={18} />
            <h3 className="font-display text-lg font-semibold">Questions de révision</h3>
          </div>
          <ol className="list-decimal space-y-2 pl-5 text-sm text-[color:var(--text-secondary)]">
            {c.review_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

function Flashcard({ question, answer }: { question: string; answer: string }) {
  const [open, setOpen] = useState(false);
  return (
    <button
      onClick={() => setOpen((o) => !o)}
      className="rounded-md border border-[color:var(--border-subtle)] bg-[color:var(--bg-inset)] p-3 text-left transition-colors hover:border-[color:var(--border-glow)]"
    >
      <p className="text-sm font-medium text-[color:var(--text-primary)]">{question}</p>
      <p
        className={`mt-2 text-sm text-[color:var(--text-secondary)] transition-opacity ${
          open ? "opacity-100" : "select-none opacity-0"
        }`}
      >
        {answer}
      </p>
      {!open && (
        <span className="mt-1 inline-block text-xs text-[color:var(--accent-primary)]">
          Cliquer pour révéler
        </span>
      )}
    </button>
  );
}
