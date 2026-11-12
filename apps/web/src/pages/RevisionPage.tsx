import { useEffect, useState } from "react";
import {
  FileText,
  FolderPlus,
  Plus,
  Trash2,
  Sparkles,
  Loader2,
  ChevronRight,
} from "lucide-react";
import { api } from "../lib/api";
import type { ExamFolder, Quiz, Sheet } from "../lib/types";

type Tab = "sheets" | "folders" | "quizzes";

export default function RevisionPage() {
  const [tab, setTab] = useState<Tab>("sheets");
  const [sheets, setSheets] = useState<Sheet[]>([]);
  const [folders, setFolders] = useState<ExamFolder[]>([]);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [s, f, q] = await Promise.all([
        api.listSheets(),
        api.listFolders(),
        api.listQuizzes(),
      ]);
      setSheets(s);
      setFolders(f);
      setQuizzes(q);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="mb-6">
        <h1 className="font-display text-3xl font-bold">Révision</h1>
        <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
          Vos fiches, dossiers d'examen et quiz générés par l'IA.
        </p>
      </div>

      <div className="mb-6 flex gap-2">
        {(["sheets", "folders", "quizzes"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t
                ? "bg-[color:var(--bg-elevated)] text-[color:var(--accent-primary)]"
                : "text-[color:var(--text-secondary)] hover:bg-[color:var(--bg-elevated)]"
            }`}
          >
            {t === "sheets" ? "Fiches" : t === "folders" ? "Dossiers d'examen" : "Quiz"}
          </button>
        ))}
      </div>

      {error && (
        <p className="mb-4 rounded-md bg-[color:var(--accent-danger)]/10 px-4 py-3 text-sm text-[color:var(--accent-danger)]">
          {error}
        </p>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-[color:var(--text-secondary)]">
          <Loader2 className="animate-spin" size={18} /> Chargement…
        </div>
      ) : tab === "sheets" ? (
        <SheetsTab sheets={sheets} onRefresh={load} />
      ) : tab === "folders" ? (
        <FoldersTab folders={folders} sheets={sheets} onRefresh={load} />
      ) : (
        <QuizzesTab quizzes={quizzes} onRefresh={load} />
      )}
    </div>
  );
}

function SheetsTab({ sheets, onRefresh }: { sheets: Sheet[]; onRefresh: () => void }) {
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [tags, setTags] = useState("");
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setError(null);
    setBusy(true);
    try {
      await api.createSheet(
        title,
        subject || null,
        tags.split(",").map((t) => t.trim()).filter(Boolean),
        { title, summary, key_concepts: [], sections: [], flashcards: [], review_questions: [] },
      );
      setTitle("");
      setSubject("");
      setTags("");
      setSummary("");
      setShowCreate(false);
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Supprimer cette fiche ?")) return;
    await api.deleteSheet(id);
    onRefresh();
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => setShowCreate((s) => !s)} className="btn-primary">
          <Plus size={16} /> Créer une fiche
        </button>
      </div>

      {showCreate && (
        <div className="card space-y-3">
          <input className="input" placeholder="Titre de la fiche" value={title} onChange={(e) => setTitle(e.target.value)} />
          <div className="grid gap-3 sm:grid-cols-2">
            <input className="input" placeholder="Matière" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <input className="input" placeholder="tags (séparés par virgule)" value={tags} onChange={(e) => setTags(e.target.value)} />
          </div>
          <textarea
            className="input min-h-24"
            placeholder="Résumé / contenu de la fiche"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
          {error && <p className="text-sm text-[color:var(--accent-danger)]">{error}</p>}
          <button onClick={create} disabled={busy || !title} className="btn-primary">
            Créer
          </button>
        </div>
      )}

      {sheets.length === 0 ? (
        <div className="card py-10 text-center text-sm text-[color:var(--text-muted)]">
          Aucune fiche. Créez-en une ou enregistrez un cours.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {sheets.map((s) => (
            <div key={s.id} className="card group relative">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <FileText size={16} className="text-[color:var(--accent-primary)]" />
                    <h3 className="font-medium">{s.title || "Fiche"}</h3>
                  </div>
                  {s.subject && (
                    <p className="mt-1 text-xs text-[color:var(--text-secondary)]">{s.subject}</p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-1">
                    {s.tags.map((t) => (
                      <span key={t} className="rounded bg-[color:var(--bg-elevated)] px-1.5 py-0.5 text-[10px]">
                        {t}
                      </span>
                    ))}
                    {s.is_manual && (
                      <span className="rounded bg-[color:var(--accent-secondary)]/15 px-1.5 py-0.5 text-[10px] text-[color:var(--accent-secondary)]">
                        manuelle
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => remove(s.id)}
                  className="rounded-md p-1.5 text-[color:var(--text-muted)] opacity-0 hover:text-[color:var(--accent-danger)] group-hover:opacity-100"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FoldersTab({
  folders,
  sheets,
  onRefresh,
}: {
  folders: ExamFolder[];
  sheets: Sheet[];
  onRefresh: () => void;
}) {
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [examDate, setExamDate] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [folderSheets, setFolderSheets] = useState<Sheet[]>([]);
  const [busy, setBusy] = useState(false);

  async function create() {
    setBusy(true);
    try {
      await api.createFolder(name, examDate ? new Date(examDate).toISOString() : null, "");
      setName("");
      setExamDate("");
      setShowCreate(false);
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function open(folder: ExamFolder) {
    setSelected(folder.id);
    setFolderSheets(await api.folderSheets(folder.id));
  }

  async function addSheet(sheetId: string) {
    if (!selected) return;
    await api.addFolderItem(selected, sheetId);
    setFolderSheets(await api.folderSheets(selected));
    onRefresh();
  }

  async function remove(id: string) {
    if (!window.confirm("Supprimer ce dossier ?")) return;
    await api.deleteFolder(id);
    if (selected === id) setSelected(null);
    onRefresh();
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => setShowCreate((s) => !s)} className="btn-primary">
          <FolderPlus size={16} /> Nouveau dossier
        </button>
      </div>

      {showCreate && (
        <div className="card space-y-3">
          <input className="input" placeholder="Nom du dossier (ex: Examen Droit S1)" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="input" type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
          <button onClick={create} disabled={busy || !name} className="btn-primary">
            Créer
          </button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          {folders.length === 0 ? (
            <div className="card py-8 text-center text-sm text-[color:var(--text-muted)]">
              Aucun dossier.
            </div>
          ) : (
            folders.map((f) => (
              <div
                key={f.id}
                className={`card flex cursor-pointer items-center justify-between ${selected === f.id ? "border-[color:var(--accent-primary)]/40" : ""}`}
                onClick={() => open(f)}
              >
                <div>
                  <h3 className="font-medium">{f.name}</h3>
                  <p className="text-xs text-[color:var(--text-muted)]">
                    {f.item_count} fiche(s)
                    {f.exam_date && ` · examen ${new Date(f.exam_date).toLocaleDateString("fr-FR")}`}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <ChevronRight size={16} className="text-[color:var(--text-muted)]" />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      remove(f.id);
                    }}
                    className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-[color:var(--accent-danger)]"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {selected && (
          <div className="card space-y-3">
            <h3 className="font-display text-lg font-semibold">Fiches du dossier</h3>
            {folderSheets.length === 0 ? (
              <p className="text-sm text-[color:var(--text-muted)]">Aucune fiche dans ce dossier.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {folderSheets.map((s) => (
                  <li key={s.id} className="rounded bg-[color:var(--bg-inset)] px-2 py-1.5">
                    {s.title || "Fiche"}
                  </li>
                ))}
              </ul>
            )}
            <div>
              <p className="mb-1 text-xs uppercase tracking-wider text-[color:var(--text-muted)]">
                Ajouter une fiche
              </p>
              <select
                className="input"
                onChange={(e) => {
                  if (e.target.value) addSheet(e.target.value);
                  e.target.value = "";
                }}
                defaultValue=""
              >
                <option value="">— choisir —</option>
                {sheets
                  .filter((s) => !folderSheets.some((fs) => fs.id === s.id))
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title || "Fiche"}
                    </option>
                  ))}
              </select>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function QuizzesTab({ quizzes, onRefresh }: { quizzes: Quiz[]; onRefresh: () => void }) {
  const [active, setActive] = useState<Quiz | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setError(null);
    setBusy(true);
    try {
      const quiz = await api.generateQuiz(null, [], 10);
      setActive(quiz);
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function open(id: string) {
    setActive(await api.getQuiz(id));
  }

  if (active) {
    return <QuizRunner quiz={active} onExit={() => setActive(null)} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[color:var(--text-secondary)]">
          Générez un quiz aléatoire à partir de vos fiches.
        </p>
        <button onClick={generate} disabled={busy} className="btn-primary">
          <Sparkles size={16} /> {busy ? "Génération…" : "Générer un quiz"}
        </button>
      </div>
      {error && (
        <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
          {error}
        </p>
      )}
      {quizzes.length === 0 ? (
        <div className="card py-10 text-center text-sm text-[color:var(--text-muted)]">
          Aucun quiz. Générez-en un !
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {quizzes.map((q) => (
            <button key={q.id} onClick={() => open(q.id)} className="card text-left hover:border-[color:var(--border-glow)]">
              <h3 className="font-medium">{q.title}</h3>
              <p className="text-xs text-[color:var(--text-muted)]">
                {new Date(q.created_at).toLocaleDateString("fr-FR")}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function QuizRunner({ quiz, onExit }: { quiz: Quiz; onExit: () => void }) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState(false);

  const score = quiz.questions.filter((q) => answers[q.id] === q.correct_index).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl font-bold">{quiz.title}</h2>
        <button onClick={onExit} className="btn-secondary">
          Quitter
        </button>
      </div>

      {submitted && (
        <div className="card text-center">
          <p className="font-display text-2xl font-bold text-[color:var(--accent-primary)]">
            {score} / {quiz.questions.length}
          </p>
          <p className="text-sm text-[color:var(--text-secondary)]">Score</p>
        </div>
      )}

      {quiz.questions.map((q, i) => (
        <div key={q.id} className="card space-y-2">
          <p className="font-medium">
            {i + 1}. {q.question}
          </p>
          <div className="space-y-1">
            {q.choices.map((c, ci) => {
              const chosen = answers[q.id] === ci;
              const isCorrect = ci === q.correct_index;
              let cls = "border-[color:var(--border-subtle)]";
              if (submitted && isCorrect) cls = "border-[color:var(--accent-success)] bg-[color:var(--accent-success)]/10";
              else if (submitted && chosen && !isCorrect) cls = "border-[color:var(--accent-danger)] bg-[color:var(--accent-danger)]/10";
              else if (chosen) cls = "border-[color:var(--accent-primary)]";
              return (
                <button
                  key={ci}
                  disabled={submitted}
                  onClick={() => setAnswers((a) => ({ ...a, [q.id]: ci }))}
                  className={`block w-full rounded-md border px-3 py-2 text-left text-sm ${cls}`}
                >
                  {c}
                </button>
              );
            })}
          </div>
          {submitted && q.explanation && (
            <p className="text-xs text-[color:var(--text-secondary)]">💡 {q.explanation}</p>
          )}
        </div>
      ))}

      {!submitted && (
        <button
          onClick={() => setSubmitted(true)}
          disabled={Object.keys(answers).length < quiz.questions.length}
          className="btn-primary w-full"
        >
          Valider mes réponses
        </button>
      )}
    </div>
  );
}
