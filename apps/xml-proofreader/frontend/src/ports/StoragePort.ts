// Persistent key/value storage, platform-agnostic. Used for user accounts and
// per-user workspace settings. Adapters: browser (localStorage) and Tauri
// (app-data files). Values are JSON-serializable.
export interface StoragePort {
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T): Promise<void>;
  remove(key: string): Promise<void>;
}
