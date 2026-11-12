import { useEffect, useState } from "react";
import { Download, Monitor, Apple, Terminal, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import type { DownloadItem } from "../lib/types";

function detectOS(): string {
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes("win")) return "windows";
  if (ua.includes("mac")) return "macos";
  if (ua.includes("linux")) return "linux";
  return "unknown";
}

function fmtSize(bytes: number): string {
  if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
  return `${(bytes / 1024).toFixed(0)} Ko`;
}

const OS_META: Record<string, { label: string; icon: typeof Monitor }> = {
  linux: { label: "Linux", icon: Terminal },
  windows: { label: "Windows", icon: Monitor },
  macos: { label: "macOS", icon: Apple },
};

export default function DownloadPage() {
  const [items, setItems] = useState<DownloadItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const os = detectOS();

  useEffect(() => {
    api
      .listDownloads()
      .then(setItems)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  const byOS = (target: string) => items.filter((i) => i.os === target);

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold">Télécharger Revizio</h1>
        <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
          L'application desktop permet d'enregistrer vos cours avec le micro de votre PC et de
          les transcrire en direct. Le site web sert à consulter vos fiches.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-[color:var(--text-secondary)]">
          <Loader2 className="animate-spin" size={18} /> Chargement…
        </div>
      ) : error ? (
        <p className="rounded-md bg-[color:var(--accent-danger)]/10 px-4 py-3 text-sm text-[color:var(--accent-danger)]">
          {error}
        </p>
      ) : items.length === 0 ? (
        <div className="card py-10 text-center">
          <p className="text-[color:var(--text-secondary)]">
            Aucun installeur disponible pour le moment.
          </p>
          <p className="mt-1 text-sm text-[color:var(--text-muted)]">
            Les binaires sont générés par la CI (Linux / macOS / Windows).
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {(["linux", "windows", "macos"] as const).map((target) => {
            const list = byOS(target);
            if (list.length === 0) return null;
            const meta = OS_META[target];
            const Icon = meta.icon;
            const isCurrent = os === target;
            return (
              <div
                key={target}
                className={`card ${isCurrent ? "border-[color:var(--accent-primary)]/40" : ""}`}
              >
                <div className="mb-3 flex items-center gap-2">
                  <Icon size={18} className="text-[color:var(--accent-primary)]" />
                  <h2 className="font-display text-lg font-semibold">{meta.label}</h2>
                  {isCurrent && (
                    <span className="rounded bg-[color:var(--accent-primary)]/15 px-2 py-0.5 text-xs text-[color:var(--accent-primary)]">
                      votre système
                    </span>
                  )}
                </div>
                <div className="space-y-2">
                  {list.map((item) => (
                    <a
                      key={item.filename}
                      href={item.url}
                      className="flex items-center justify-between rounded-md bg-[color:var(--bg-inset)] px-3 py-2.5 transition-colors hover:bg-[color:var(--bg-elevated)]"
                    >
                      <div className="flex items-center gap-3">
                        <Download size={16} className="text-[color:var(--text-secondary)]" />
                        <span className="font-mono text-sm">{item.filename}</span>
                      </div>
                      <span className="text-xs text-[color:var(--text-muted)]">
                        v{item.version} · {fmtSize(item.size)}
                      </span>
                    </a>
                  ))}
                </div>
              </div>
            );
          })}

          <div className="card">
            <h2 className="mb-2 font-display text-lg font-semibold">Installation</h2>
            <ul className="space-y-1 text-sm text-[color:var(--text-secondary)]">
              <li>
                <strong>Linux (.deb)</strong> : <code className="font-mono text-xs">sudo dpkg -i Revizio_*.deb</code>
              </li>
              <li>
                <strong>Linux (.AppImage)</strong> : <code className="font-mono text-xs">chmod +x Revizio_*.AppImage && ./Revizio_*.AppImage</code>
              </li>
              <li>
                <strong>Windows</strong> : double-clic sur le <code className="font-mono text-xs">.msi</code>
              </li>
              <li>
                <strong>macOS</strong> : ouvrir le <code className="font-mono text-xs">.dmg</code> et glisser dans Applications
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
