import { NavLink } from "react-router-dom";
import { Home, Settings, LogOut, Shield } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import type { ReactNode } from "react";
import Logo from "./Logo";

export default function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();

  const items = [
    { to: "/", label: "Mes cours", icon: Home, end: true },
    { to: "/settings", label: "Réglages", icon: Settings, end: false },
  ];
  if (user?.role === "admin") {
    items.push({ to: "/admin", label: "Administration", icon: Shield, end: false });
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-60 flex-col border-r border-[color:var(--border-subtle)] bg-[color:var(--bg-surface)]">
        <div className="flex items-center gap-2 px-5 py-5">
          <Logo size={32} />
          <span className="font-display text-lg font-bold tracking-tight">Revizio</span>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3">
          {items.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
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

      <main className="flex-1">{children}</main>
    </div>
  );
}
