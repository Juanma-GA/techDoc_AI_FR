// ============================================================
// Tauri adapter for FileSystemPort.
//
// Talks to the Rust shell through the globally-injected `window.__TAURI__`
// bridge (enabled via `app.withGlobalTauri = true` in tauri.conf.json), so
// this file needs no compile-time dependency on @tauri-apps/api and the
// browser build stays clean. The native commands `read_text_file`,
// `save_text_file` (which writes a .bak first) and the dialog plugin are
// provided by src-tauri/src/main.rs.
// ============================================================

import type { FileSystemPort, OpenedFile } from "../../ports/FileSystemPort";

interface TauriBridge {
  core: { invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> };
  dialog: {
    open(opts?: unknown): Promise<string | string[] | null>;
    save(opts?: unknown): Promise<string | null>;
  };
}

function bridge(): TauriBridge {
  const t = (window as unknown as { __TAURI__?: TauriBridge }).__TAURI__;
  if (!t) throw new Error("Tauri bridge unavailable");
  return t;
}

const DIALOG_FILTER = {
  filters: [{ name: "DITA / XML", extensions: ["dita", "xml", "ditamap"] }],
};

export function isTauri(): boolean {
  // Guard `window`: in a pure-node context (e.g. unit tests without jsdom) a bare
  // `window` reference throws ReferenceError. The app only runs in a browser /
  // Tauri webview, so "no window" simply means "not Tauri".
  return typeof window !== "undefined"
    && typeof (window as unknown as { __TAURI__?: unknown }).__TAURI__ !== "undefined";
}

export class TauriFileSystem implements FileSystemPort {
  readonly canSaveInPlace = true;

  async openFile(): Promise<OpenedFile | null> {
    const t = bridge();
    const picked = await t.dialog.open({ multiple: false, ...DIALOG_FILTER });
    const path = Array.isArray(picked) ? picked[0] : picked;
    if (!path) return null;
    const content = await t.core.invoke<string>("read_text_file", { path });
    const fileName = path.split(/[\\/]/).pop() ?? path;
    return { uri: path, fileName, content };
  }

  async saveFile(uri: string | null, fileName: string, content: string): Promise<string> {
    if (!uri) return (await this.saveFileAs(fileName, content)) ?? "";
    // Native command writes a .bak of the previous contents before overwriting.
    await bridge().core.invoke("save_text_file", { path: uri, content, backup: true });
    return uri;
  }

  async saveFileAs(suggestedName: string, content: string): Promise<string | null> {
    const t = bridge();
    const path = await t.dialog.save({ defaultPath: suggestedName, ...DIALOG_FILTER });
    if (!path) return null;
    await t.core.invoke("save_text_file", { path, content, backup: false });
    return path;
  }

  async saveTemp(key: string, content: string): Promise<void> {
    await bridge().core.invoke("save_temp", { key, content });
  }
  async readTemp(key: string): Promise<string | null> {
    return bridge().core.invoke<string | null>("read_temp", { key });
  }
  async clearTemp(key: string): Promise<void> {
    await bridge().core.invoke("clear_temp", { key });
  }
}
