import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import RecordPage from "./pages/RecordPage";
import CoursePage from "./pages/CoursePage";
import SettingsPage from "./pages/SettingsPage";
import AppShell from "./components/AppShell";

export default function App() {
  const { user, loading, init } = useAuth();

  useEffect(() => {
    void init();
  }, [init]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[color:var(--border-strong)] border-t-[color:var(--accent-primary)]" />
      </div>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/record" element={<RecordPage />} />
        <Route path="/courses/:id" element={<CoursePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
