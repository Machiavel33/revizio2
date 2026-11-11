import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import type { CourseDetail } from "../lib/types";
import StudySheetView from "../components/StudySheetView";

export default function CoursePage() {
  const { id } = useParams<{ id: string }>();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!id) return;
    try {
      setCourse(await api.getCourse(id));
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    void load();
  }, [id]);

  // Polling tant que le traitement est en cours
  useEffect(() => {
    if (!course) return;
    const pending = ["transcribing", "generating", "recording"].includes(course.status);
    if (!pending) return;
    const t = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(t);
  }, [course?.status]);

  if (error) {
    return (
      <div className="p-8">
        <p className="text-[color:var(--accent-danger)]">{error}</p>
      </div>
    );
  }

  if (!course) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="animate-spin text-[color:var(--accent-primary)]" />
      </div>
    );
  }

  const processing = ["transcribing", "generating", "recording"].includes(course.status);

  return (
    <div className="mx-auto max-w-4xl p-8">
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-2 text-sm text-[color:var(--text-secondary)] hover:text-[color:var(--accent-primary)]"
      >
        <ArrowLeft size={16} />
        Retour aux cours
      </Link>

      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold">{course.title}</h1>
        {course.subject && (
          <p className="mt-1 text-sm text-[color:var(--text-secondary)]">{course.subject}</p>
        )}
      </div>

      {processing && (
        <div className="card flex items-center gap-3 py-8">
          <RefreshCw size={20} className="animate-spin text-[color:var(--accent-primary)]" />
          <div>
            <p className="font-medium">
              {course.status === "transcribing"
                ? "Transcription en cours…"
                : "Génération de la fiche de révision…"}
            </p>
            <p className="text-sm text-[color:var(--text-secondary)]">
              Cela peut prendre quelques minutes selon la durée du cours.
            </p>
          </div>
        </div>
      )}

      {course.status === "failed" && (
        <div className="card border-[color:var(--accent-danger)]/30 py-6">
          <p className="font-medium text-[color:var(--accent-danger)]">
            Le traitement a échoué.
          </p>
          <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
            Vérifiez que vos clés API (BYOK) sont configurées dans les réglages.
          </p>
        </div>
      )}

      {course.study_sheet && <StudySheetView sheet={course.study_sheet} />}

      {course.transcript && (
        <details className="card mt-6">
          <summary className="cursor-pointer text-sm font-medium text-[color:var(--text-secondary)]">
            Transcription complète
          </summary>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-[color:var(--text-secondary)]">
            {course.transcript.full_text}
          </p>
        </details>
      )}
    </div>
  );
}
