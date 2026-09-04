import type { ResourcePort } from "../../ports/ResourcePort";

// In the browser/portable build we have no access to sibling files on disk.
// Absolute http(s) and data: URIs are handled by the resolver itself; relative
// paths simply can't be read here, so we return null (the viewer shows a
// placeholder). The Tauri build resolves them from disk.
export class BrowserResource implements ResourcePort {
  async readBytes(_baseUri: string | null, relPath: string): Promise<Uint8Array | null> {
    // Same-origin relative fetch only works if the document came from a URL,
    // which the file-picker flow does not provide. Try, but tolerate failure.
    try {
      if (/^https?:\/\//i.test(relPath)) {
        const res = await fetch(relPath);
        if (res.ok) return new Uint8Array(await res.arrayBuffer());
      }
    } catch {
      /* ignore */
    }
    return null;
  }
}
