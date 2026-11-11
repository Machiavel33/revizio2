import { useEffect, useState } from "react";
import {
  Users,
  BookOpen,
  Activity,
  AlertTriangle,
  Loader2,
  ShieldCheck,
  ShieldOff,
} from "lucide-react";
import { api } from "../../lib/api";
import type { AdminJob, AdminStats, AdminUser } from "../../lib/types";

type Tab = "stats" | "users" | "jobs";

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("stats");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [s, u, j] = await Promise.all([
        api.adminStats(),
        api.adminUsers(),
        api.adminJobs(),
      ]);
      setStats(s);
      setUsers(u);
      setJobs(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function toggleActive(u: AdminUser) {
    const updated = await api.adminSetUserActive(u.id, !u.is_active);
    setUsers((list) => list.map((x) => (x.id === u.id ? updated : x)));
  }

  return (
    <div className="mx-auto max-w-6xl p-8">
      <div className="mb-6 flex items-center gap-2">
        <ShieldCheck size={22} className="text-[color:var(--accent-primary)]" />
        <h1 className="font-display text-3xl font-bold">Administration</h1>
      </div>

      <div className="mb-6 flex gap-2">
        {(["stats", "users", "jobs"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t
                ? "bg-[color:var(--bg-elevated)] text-[color:var(--accent-primary)]"
                : "text-[color:var(--text-secondary)] hover:bg-[color:var(--bg-elevated)]"
            }`}
          >
            {t === "stats" ? "Statistiques" : t === "users" ? "Utilisateurs" : "Jobs"}
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
      ) : tab === "stats" && stats ? (
        <StatsTab stats={stats} />
      ) : tab === "users" ? (
        <UsersTab users={users} onToggle={toggleActive} />
      ) : (
        <JobsTab jobs={jobs} />
      )}
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: typeof Users;
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="card">
      <div className="flex items-center gap-2" style={{ color }}>
        <Icon size={18} />
        <span className="text-xs uppercase tracking-wider text-[color:var(--text-secondary)]">
          {label}
        </span>
      </div>
      <p className="mt-2 font-display text-3xl font-bold">{value}</p>
    </div>
  );
}

function StatsTab({ stats }: { stats: AdminStats }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard icon={Users} label="Utilisateurs" value={stats.total_users} color="var(--accent-primary)" />
      <StatCard icon={Activity} label="Actifs" value={stats.active_users} color="var(--accent-success)" />
      <StatCard icon={BookOpen} label="Cours" value={stats.total_courses} color="var(--accent-secondary)" />
      <StatCard icon={BookOpen} label="Fiches prêtes" value={stats.ready_courses} color="var(--accent-success)" />
      <StatCard icon={AlertTriangle} label="Cours en échec" value={stats.failed_courses} color="var(--accent-danger)" />
      <StatCard icon={Activity} label="Jobs en file" value={stats.queued_jobs} color="var(--accent-warning)" />
      <StatCard icon={Activity} label="Jobs en cours" value={stats.running_jobs} color="var(--accent-primary)" />
      <StatCard icon={AlertTriangle} label="Jobs en échec" value={stats.failed_jobs} color="var(--accent-danger)" />
    </div>
  );
}

function UsersTab({
  users,
  onToggle,
}: {
  users: AdminUser[];
  onToggle: (u: AdminUser) => void;
}) {
  return (
    <div className="card overflow-x-auto p-0">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[color:var(--border-subtle)] text-left text-xs uppercase tracking-wider text-[color:var(--text-muted)]">
            <th className="px-4 py-3">Email</th>
            <th className="px-4 py-3">Nom</th>
            <th className="px-4 py-3">Rôle</th>
            <th className="px-4 py-3">Cours</th>
            <th className="px-4 py-3">Statut</th>
            <th className="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b border-[color:var(--border-subtle)]/50">
              <td className="px-4 py-3 font-mono text-xs">{u.email}</td>
              <td className="px-4 py-3">{u.display_name}</td>
              <td className="px-4 py-3">
                <span
                  className={`rounded px-2 py-0.5 text-xs ${
                    u.role === "admin"
                      ? "bg-[color:var(--accent-secondary)]/15 text-[color:var(--accent-secondary)]"
                      : "bg-[color:var(--bg-elevated)] text-[color:var(--text-secondary)]"
                  }`}
                >
                  {u.role}
                </span>
              </td>
              <td className="px-4 py-3">{u.course_count}</td>
              <td className="px-4 py-3">
                <span
                  className={
                    u.is_active
                      ? "text-[color:var(--accent-success)]"
                      : "text-[color:var(--accent-danger)]"
                  }
                >
                  {u.is_active ? "actif" : "désactivé"}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => onToggle(u)}
                  className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-[color:var(--accent-primary)]"
                  aria-label="Basculer le statut"
                >
                  {u.is_active ? <ShieldOff size={16} /> : <ShieldCheck size={16} />}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function JobsTab({ jobs }: { jobs: AdminJob[] }) {
  const statusColor: Record<string, string> = {
    queued: "var(--accent-warning)",
    running: "var(--accent-primary)",
    done: "var(--accent-success)",
    failed: "var(--accent-danger)",
  };
  return (
    <div className="card overflow-x-auto p-0">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[color:var(--border-subtle)] text-left text-xs uppercase tracking-wider text-[color:var(--text-muted)]">
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Cours</th>
            <th className="px-4 py-3">Utilisateur</th>
            <th className="px-4 py-3">Statut</th>
            <th className="px-4 py-3">Erreur</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} className="border-b border-[color:var(--border-subtle)]/50">
              <td className="px-4 py-3">{j.type}</td>
              <td className="px-4 py-3">{j.course_title}</td>
              <td className="px-4 py-3 font-mono text-xs">{j.user_email}</td>
              <td className="px-4 py-3">
                <span style={{ color: statusColor[j.status] ?? "var(--text-secondary)" }}>
                  {j.status}
                </span>
              </td>
              <td className="max-w-xs truncate px-4 py-3 text-xs text-[color:var(--text-muted)]">
                {j.error ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
