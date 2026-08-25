import type { StoragePort } from "../../ports/StoragePort";

const PREFIX = "xmlproofreader:";

// Resolve a usable Storage, or null when none exists (e.g. node/test context
// without jsdom). Guards a bare `localStorage` reference, which would otherwise
// throw ReferenceError. In production (browser/Tauri webview) it is always
// present; "no storage" degrades to a safe no-op instead of crashing the store.
function ls(): Storage | null {
  return typeof localStorage !== "undefined" ? localStorage : null;
}

export class BrowserStorage implements StoragePort {
  async get<T>(key: string): Promise<T | null> {
    const raw = ls()?.getItem(PREFIX + key) ?? null;
    return raw ? (JSON.parse(raw) as T) : null;
  }
  async set<T>(key: string, value: T): Promise<void> {
    ls()?.setItem(PREFIX + key, JSON.stringify(value));
  }
  async remove(key: string): Promise<void> {
    ls()?.removeItem(PREFIX + key);
  }
}
