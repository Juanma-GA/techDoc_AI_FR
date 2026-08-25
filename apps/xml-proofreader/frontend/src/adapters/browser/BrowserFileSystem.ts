// ============================================================
// Browser adapter for FileSystemPort.
// Uses the File System Access API when available (Chromium/Edge) so the
// SME can save back to the original file in place; otherwise falls back
// to the classic download/upload flow. Temp copies use IndexedDB.
// ============================================================

import type { FileSystemPort, OpenedFile } from "../../ports/FileSystemPort";

type FSAWindow = Window & {
  showOpenFilePicker?: (opts?: unknown) => Promise<FileSystemFileHandleLike[]>;
  showSaveFilePicker?: (opts?: unknown) => Promise<FileSystemFileHandleLike>;
};

interface FileSystemFileHandleLike {
  getFile(): Promise<File>;
  createWritable(): Promise<{
    write(data: string): Promise<void>;
    close(): Promise<void>;
  }>;
  name: string;
}

const PICKER_OPTS = {
  types: [
    {
      description: "DITA / XML documents",
      accept: { "application/xml": [".dita", ".xml", ".ditamap"] },
    },
  ],
};

const TEMP_DB = "docreview-temp";
const TEMP_STORE = "files";

function idb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(TEMP_DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(TEMP_STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbPut(key: string, value: string): Promise<void> {
  const db = await idb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(TEMP_STORE, "readwrite");
    tx.objectStore(TEMP_STORE).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function idbGet(key: string): Promise<string | null> {
  const db = await idb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(TEMP_STORE, "readonly");
    const req = tx.objectStore(TEMP_STORE).get(key);
    req.onsuccess = () => resolve((req.result as string) ?? null);
    req.onerror = () => reject(req.error);
  });
}

async function idbDel(key: string): Promise<void> {
  const db = await idb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(TEMP_STORE, "readwrite");
    tx.objectStore(TEMP_STORE).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

/** In-memory map of uri → live file handle for in-place saves. */
const handles = new Map<string, FileSystemFileHandleLike>();

function triggerDownload(name: string, content: string): void {
  const blob = new Blob([content], { type: "application/xml" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

export class BrowserFileSystem implements FileSystemPort {
  get canSaveInPlace(): boolean {
    return typeof (window as FSAWindow).showSaveFilePicker === "function";
  }

  async openFile(): Promise<OpenedFile | null> {
    const w = window as FSAWindow;
    if (w.showOpenFilePicker) {
      const picked = await w.showOpenFilePicker(PICKER_OPTS).catch(() => null);
      if (!picked || !picked.length) return null;
      const handle = picked[0];
      const file = await handle.getFile();
      const content = await file.text();
      const uri = `fsa:${handle.name}:${Date.now()}`;
      handles.set(uri, handle);
      return { uri, fileName: handle.name, content };
    }
    // Fallback: classic <input type=file>
    return new Promise((resolve) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".dita,.xml,.ditamap";
      input.onchange = async () => {
        const file = input.files?.[0];
        if (!file) return resolve(null);
        const content = await file.text();
        resolve({ uri: `mem:${file.name}`, fileName: file.name, content });
      };
      input.click();
    });
  }

  async saveFile(uri: string | null, fileName: string, content: string): Promise<string> {
    if (uri && handles.has(uri)) {
      const handle = handles.get(uri)!;
      const writable = await handle.createWritable();
      await writable.write(content);
      await writable.close();
      return uri;
    }
    // No in-place handle: behave like Save As.
    const newUri = await this.saveFileAs(fileName, content);
    return newUri ?? uri ?? `mem:${fileName}`;
  }

  async saveFileAs(suggestedName: string, content: string): Promise<string | null> {
    const w = window as FSAWindow;
    if (w.showSaveFilePicker) {
      const handle = await w
        .showSaveFilePicker({ ...PICKER_OPTS, suggestedName })
        .catch(() => null);
      if (!handle) return null;
      const writable = await handle.createWritable();
      await writable.write(content);
      await writable.close();
      const uri = `fsa:${handle.name}:${Date.now()}`;
      handles.set(uri, handle);
      return uri;
    }
    triggerDownload(suggestedName, content);
    return `mem:${suggestedName}`;
  }

  async saveTemp(key: string, content: string): Promise<void> {
    await idbPut(key, content);
  }
  async readTemp(key: string): Promise<string | null> {
    return idbGet(key);
  }
  async clearTemp(key: string): Promise<void> {
    await idbDel(key);
  }
}
