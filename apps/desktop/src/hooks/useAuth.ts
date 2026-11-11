/** Store d'authentification (zustand). */

import { create } from "zustand";
import { api, tokenStore } from "../lib/api";
import type { User } from "../lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  init: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,
  error: null,

  init: async () => {
    if (!tokenStore.access) {
      set({ loading: false });
      return;
    }
    try {
      const user = await api.me();
      set({ user, loading: false });
    } catch {
      tokenStore.clear();
      set({ user: null, loading: false });
    }
  },

  login: async (email, password) => {
    set({ error: null });
    const tokens = await api.login(email, password);
    tokenStore.set(tokens);
    const user = await api.me();
    set({ user });
  },

  register: async (email, password, name) => {
    set({ error: null });
    const tokens = await api.register(email, password, name);
    tokenStore.set(tokens);
    const user = await api.me();
    set({ user });
  },

  logout: () => {
    tokenStore.clear();
    set({ user: null });
  },
}));
