import { useState } from "react";
import {
  Download,
  BookOpen,
  Lightbulb,
  HelpCircle,
  Layers,
  Target,
  Sigma,
  AlertTriangle,
  Sparkles,
  Info,
  FlaskConical,
} from "lucide-react";
import type { StudySheet, SheetSection, SectionType } from "../lib/types";
import { exportSheetToPdf } from "../lib/pdf";

/** Style visuel par type de section (mise en avant). */
const SECTION_STYLE: Record<
  SectionType,
  { icon: typeof Info; color: string; bg: string; border: string; label: string }
> = {
  normal: {
    icon: Info,
    color: "var(--text-primary)",
    bg: "var(--bg-surface)",
    border: "var(--border-subtle)",
    label: "",
  },
  definition: {
    icon: BookOpen,
    color: "var(--accent-primary)",
    bg: "rgba(0,229,255,0.06)",
    border: "rgba(0,229,255,0.35)",
    label: "Définition",
  },
  formula: {
    icon: Sigma,
    color: "var(--accent-secondary)",
    bg: "rgba(177,78,255,0.06)",
    border: "rgba(177,78,255,0.35)",
    label: "Formule",
  },
  example: {
    icon: FlaskConical,
    color: "var(--accent-success)",
    bg: "rgba(0,255,163,0.06)",
    border: "rgba(0,255,163,0.35)",
    label: "Exemple",
  },
  warning: {
    icon: AlertTriangle,
    color: "var(--accent-danger)",
    bg: "rgba(255,59,92,0.06)",
    border: "rgba(255,59,92,0.35)",
    label: "Attention",
  },
  tip: {
    icon: Sparkles,
    color: "var(--accent-warning)",
    bg: "rgba(255,184,0,0.06)",
    border: "rgba(255,184,0,0.35)",
    label: "Astuce",
  },
};

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
        <div className="flex items-center gap-3">
          <h2 className="font-display text-2xl font-bold">{c.title || "Fiche de révision"}</h2>
          {c.domain_label && c.domain && c.domain !== "generic" && (
            <span className="rounded bg-[color:var(--accent-primary)]/15 px-2 py-0.5 text-xs font-semibold uppercase text-[color:var(--accent-primary)]">
              {c.domain_label}
            </span>
          )}
        </div>
        <button onClick={handleExport} disabled={exporting} className="btn-secondary">
          <Download size={16} />
          {exporting ? "Export…" : "Exporter en PDF"}
        </button>
      </div>

      {/* Avertissement du domaine (garde-fou) */}
      {c.disclaimer && (
        <div className="flex gap-2 rounded-md border border-[color:var(--accent-warning)]/40 bg-[color:var(--accent-warning)]/10 p-3 text-sm text-[color:var(--text-secondary)]">
          <AlertTriangle size={18} className="mt-0.5 shrink-0 text-[color:var(--accent-warning)]" />
          <p>{c.disclaimer}</p>
        </div>
      )}

      {/* Objectifs d'apprentissage */}
      {c.learning_objectives && c.learning_objectives.length > 0 && (
        <section className="card border-l-4 border-[color:var(--accent-primary)]">
          <div className="mb-3 flex items-center gap-2 text-[color:var(--accent-primary)]">
            <Target size={18} />
            <h3 className="font-display text-lg font-semibold">Objectifs d'apprentissage</h3>
          </div>
          <ul className="space-y-1.5">
            {c.learning_objectives.map((o, i) => (
              <li key={i} className="flex gap-2 text-sm text-[color:var(--text-secondary)]">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[color:var(--accent-primary)]" />
                {o}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Résumé */}
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

      {/* Notions clés */}
      {c.key_concepts.length > 0 && (
        <section className="card">
          <div className="mb-4 flex items-center gap-2 text-[color:var(--accent-secondary)]">
            <Lightbulb size={18} />
            <h3 className="font-display text-lg font-semibold">Notions clés</h3>
          </div>
          <dl className="space-y-3">
            {c.key_concepts.map((k, i) => (
              <div
                key={i}
                className={`rounded-md p-3 ${
                  k.importance === "high"
                    ? "border-l-4 border-[color:var(--accent-secondary)] bg-[color:var(--bg-inset)]"
                    : "bg-[color:var(--bg-inset)]"
                }`}
              >
                <dt className="flex items-center gap-2 font-medium text-[color:var(--text-primary)]">
                  {k.term}
                  {k.importance === "high" && (
                    <span className="rounded bg-[color:var(--accent-secondary)]/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[color:var(--accent-secondary)]">
                      Essentiel
                    </span>
                  )}
                </dt>
                <dd className="mt-1 text-sm text-[color:var(--text-secondary)]">{k.definition}</dd>
                {k.example && (
                  <dd className="mt-1.5 text-xs italic text-[color:var(--text-muted)]">
                    Ex. : {k.example}
                  </dd>
                )}
              </div>
            ))}
          </dl>
        </section>
      )}

      {/* Formules */}
      {c.formulas && c.formulas.length > 0 && (
        <section className="card">
          <div className="mb-4 flex items-center gap-2 text-[color:var(--accent-secondary)]">
            <Sigma size={18} />
            <h3 className="font-display text-lg font-semibold">Formules</h3>
          </div>
          <div className="space-y-2">
            {c.formulas.map((f, i) => (
              <div key={i} className="rounded-md bg-[color:var(--bg-inset)] p-3">
                <p className="font-mono text-base text-[color:var(--accent-secondary)]">
                  {f.expression}
                </p>
                {f.name && (
                  <p className="mt-1 text-sm font-medium text-[color:var(--text-primary)]">
                    {f.name}
                  </p>
                )}
                {f.meaning && (
                  <p className="mt-0.5 text-xs text-[color:var(--text-muted)]">{f.meaning}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Sections (avec mise en avant par type) */}
      {c.sections.map((s, i) => (
        <SectionBlock key={i} section={s} />
      ))}

      {/* Pièges à éviter */}
      {c.pitfalls && c.pitfalls.length > 0 && (
        <section className="card border-l-4 border-[color:var(--accent-danger)]">
          <div className="mb-3 flex items-center gap-2 text-[color:var(--accent-danger)]">
            <AlertTriangle size={18} />
            <h3 className="font-display text-lg font-semibold">Pièges à éviter</h3>
          </div>
          <ul className="space-y-1.5">
            {c.pitfalls.map((p, i) => (
              <li key={i} className="flex gap-2 text-sm text-[color:var(--text-secondary)]">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[color:var(--accent-danger)]" />
                {p}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Mnémotechniques */}
      {c.mnemonics && c.mnemonics.length > 0 && (
        <section className="card border-l-4 border-[color:var(--accent-warning)]">
          <div className="mb-3 flex items-center gap-2 text-[color:var(--accent-warning)]">
            <Sparkles size={18} />
            <h3 className="font-display text-lg font-semibold">Moyens mnémotechniques</h3>
          </div>
          <ul className="space-y-1.5">
            {c.mnemonics.map((m, i) => (
              <li key={i} className="text-sm text-[color:var(--text-secondary)]">
                {m}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Flashcards */}
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

      {/* Questions de révision */}
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

function SectionBlock({ section }: { section: SheetSection }) {
  const type = (section.type ?? "normal") as SectionType;
  const style = SECTION_STYLE[type] ?? SECTION_STYLE.normal;
  const Icon = style.icon;
  return (
    <section
      className="card"
      style={{ backgroundColor: style.bg, borderColor: style.border }}
    >
      <div className="mb-3 flex items-center gap-2" style={{ color: style.color }}>
        <Icon size={18} />
        <h3 className="font-display text-lg font-semibold">{section.heading}</h3>
        {style.label && (
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase"
            style={{ backgroundColor: style.border, color: style.color }}
          >
            {style.label}
          </span>
        )}
      </div>
      <ul className="space-y-2">
        {section.points.map((p, j) => (
          <li key={j} className="flex gap-2 text-sm text-[color:var(--text-secondary)]">
            <span
              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: style.color }}
            />
            {p}
          </li>
        ))}
      </ul>
    </section>
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
