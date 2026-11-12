import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FileText, Clock, Trash2, Monitor, Search, Pencil, X } from "lucide-react";
import { api } from "../lib/api";
import type { Course, CourseStatus } from "../lib/types";

const statusMeta: Record<CourseStatus, { label: string; color: string }> = {
  recording: { label: "Enregistrement", color: "var(--accent-danger)" },
  transcribing: { label: "Transcription", color: "var(--accent-primary)" },
  generating: { label: "Génération", color: "var(--accent-secondary)" },
  ready: { label: "Prêt", color: "var(--accent-success)" },
  failed: { label: "Échec", color: "var(--accent-danger)" },
};

export default function DashboardPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [editing, setEditing] = useState<Course | null>(null);

  async function load() {
    setLoading(true);
    try {
      setCourses(await api.listCourses());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function remove(id: string) {
    if (!window.confirm("Supprimer ce cours ?")) return;
    await api.deleteCourse(id);
    setCourses((c) => c.filter((x) => x.id !== id));
  }

  const subjects = useMemo(
    () => Array.from(new Set(courses.map((c) => c.subject).filter(Boolean))) as string[],
    [courses],
  );
  const allTags = useMemo(
    () => Array.from(new Set(courses.flatMap((c) => c.tags ?? []))).sort(),
    [courses],
  );

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return courses.filter((c) => {
      if (q && !c.title.toLowerCase().includes(q) && !(c.subject ?? "").toLowerCase().includes(q))
        return false;
      if (subjectFilter && c.subject !== subjectFilter) return false;
      if (tagFilter && !(c.tags ?? []).includes(tagFilter)) return false;
      return true;
    });
  }, [courses, search, subjectFilter, tagFilter]);

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold">Mes cours</h1>
          <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
            Vos enregistrements et fiches de révision.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-md bg-[color:var(--bg-surface)] px-3 py-2 text-xs text-[color:var(--text-secondary)]">
          <Monitor size={14} />
          Enregistrez depuis l'app desktop
        </div>
      </div>

      {/* Filtres */}
      <div className="mb-6 grid gap-3 sm:grid-cols-[2fr_1fr_1fr]">
        <div className="relative">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--text-muted)]"
          />
          <input
            className="input pl-9"
            placeholder="Rechercher un cours…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="input" value={subjectFilter} onChange={(e) => setSubjectFilter(e.target.value)}>
          <option value="">Toutes les matières</option>
          {subjects.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select className="input" value={tagFilter} onChange={(e) => setTagFilter(e.target.value)}>
          <option value="">Tous les tags</option>
          {allTags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="text-sm text-[color:var(--text-muted)]">Chargement…</p>
      ) : filtered.length === 0 ? (
        <div className="card flex flex-col items-center gap-3 py-16 text-center">
          <FileText size={40} className="text-[color:var(--text-muted)]" />
          <p className="text-[color:var(--text-secondary)]">
            {courses.length === 0 ? "Aucun cours pour l'instant." : "Aucun cours ne correspond aux filtres."}
          </p>
          {courses.length === 0 && (
            <p className="max-w-sm text-sm text-[color:var(--text-muted)]">
              Lancez un enregistrement depuis l'application desktop : vos cours et fiches
              apparaîtront ici automatiquement.
            </p>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {filtered.map((course) => {
            const meta = statusMeta[course.status] ?? statusMeta.recording;
            return (
              <div key={course.id} className="card group relative">
                <div
                  className="absolute left-0 top-0 h-full w-1 rounded-l-lg"
                  style={{ background: meta.color }}
                />
                <div className="flex items-start justify-between pl-2">
                  <Link to={`/courses/${course.id}`} className="flex-1">
                    <h3 className="font-display text-lg font-semibold group-hover:text-[color:var(--accent-primary)]">
                      {course.title}
                    </h3>
                    {course.subject && (
                      <p className="text-sm text-[color:var(--text-secondary)]">{course.subject}</p>
                    )}
                    {(course.tags ?? []).length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {course.tags.map((t) => (
                          <span
                            key={t}
                            className="rounded bg-[color:var(--bg-elevated)] px-1.5 py-0.5 text-[10px] text-[color:var(--text-secondary)]"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="mt-3 flex items-center gap-4 text-xs text-[color:var(--text-muted)]">
                      <span className="flex items-center gap-1">
                        <Clock size={13} />
                        {Math.round(course.duration_sec / 60)} min
                      </span>
                      <span className="flex items-center gap-1.5" style={{ color: meta.color }}>
                        <span className="h-1.5 w-1.5 rounded-full" style={{ background: meta.color }} />
                        {meta.label}
                      </span>
                    </div>
                  </Link>
                  <div className="flex flex-col gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      onClick={() => setEditing(course)}
                      className="rounded-md p-2 text-[color:var(--text-muted)] hover:text-[color:var(--accent-primary)]"
                      aria-label="Éditer"
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      onClick={() => remove(course.id)}
                      className="rounded-md p-2 text-[color:var(--text-muted)] hover:text-[color:var(--accent-danger)]"
                      aria-label="Supprimer"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {editing && (
        <EditCourseModal
          course={editing}
          onClose={() => setEditing(null)}
          onSaved={(updated) => {
            setCourses((list) => list.map((c) => (c.id === updated.id ? updated : c)));
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}

function EditCourseModal({
  course,
  onClose,
  onSaved,
}: {
  course: Course;
  onClose: () => void;
  onSaved: (c: Course) => void;
}) {
  const [title, setTitle] = useState(course.title);
  const [subject, setSubject] = useState(course.subject ?? "");
  const [tags, setTags] = useState((course.tags ?? []).join(", "));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setError(null);
    setBusy(true);
    try {
      const updated = await api.updateCourse(course.id, {
        title,
        subject: subject || null,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      onSaved(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="card w-full max-w-md space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold">Éditer le cours</h2>
          <button onClick={onClose} className="text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]">
            <X size={18} />
          </button>
        </div>
        <div>
          <label className="label">Titre</label>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <label className="label">Matière</label>
          <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div>
          <label className="label">Tags (séparés par virgule)</label>
          <input className="input" value={tags} onChange={(e) => setTags(e.target.value)} />
        </div>
        {error && <p className="text-sm text-[color:var(--accent-danger)]">{error}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">
            Annuler
          </button>
          <button onClick={save} disabled={busy || !title} className="btn-primary">
            Enregistrer
          </button>
        </div>
      </div>
    </div>
  );
}
