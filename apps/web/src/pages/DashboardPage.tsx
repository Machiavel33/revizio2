import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileText, Clock, Trash2, Monitor } from "lucide-react";
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
    await api.deleteCourse(id);
    setCourses((c) => c.filter((x) => x.id !== id));
  }

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold">Mes cours</h1>
          <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
            Vos enregistrements et fiches de révision.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-md bg-[color:var(--bg-surface)] px-3 py-2 text-xs text-[color:var(--text-secondary)]">
          <Monitor size={14} />
          Enregistrez depuis l'app desktop Revizio
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-[color:var(--text-muted)]">Chargement…</p>
      ) : courses.length === 0 ? (
        <div className="card flex flex-col items-center gap-3 py-16 text-center">
          <FileText size={40} className="text-[color:var(--text-muted)]" />
          <p className="text-[color:var(--text-secondary)]">Aucun cours pour l'instant.</p>
          <p className="max-w-sm text-sm text-[color:var(--text-muted)]">
            Lancez un enregistrement depuis l'application desktop : vos cours et fiches
            apparaîtront ici automatiquement.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {courses.map((course) => {
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
                    <div className="mt-3 flex items-center gap-4 text-xs text-[color:var(--text-muted)]">
                      <span className="flex items-center gap-1">
                        <Clock size={13} />
                        {Math.round(course.duration_sec / 60)} min
                      </span>
                      <span className="flex items-center gap-1.5" style={{ color: meta.color }}>
                        <span
                          className="h-1.5 w-1.5 rounded-full"
                          style={{ background: meta.color }}
                        />
                        {meta.label}
                      </span>
                    </div>
                  </Link>
                  <button
                    onClick={() => remove(course.id)}
                    className="rounded-md p-2 text-[color:var(--text-muted)] opacity-0 transition-opacity hover:text-[color:var(--accent-danger)] group-hover:opacity-100"
                    aria-label="Supprimer"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
