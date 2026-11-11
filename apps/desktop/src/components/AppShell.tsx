import { NavLink } from "react-router-dom";
import { Home, Mic, Settings, LogOut } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import type { ReactNode } from "react";

const navItems = [
  { to: "/", label: "Cours", icon: Home },
  { to: "/record", label: "Enregistrer", icon: Mic },
  { to: "/settings", label: "Réglages", icon: Settings },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="flex h-full">
      <aside className="flex w-60 flex-col border-r border-[color:var(--border-subtle)] bg-[color:var(--bg-surface)]">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="h-8 w-8 rounded-md bg-grad-primary" />
          <span className="font-display text-lg font-bold tracking-tight">Revizio</span>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-[color:var(--bg-elevated)] text-[color:var(--accent-primary)]"
                    : "text-[color:var(--text-secondary)] hover:bg-[color:var(--bg-elevated)] hover:text-[color:var(--text-primary)]"
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-[color:var(--border-subtle)] p-3">
          <div className="mb-2 px-2">
            <p className="truncate text-sm font-medium">{user?.display_name}</p>
            <p className="truncate text-xs text-[color:var(--text-muted)]">{user?.email}</p>
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-[color:var(--text-secondary)] transition-colors hover:bg-[color:var(--bg-elevated)] hover:text-[color:var(--accent-danger)]"
          >
            <LogOut size={16} />
            Déconnexion
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
