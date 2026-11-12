/** Client API Revizio (web). */

import type {
  AdminJob,
  AdminStats,
  AdminUser,
  ApiKey,
  Course,
  CourseDetail,
  Alert,
  DownloadItem,
  EmailLog,
  ExamFolder,
  KeyMode,
  OnlineInfo,
  PlatformKey,
  Quiz,
  Sheet,
  SmtpConfig,
  SystemInfo,
  TokenPair,
  User,
  UserUsage,
} from "./types";

// En production, l'API est servie en relatif (/api/...) via le reverse proxy nginx
// sur le même domaine. En dev, VITE_API_URL pointe vers le backend local.
const API_BASE = import.meta.env.VITE_API_URL ?? "";
const ACCESS_KEY = "revizio.access";
const REFRESH_KEY = "revizio.refresh";

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(t: TokenPair) {
    localStorage.setItem(ACCESS_KEY, t.access_token);
    localStorage.setItem(REFRESH_KEY, t.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const access = tokenStore.access;
  if (access) headers.set("Authorization", `Bearer ${access}`);

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (resp.status === 401 && retry && tokenStore.refresh) {
    if (await tryRefresh()) return request<T>(path, options, false);
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const resp = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokenStore.refresh }),
    });
    if (!resp.ok) {
      tokenStore.clear();
      return false;
    }
    tokenStore.set(await resp.json());
    return true;
  } catch {
    tokenStore.clear();
    return false;
  }
}

export const api = {
  register: (email: string, password: string, display_name: string) =>
    request<TokenPair>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    }),
  login: (email: string, password: string) =>
    request<TokenPair>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/api/auth/me"),

  listKeys: () => request<ApiKey[]>("/api/api-keys"),
  createKey: (provider: string, api_key: string, is_default = false) =>
    request<ApiKey>("/api/api-keys", {
      method: "POST",
      body: JSON.stringify({ provider, api_key, is_default }),
    }),
  deleteKey: (id: string) => request<void>(`/api/api-keys/${id}`, { method: "DELETE" }),
  rotateKey: (id: string, provider: string, api_key: string) =>
    request<ApiKey>(`/api/api-keys/${id}/rotate`, {
      method: "POST",
      body: JSON.stringify({ provider, api_key, is_default: false }),
    }),

  listCourses: () => request<Course[]>("/api/courses"),
  getCourse: (id: string) => request<CourseDetail>(`/api/courses/${id}`),
  deleteCourse: (id: string) => request<void>(`/api/courses/${id}`, { method: "DELETE" }),

  // 2FA
  totpStatus: () => request<{ enabled: boolean }>("/api/2fa/status"),
  totpSetup: () =>
    request<{ secret: string; provisioning_uri: string }>("/api/2fa/setup", { method: "POST" }),
  totpEnable: (code: string) =>
    request<{ enabled: boolean; backup_codes: string[] }>("/api/2fa/enable", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  totpDisable: (code: string) =>
    request<{ enabled: boolean }>("/api/2fa/disable", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),

  // Key mode (user)
  getKeyMode: () => request<KeyMode>("/api/api-keys/key-mode"),
  setKeyMode: (key_mode: string) =>
    request<KeyMode>("/api/api-keys/key-mode", {
      method: "PUT",
      body: JSON.stringify({ key_mode }),
    }),

  // Admin
  adminStats: () => request<AdminStats>("/api/admin/stats"),
  adminUsers: () => request<AdminUser[]>("/api/admin/users"),
  adminUpdateUser: (id: string, patch: { is_active?: boolean; key_mode?: string }) =>
    request<AdminUser>(`/api/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  adminJobs: () => request<AdminJob[]>("/api/admin/jobs"),
  adminPlatformKeys: () => request<PlatformKey[]>("/api/admin/platform-keys"),
  adminCreatePlatformKey: (provider: string, api_key: string) =>
    request<PlatformKey>("/api/admin/platform-keys", {
      method: "POST",
      body: JSON.stringify({ provider, api_key }),
    }),
  adminDeletePlatformKey: (id: string) =>
    request<void>(`/api/admin/platform-keys/${id}`, { method: "DELETE" }),
  adminSystem: () => request<SystemInfo>("/api/admin/system"),
  adminOnline: () => request<OnlineInfo>("/api/admin/online"),

  // Downloads (public)
  listDownloads: () => request<DownloadItem[]>("/api/downloads"),

  // Alertes / usage (admin)
  adminAlerts: () => request<Alert[]>("/api/admin/alerts"),
  adminAlertsCount: () => request<{ unread: number }>("/api/admin/alerts/count"),
  adminMarkAlertRead: (id: string) =>
    request<void>(`/api/admin/alerts/${id}/read`, { method: "POST" }),
  adminUsage: () => request<UserUsage[]>("/api/admin/usage"),

  // Admin complet : users CRUD
  adminCreateUser: (email: string, password: string, display_name: string, role: string) =>
    request<AdminUser>("/api/admin/users", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name, role }),
    }),
  adminSetRole: (id: string, role: string) =>
    request<AdminUser>(`/api/admin/users/${id}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  adminDeleteUser: (id: string) =>
    request<void>(`/api/admin/users/${id}`, { method: "DELETE" }),
  adminForceReset: (id: string) =>
    request<{ detail: string }>(`/api/admin/users/${id}/force-reset`, { method: "POST" }),

  // Clé plateforme avec compte
  adminCreatePlatformKeyFull: (provider: string, api_key: string, account_label: string) =>
    request<PlatformKey>("/api/admin/platform-keys/full", {
      method: "POST",
      body: JSON.stringify({ provider, api_key, account_label }),
    }),
  adminPlatformAccounts: () => request<string[]>("/api/admin/platform-keys/accounts"),

  // Emails
  adminEmailConfig: () => request<SmtpConfig>("/api/admin/email/config"),
  adminSetEmailConfig: (cfg: {
    host: string;
    port: number;
    user: string;
    password: string;
    use_tls: boolean;
    from_addr: string;
  }) =>
    request<SmtpConfig>("/api/admin/email/config", {
      method: "PUT",
      body: JSON.stringify(cfg),
    }),
  adminTestEmail: (to: string) =>
    request<{ sent: boolean }>("/api/admin/email/test", {
      method: "POST",
      body: JSON.stringify({ to }),
    }),
  adminEmailLogs: () => request<EmailLog[]>("/api/admin/email/logs"),

  // Alertes
  adminDeleteAlert: (id: string) =>
    request<void>(`/api/admin/alerts/${id}`, { method: "DELETE" }),

  // Révision : fiches
  listSheets: () => request<Sheet[]>("/api/revision/sheets"),
  createSheet: (title: string, subject: string | null, tags: string[], content: object) =>
    request<Sheet>("/api/revision/sheets", {
      method: "POST",
      body: JSON.stringify({ title, subject, tags, content }),
    }),
  updateSheet: (id: string, patch: object) =>
    request<Sheet>(`/api/revision/sheets/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  deleteSheet: (id: string) =>
    request<void>(`/api/revision/sheets/${id}`, { method: "DELETE" }),

  // Révision : dossiers
  listFolders: () => request<ExamFolder[]>("/api/revision/folders"),
  createFolder: (name: string, exam_date: string | null, description: string) =>
    request<ExamFolder>("/api/revision/folders", {
      method: "POST",
      body: JSON.stringify({ name, exam_date, description }),
    }),
  deleteFolder: (id: string) =>
    request<void>(`/api/revision/folders/${id}`, { method: "DELETE" }),
  addFolderItem: (folderId: string, sheetId: string) =>
    request<{ detail: string }>(`/api/revision/folders/${folderId}/items`, {
      method: "POST",
      body: JSON.stringify({ study_sheet_id: sheetId }),
    }),
  folderSheets: (folderId: string) =>
    request<Sheet[]>(`/api/revision/folders/${folderId}/sheets`),

  // Révision : quiz
  generateQuiz: (folder_id: string | null, sheet_ids: string[], count: number) =>
    request<Quiz>("/api/revision/quiz/generate", {
      method: "POST",
      body: JSON.stringify({ folder_id, sheet_ids, count }),
    }),
  listQuizzes: () => request<Quiz[]>("/api/revision/quizzes"),
  getQuiz: (id: string) => request<Quiz>(`/api/revision/quizzes/${id}`),
  deleteQuiz: (id: string) =>
    request<void>(`/api/revision/quizzes/${id}`, { method: "DELETE" }),

  // Mot de passe oublié
  forgotPassword: (email: string) =>
    request<{ detail: string }>("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, new_password: string) =>
    request<{ detail: string }>("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    }),
};

export { API_BASE };
