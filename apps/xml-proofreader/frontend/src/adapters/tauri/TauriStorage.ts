// Tauri key/value storage backed by the native temp/app-data commands
// (save_temp/read_temp/clear_temp). Keys are namespaced with "kv:".
import type { StoragePort } from "../../ports/StoragePort";

interface Bridge {
  core: { invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> };
}
function bridge(): Bridge {
  const t = (window as unknown as { __TAURI__?: Bridge }).__TAURI__;
  if (!t) throw new Error("Tauri bridge unavailable");
  return t;
}

export class TauriStorage implements StoragePort {
  async get<T>(key: string): Promise<T | null> {
    const raw = await bridge().core.invoke<string | null>("read_temp", { key: "kv:" + key });
    return raw ? (JSON.parse(raw) as T) : null;
  }
  async set<T>(key: string, value: T): Promise<void> {
    await bridge().core.invoke("save_temp", { key: "kv:" + key, content: JSON.stringify(value) });
  }
  async remove(key: string): Promise<void> {
    await bridge().core.invoke("clear_temp", { key: "kv:" + key });
  }
}
