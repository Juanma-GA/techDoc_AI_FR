// Session store: local authentication + per-user workspace settings.
// The annotation author comes from the signed-in user.
import { create } from "zustand";
import { createStorage } from "../adapters";
import { AuthService } from "../core/auth/service";
import type { User } from "../core/auth/types";
import { initials } from "../core/auth/types";
import { defaultSettings, type Settings } from "../core/workspace/types";
import { useStore } from "./store";

const storage = createStorage();
const auth = new AuthService();
const CURRENT_KEY = "currentUserId";
const settingsKey = (userId: string) => `ws:${userId}`;

interface SessionState {
  ready: boolean;
  user: User | null;
  users: User[];
  settings: Settings;
  error: string | null;

  init: () => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<boolean>;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  updateSettings: (patch: Partial<Settings>) => Promise<void>;
  updateProfile: (name: string, email: string) => Promise<void>;
  setProject: (projectId: string) => Promise<void>;
}

async function loadSettings(userId: string): Promise<Settings> {
  return (await storage.get<Settings>(settingsKey(userId))) ?? defaultSettings();
}

function applyAuthorToDoc(user: User | null) {
  useStore.getState().setAuthor(user ? user.name : "Reviewer", user ? initials(user.name) : "R");
}

export const useSession = create<SessionState>((set, get) => ({
  ready: false,
  user: null,
  users: [],
  settings: defaultSettings(),
  error: null,

  init: async () => {
    try {
      const users = await auth.listUsers();
      const currentId = await storage.get<string>(CURRENT_KEY);
      const user = users.find((u) => u.id === currentId) ?? null;
      const settings = user ? await loadSettings(user.id) : defaultSettings();
      applyAuthorToDoc(user);
      set({ ready: true, users, user, settings });
    } catch (e) {
      set({ ready: true, error: (e as Error).message });
    }
  },

  register: async (name, email, password) => {
    try {
      const user = await auth.register(name, email, password);
      await storage.set(CURRENT_KEY, user.id);
      const settings = await loadSettings(user.id);
      applyAuthorToDoc(user);
      set({ user, users: await auth.listUsers(), settings, error: null });
      return true;
    } catch (e) {
      set({ error: (e as Error).message });
      return false;
    }
  },

  login: async (email, password) => {
    try {
      const user = await auth.login(email, password);
      if (!user) {
        set({ error: "Invalid email or password" });
        return false;
      }
      await storage.set(CURRENT_KEY, user.id);
      const settings = await loadSettings(user.id);
      applyAuthorToDoc(user);
      set({ user, settings, error: null });
      return true;
    } catch (e) {
      set({ error: (e as Error).message });
      return false;
    }
  },

  logout: () => {
    storage.remove(CURRENT_KEY);
    applyAuthorToDoc(null);
    set({ user: null });
  },

  updateSettings: async (patch) => {
    const user = get().user;
    const next = { ...get().settings, ...patch };
    set({ settings: next });
    if (user) await storage.set(settingsKey(user.id), next);
  },

  setProject: async (projectId) => {
    await get().updateSettings({ currentProjectId: projectId });
  },

  updateProfile: async (name, email) => {
    const user = get().user;
    if (!user) return;
    try {
      const updated = await auth.updateProfile(user.id, name, email);
      const users = get().users.map((u) => (u.id === user.id ? updated : u));
      applyAuthorToDoc(updated);
      set({ user: updated, users, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },
}));
