/** Client API Revizio (web). */

import type {
  AdminJob,
  AdminStats,
  AdminUser,
  ApiKey,
  Course,
  CourseDetail,
  DownloadItem,
  KeyMode,
  OnlineInfo,
  PlatformKey,
  SystemInfo,
  TokenPair,
  User,
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
};

export { API_BASE };
