/** Store d'authentification (web). */

import { create } from "zustand";
import { api, tokenStore } from "../lib/api";
import type { User } from "../lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  init: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    first_name: string,
    last_name: string,
  ) => Promise<void>;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,

  init: async () => {
    if (!tokenStore.access) {
      set({ loading: false });
      return;
    }
    try {
      set({ user: await api.me(), loading: false });
    } catch {
      tokenStore.clear();
      set({ user: null, loading: false });
    }
  },

  login: async (email, password) => {
    tokenStore.set(await api.login(email, password));
    set({ user: await api.me() });
  },

  register: async (email, password, first_name, last_name) => {
    tokenStore.set(await api.register(email, password, first_name, last_name));
    set({ user: await api.me() });
  },

  logout: () => {
    tokenStore.clear();
    set({ user: null });
  },
}));
