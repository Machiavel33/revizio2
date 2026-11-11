/** Client API Revizio (backend FastAPI). */

import type {
  ApiKey,
  Course,
  CourseDetail,
  TokenPair,
  User,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const ACCESS_KEY = "revizio.access";
const REFRESH_KEY = "revizio.refresh";

export const tokenStore = {
  get access(): string | null {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh(): string | null {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(tokens: TokenPair) {
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
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

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const access = tokenStore.access;
  if (access) headers.set("Authorization", `Bearer ${access}`);

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (resp.status === 401 && retry && tokenStore.refresh) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, options, false);
  }

  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
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
  // Auth
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

  // API keys (BYOK)
  listKeys: () => request<ApiKey[]>("/api/api-keys"),
  createKey: (provider: string, api_key: string, is_default = false) =>
    request<ApiKey>("/api/api-keys", {
      method: "POST",
      body: JSON.stringify({ provider, api_key, is_default }),
    }),
  deleteKey: (id: string) =>
    request<void>(`/api/api-keys/${id}`, { method: "DELETE" }),

  // Courses
  listCourses: () => request<Course[]>("/api/courses"),
  createCourse: (title: string, subject?: string, language = "fr") =>
    request<Course>("/api/courses", {
      method: "POST",
      body: JSON.stringify({ title, subject, language }),
    }),
  getCourse: (id: string) => request<CourseDetail>(`/api/courses/${id}`),
  deleteCourse: (id: string) =>
    request<void>(`/api/courses/${id}`, { method: "DELETE" }),
  uploadAudio: (id: string, blob: Blob, filename = "audio.wav") => {
    const form = new FormData();
    form.append("file", blob, filename);
    return request<Course>(`/api/courses/${id}/audio`, {
      method: "POST",
      body: form,
    });
  },
  processCourse: (id: string) =>
    request<unknown>(`/api/courses/${id}/process`, { method: "POST" }),
};

export { API_BASE };
