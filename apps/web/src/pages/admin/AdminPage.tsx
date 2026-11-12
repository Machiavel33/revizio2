import { useEffect, useState } from "react";
import {
  Users,
  BookOpen,
  Activity,
  AlertTriangle,
  Loader2,
  ShieldCheck,
  ShieldOff,
  KeyRound,
  Trash2,
  Plus,
  Mail,
} from "lucide-react";
import { api } from "../../lib/api";
import type {
  AdminJob,
  AdminStats,
  AdminUser,
  Alert,
  EmailLog,
  OnlineInfo,
  PlatformKey,
  SmtpConfig,
  SystemInfo,
  UserUsage,
} from "../../lib/types";

type Tab =
  | "stats"
  | "users"
  | "platform"
  | "alerts"
  | "usage"
  | "emails"
  | "system"
  | "online"
  | "jobs";

const PROVIDERS = [
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Anthropic" },
  { id: "deepgram", label: "Deepgram" },
];

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("stats");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [platformKeys, setPlatformKeys] = useState<PlatformKey[]>([]);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [online, setOnline] = useState<OnlineInfo | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [usage, setUsage] = useState<UserUsage[]>([]);
  const [emailLogs, setEmailLogs] = useState<EmailLog[]>([]);
  const [smtp, setSmtp] = useState<SmtpConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [s, u, j, pk, sys, on, al, us, el, sm] = await Promise.all([
        api.adminStats(),
        api.adminUsers(),
        api.adminJobs(),
        api.adminPlatformKeys(),
        api.adminSystem(),
        api.adminOnline(),
        api.adminAlerts(),
        api.adminUsage(),
        api.adminEmailLogs(),
        api.adminEmailConfig(),
      ]);
      setStats(s);
      setUsers(u);
      setJobs(j);
      setPlatformKeys(pk);
      setAlerts(al);
      setUsage(us);
      setSystem(sys);
      setOnline(on);
      setEmailLogs(el);
      setSmtp(sm);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function markRead(id: string) {
    await api.adminMarkAlertRead(id);
    setAlerts((list) => list.map((a) => (a.id === id ? { ...a, is_read: true } : a)));
  }

  async function deleteAlert(id: string) {
    await api.adminDeleteAlert(id);
    setAlerts((list) => list.filter((a) => a.id !== id));
  }

  useEffect(() => {
    void load();
  }, []);

  // Rafraîchissement live (système + présence) toutes les 5s
  useEffect(() => {
    const t = window.setInterval(async () => {
      try {
        const [sys, on] = await Promise.all([api.adminSystem(), api.adminOnline()]);
        setSystem(sys);
        setOnline(on);
      } catch {
        /* ignore */
      }
    }, 5000);
    return () => window.clearInterval(t);
  }, []);

  async function updateUser(u: AdminUser, patch: { is_active?: boolean; key_mode?: string }) {
    const updated = await api.adminUpdateUser(u.id, patch);
    setUsers((list) => list.map((x) => (x.id === u.id ? updated : x)));
  }

  return (
    <div className="mx-auto max-w-6xl p-8">
      <div className="mb-6 flex items-center gap-2">
        <ShieldCheck size={22} className="text-[color:var(--accent-primary)]" />
        <h1 className="font-display text-3xl font-bold">Administration</h1>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        {(
          [
            "stats",
            "users",
            "platform",
            "alerts",
            "usage",
            "emails",
            "system",
            "online",
            "jobs",
          ] as Tab[]
        ).map((t) => {
          const unread = alerts.filter((a) => !a.is_read).length;
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                tab === t
                  ? "bg-[color:var(--bg-elevated)] text-[color:var(--accent-primary)]"
                  : "text-[color:var(--text-secondary)] hover:bg-[color:var(--bg-elevated)]"
              }`}
            >
              {t === "stats"
                ? "Statistiques"
                : t === "users"
                  ? "Utilisateurs"
                  : t === "platform"
                    ? "Clés plateforme"
                    : t === "alerts"
                      ? `Alertes${unread ? ` (${unread})` : ""}`
                      : t === "usage"
                        ? "Quotas & usage"
                        : t === "emails"
                          ? "Emails"
                          : t === "system"
                            ? "Système"
                            : t === "online"
                              ? `En ligne${online ? ` (${online.count})` : ""}`
                              : "Jobs"}
            </button>
          );
        })}
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
        <UsersTab users={users} onUpdate={updateUser} onRefresh={load} />
      ) : tab === "platform" ? (
        <PlatformKeysTab keys={platformKeys} onChange={load} />
      ) : tab === "alerts" ? (
        <AlertsTab alerts={alerts} onRead={markRead} onDelete={deleteAlert} />
      ) : tab === "usage" ? (
        <UsageTab usage={usage} />
      ) : tab === "emails" ? (
        <EmailsTab smtp={smtp} logs={emailLogs} onRefresh={load} />
      ) : tab === "system" ? (
        <SystemTab system={system} />
      ) : tab === "online" ? (
        <OnlineTab online={online} />
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

function ProviderBadges({ providers, color }: { providers: string[]; color: string }) {
  if (providers.length === 0) return <span className="text-xs text-[color:var(--text-muted)]">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {providers.map((p) => (
        <span
          key={p}
          className="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase"
          style={{ background: `${color}22`, color }}
        >
          {p}
        </span>
      ))}
    </div>
  );
}

function UsersTab({
  users,
  onUpdate,
  onRefresh,
}: {
  users: AdminUser[];
  onUpdate: (u: AdminUser, patch: { is_active?: boolean; key_mode?: string }) => void;
  onRefresh: () => void;
}) {
  const [showCreate, setShowCreate] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [role, setRole] = useState("student");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setError(null);
    setBusy(true);
    try {
      await api.adminCreateUser(email, password, firstName, lastName, role);
      setEmail("");
      setPassword("");
      setFirstName("");
      setLastName("");
      setRole("student");
      setShowCreate(false);
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function changeRole(u: AdminUser, newRole: string) {
    await api.adminSetRole(u.id, newRole);
    onRefresh();
  }

  async function remove(u: AdminUser) {
    if (!window.confirm(`Supprimer définitivement ${u.email} ?`)) return;
    try {
      await api.adminDeleteUser(u.id);
      onRefresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  async function forceReset(u: AdminUser) {
    try {
      await api.adminForceReset(u.id);
      alert(`Lien de réinitialisation envoyé à ${u.email}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => setShowCreate((s) => !s)} className="btn-primary">
          <Plus size={16} /> Créer un utilisateur
        </button>
      </div>

      {showCreate && (
        <div className="card space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              className="input"
              placeholder="email@exemple.fr"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <input
              className="input"
              type="password"
              placeholder="mot de passe (min 8)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <input
              className="input"
              placeholder="prénom"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
            />
            <input
              className="input"
              placeholder="nom"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
            />
            <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="student">Élève (student)</option>
              <option value="admin">Administrateur</option>
            </select>
          </div>
          {error && (
            <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
              {error}
            </p>
          )}
          <button
            onClick={create}
            disabled={busy || !email || password.length < 8}
            className="btn-primary"
          >
            Créer
          </button>
        </div>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[color:var(--border-subtle)] text-left text-xs uppercase tracking-wider text-[color:var(--text-muted)]">
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Rôle</th>
              <th className="px-4 py-3">Cours</th>
              <th className="px-4 py-3">Mode clé IA</th>
              <th className="px-4 py-3">BYOK</th>
              <th className="px-4 py-3">Statut</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-[color:var(--border-subtle)]/50">
                <td className="px-4 py-3">
                  <div className="font-mono text-xs">{u.email}</div>
                  <div className="text-xs text-[color:var(--text-muted)]">{u.display_name}</div>
                </td>
                <td className="px-4 py-3">
                  <select
                    value={u.role}
                    onChange={(e) => changeRole(u, e.target.value)}
                    className="rounded-md bg-[color:var(--bg-inset)] px-2 py-1 text-xs"
                  >
                    <option value="student">student</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td className="px-4 py-3">{u.course_count}</td>
                <td className="px-4 py-3">
                  <select
                    value={u.key_mode}
                    onChange={(e) => onUpdate(u, { key_mode: e.target.value })}
                    className="rounded-md bg-[color:var(--bg-inset)] px-2 py-1 text-xs"
                  >
                    <option value="byok">BYOK</option>
                    <option value="platform">Plateforme</option>
                  </select>
                </td>
                <td className="px-4 py-3">
                  <ProviderBadges providers={u.byok_providers} color="var(--accent-primary)" />
                </td>
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
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => onUpdate(u, { is_active: !u.is_active })}
                      className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-[color:var(--accent-primary)]"
                      title={u.is_active ? "Désactiver" : "Activer"}
                    >
                      {u.is_active ? <ShieldOff size={16} /> : <ShieldCheck size={16} />}
                    </button>
                    <button
                      onClick={() => forceReset(u)}
                      className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-[color:var(--accent-warning)]"
                      title="Forcer réinitialisation mot de passe"
                    >
                      <KeyRound size={16} />
                    </button>
                    <button
                      onClick={() => remove(u)}
                      className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-[color:var(--accent-danger)]"
                      title="Supprimer"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
function PlatformKeysTab({ keys, onChange }: { keys: PlatformKey[]; onChange: () => void }) {
  const [provider, setProvider] = useState("openai");
  const [value, setValue] = useState("");
  const [account, setAccount] = useState("");
  const [accounts, setAccounts] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.adminPlatformAccounts().then(setAccounts).catch(() => {});
  }, [keys]);

  async function add() {
    setError(null);
    setBusy(true);
    try {
      await api.adminCreatePlatformKeyFull(provider, value, account);
      setValue("");
      setAccount("");
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await api.adminDeletePlatformKey(id);
    onChange();
  }

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <div className="flex items-center gap-2 text-[color:var(--accent-primary)]">
          <KeyRound size={18} />
          <h2 className="font-display text-lg font-semibold">Clés API de la plateforme</h2>
        </div>
        <p className="text-sm text-[color:var(--text-secondary)]">
          Ces clés sont utilisées par les utilisateurs en mode « Plateforme ». Chiffrées
          AES-256-GCM, jamais affichées en clair.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <select className="input" value={provider} onChange={(e) => setProvider(e.target.value)}>
            {PROVIDERS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
          <input
            className="input"
            list="platform-accounts"
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            placeholder="compte associé (ex: compte OpenAI école)"
          />
          <datalist id="platform-accounts">
            {accounts.map((a) => (
              <option key={a} value={a} />
            ))}
          </datalist>
          <input
            className="input sm:col-span-2"
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="clé API"
          />
          <button
            onClick={add}
            disabled={busy || !value}
            className="btn-primary sm:col-span-2"
          >
            <Plus size={16} />
            Ajouter
          </button>
        </div>
        {error && (
          <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-3 py-2 text-sm text-[color:var(--accent-danger)]">
            {error}
          </p>
        )}
      </div>

      <div className="card space-y-2">
        {keys.length === 0 ? (
          <p className="text-sm text-[color:var(--text-muted)]">Aucune clé plateforme configurée.</p>
        ) : (
          keys.map((k) => (
            <div
              key={k.id}
              className="flex items-center justify-between rounded-md bg-[color:var(--bg-inset)] px-3 py-2.5"
            >
              <div className="flex items-center gap-3">
                <span className="rounded bg-[color:var(--bg-elevated)] px-2 py-0.5 text-xs font-medium uppercase text-[color:var(--accent-primary)]">
                  {k.provider}
                </span>
                {k.account_label && (
                  <span className="text-xs text-[color:var(--text-secondary)]">
                    {k.account_label}
                  </span>
                )}
                <span className="font-mono text-sm text-[color:var(--text-muted)]">
                  {k.key_hint}
                </span>
                <span className="text-xs text-[color:var(--accent-success)]">active</span>
              </div>
              <button
                onClick={() => remove(k.id)}
                className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-[color:var(--accent-danger)]"
                aria-label="Supprimer"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))
        )}
      </div>
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

function fmtUptime(sec: number): string {
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (d > 0) return `${d}j ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function SystemTab({ system }: { system: SystemInfo | null }) {
  if (!system) return <p className="text-sm text-[color:var(--text-muted)]">Chargement…</p>;
  const a = system.app;
  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="mb-3 font-display text-lg font-semibold">Application</h2>
        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wider text-[color:var(--text-muted)]">Nom</dt>
            <dd className="font-medium">{a.name}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-[color:var(--text-muted)]">Version</dt>
            <dd className="font-mono text-[color:var(--accent-primary)]">v{a.version}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-[color:var(--text-muted)]">Environnement</dt>
            <dd>{a.environment}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-[color:var(--text-muted)]">Uptime</dt>
            <dd>{fmtUptime(a.uptime_seconds)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-[color:var(--text-muted)]">Python</dt>
            <dd className="font-mono text-xs">{a.python}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-[color:var(--text-muted)]">Plateforme</dt>
            <dd className="font-mono text-xs">{a.platform}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-[color:var(--text-muted)]">Stockage</dt>
            <dd>{system.storage_backend}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-[color:var(--text-muted)]">Rate-limit</dt>
            <dd>
              {system.rate_limit.enabled ? `actif (${system.rate_limit.backend})` : "désactivé"}
            </dd>
          </div>
        </dl>
      </div>

      <div className="card">
        <h2 className="mb-3 font-display text-lg font-semibold">Services</h2>
        <div className="space-y-2">
          {system.services.map((s) => (
            <div
              key={s.name}
              className="flex items-center justify-between rounded-md bg-[color:var(--bg-inset)] px-3 py-2.5"
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{
                    background:
                      s.status === "up" ? "var(--accent-success)" : "var(--accent-danger)",
                  }}
                />
                <span className="font-medium">{s.name}</span>
              </div>
              <div className="flex items-center gap-3 text-xs">
                {s.workers && s.workers.length > 0 && (
                  <span className="text-[color:var(--text-muted)]">
                    {s.workers.length} worker(s)
                  </span>
                )}
                <span
                  style={{
                    color:
                      s.status === "up" ? "var(--accent-success)" : "var(--accent-danger)",
                  }}
                >
                  {s.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function OnlineTab({ online }: { online: OnlineInfo | null }) {
  if (!online) return <p className="text-sm text-[color:var(--text-muted)]">Chargement…</p>;
  return (
    <div className="space-y-4">
      <div className="card flex items-center gap-3">
        <span className="h-3 w-3 animate-pulse rounded-full bg-[color:var(--accent-success)]" />
        <span className="font-display text-2xl font-bold">{online.count}</span>
        <span className="text-sm text-[color:var(--text-secondary)]">
          utilisateur(s) en ligne (live, rafraîchi toutes les 5s)
        </span>
      </div>

      <div className="card overflow-x-auto p-0">
        {online.users.length === 0 ? (
          <p className="p-4 text-sm text-[color:var(--text-muted)]">Personne en ligne.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[color:var(--border-subtle)] text-left text-xs uppercase tracking-wider text-[color:var(--text-muted)]">
                <th className="px-4 py-3">Utilisateur</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Dernière activité</th>
              </tr>
            </thead>
            <tbody>
              {online.users.map((u) => (
                <tr key={u.user_id} className="border-b border-[color:var(--border-subtle)]/50">
                  <td className="px-4 py-3 font-medium">{u.display_name || "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{u.email}</td>
                  <td className="px-4 py-3 text-xs text-[color:var(--text-secondary)]">
                    il y a {u.idle_seconds}s
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function AlertsTab({
  alerts,
  onRead,
  onDelete,
}: {
  alerts: Alert[];
  onRead: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const sevColor: Record<string, string> = {
    info: "var(--accent-primary)",
    warning: "var(--accent-warning)",
    critical: "var(--accent-danger)",
  };
  if (alerts.length === 0) {
    return (
      <div className="card py-10 text-center text-sm text-[color:var(--text-muted)]">
        Aucune alerte.
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {alerts.map((a) => (
        <div key={a.id} className={`card flex items-start gap-3 ${a.is_read ? "opacity-60" : ""}`}>
          <span
            className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ background: sevColor[a.severity] ?? "var(--text-muted)" }}
          />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{a.title}</span>
              <span
                className="rounded px-1.5 py-0.5 text-[10px] uppercase"
                style={{ background: `${sevColor[a.severity]}22`, color: sevColor[a.severity] }}
              >
                {a.category}
              </span>
            </div>
            {a.message && (
              <p className="mt-1 text-sm text-[color:var(--text-secondary)]">{a.message}</p>
            )}
            <p className="mt-1 text-xs text-[color:var(--text-muted)]">
              {new Date(a.created_at).toLocaleString("fr-FR")}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            {!a.is_read && (
              <button
                onClick={() => onRead(a.id)}
                className="rounded-md px-2 py-1 text-xs text-[color:var(--text-secondary)] hover:text-[color:var(--accent-primary)]"
              >
                Marquer lu
              </button>
            )}
            <button
              onClick={() => onDelete(a.id)}
              className="rounded-md px-2 py-1 text-xs text-[color:var(--text-muted)] hover:text-[color:var(--accent-danger)]"
            >
              Supprimer
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function UsageTab({ usage }: { usage: UserUsage[] }) {
  return (
    <div className="card overflow-x-auto p-0">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[color:var(--border-subtle)] text-left text-xs uppercase tracking-wider text-[color:var(--text-muted)]">
            <th className="px-4 py-3">Utilisateur</th>
            <th className="px-4 py-3">Mode</th>
            <th className="px-4 py-3">Audio (min)</th>
            <th className="px-4 py-3">Fiches</th>
            <th className="px-4 py-3">Coût est. (USD)</th>
            <th className="px-4 py-3">Signaux</th>
          </tr>
        </thead>
        <tbody>
          {usage.map((u) => {
            const audioRatio = u.audio_minutes / Math.max(u.quota_audio_minutes, 1);
            const sheetRatio = u.sheet_count / Math.max(u.quota_sheet_count, 1);
            const ratio = Math.max(audioRatio, sheetRatio);
            const barColor =
              ratio >= 1
                ? "var(--accent-danger)"
                : ratio >= 0.8
                  ? "var(--accent-warning)"
                  : "var(--accent-success)";
            return (
              <tr key={u.user_id} className="border-b border-[color:var(--border-subtle)]/50">
                <td className="px-4 py-3 font-mono text-xs">{u.email}</td>
                <td className="px-4 py-3">
                  <span className="rounded bg-[color:var(--bg-elevated)] px-2 py-0.5 text-xs">
                    {u.key_mode}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="w-16 text-xs">
                      {u.audio_minutes}/{u.quota_audio_minutes}
                    </span>
                    <div className="h-1.5 w-20 overflow-hidden rounded-full bg-[color:var(--bg-inset)]">
                      <div
                        className="h-full"
                        style={{
                          width: `${Math.min(audioRatio * 100, 100)}%`,
                          background: barColor,
                        }}
                      />
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs">
                  {u.sheet_count}/{u.quota_sheet_count}
                </td>
                <td className="px-4 py-3 font-mono text-xs">${u.cost_usd.toFixed(4)}</td>
                <td className="px-4 py-3">
                  {u.abuse_flags.length > 0 ? (
                    <span
                      className="rounded px-1.5 py-0.5 text-[10px] uppercase"
                      style={{ background: "var(--accent-danger)22", color: "var(--accent-danger)" }}
                      title={u.abuse_flags.join("; ")}
                    >
                      ⚠ {u.abuse_flags.length} signal(aux)
                    </span>
                  ) : (
                    <span className="text-xs text-[color:var(--text-muted)]">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function EmailsTab({
  smtp,
  logs,
  onRefresh,
}: {
  smtp: SmtpConfig | null;
  logs: EmailLog[];
  onRefresh: () => void;
}) {
  const [host, setHost] = useState(smtp?.host ?? "");
  const [port, setPort] = useState(String(smtp?.port ?? 587));
  const [user, setUser] = useState(smtp?.user ?? "");
  const [password, setPassword] = useState("");
  const [useTls, setUseTls] = useState(smtp?.use_tls ?? true);
  const [fromAddr, setFromAddr] = useState(smtp?.from_addr ?? "");
  const [testTo, setTestTo] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      await api.adminSetEmailConfig({
        host,
        port: Number(port),
        user,
        password,
        use_tls: useTls,
        from_addr: fromAddr,
      });
      setMsg("Configuration enregistrée.");
      onRefresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.adminTestEmail(testTo);
      setMsg(res.sent ? "Email de test envoyé." : "Échec de l'envoi (voir logs).");
      onRefresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <div className="flex items-center gap-2 text-[color:var(--accent-primary)]">
          <Mail size={18} />
          <h2 className="font-display text-lg font-semibold">Configuration SMTP</h2>
          <span
            className={`ml-auto text-xs ${smtp?.configured ? "text-[color:var(--accent-success)]" : "text-[color:var(--text-muted)]"}`}
          >
            {smtp?.configured ? "configuré" : "non configuré (emails loggés)"}
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <input className="input" placeholder="hôte SMTP" value={host} onChange={(e) => setHost(e.target.value)} />
          <input className="input" placeholder="port" value={port} onChange={(e) => setPort(e.target.value)} />
          <input className="input" placeholder="utilisateur" value={user} onChange={(e) => setUser(e.target.value)} />
          <input
            className="input"
            type="password"
            placeholder="mot de passe (laisser vide = inchangé)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <input
            className="input sm:col-span-2"
            placeholder="expéditeur (ex: Revizio <no-reply@domaine>)"
            value={fromAddr}
            onChange={(e) => setFromAddr(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
            <input type="checkbox" checked={useTls} onChange={(e) => setUseTls(e.target.checked)} />
            STARTTLS (port 587). Décocher pour SSL direct (port 465).
          </label>
        </div>
        <button onClick={save} disabled={busy} className="btn-primary">
          Enregistrer
        </button>
      </div>

      <div className="card space-y-3">
        <h2 className="font-display text-lg font-semibold">Tester l'envoi</h2>
        <div className="flex gap-2">
          <input
            className="input"
            placeholder="email de destination"
            value={testTo}
            onChange={(e) => setTestTo(e.target.value)}
          />
          <button onClick={test} disabled={busy || !testTo} className="btn-secondary">
            Envoyer un test
          </button>
        </div>
        {msg && <p className="text-sm text-[color:var(--accent-primary)]">{msg}</p>}
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[color:var(--border-subtle)] text-left text-xs uppercase tracking-wider text-[color:var(--text-muted)]">
              <th className="px-4 py-3">Destinataire</th>
              <th className="px-4 py-3">Sujet</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Statut</th>
              <th className="px-4 py-3">Date</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-[color:var(--text-muted)]">
                  Aucun email envoyé.
                </td>
              </tr>
            ) : (
              logs.map((l) => (
                <tr key={l.id} className="border-b border-[color:var(--border-subtle)]/50">
                  <td className="px-4 py-3 font-mono text-xs">{l.to_email}</td>
                  <td className="px-4 py-3">{l.subject}</td>
                  <td className="px-4 py-3 text-xs text-[color:var(--text-muted)]">{l.template}</td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        l.status === "sent"
                          ? "text-[color:var(--accent-success)]"
                          : l.status === "failed"
                            ? "text-[color:var(--accent-danger)]"
                            : "text-[color:var(--text-muted)]"
                      }
                    >
                      {l.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-[color:var(--text-muted)]">
                    {new Date(l.created_at).toLocaleString("fr-FR")}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
