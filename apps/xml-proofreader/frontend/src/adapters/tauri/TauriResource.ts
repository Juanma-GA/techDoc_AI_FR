// Reads sibling image files from disk (relative to the open document) via the
// native command `read_image_base64`, which joins the path against the
// document's directory and returns base64, or null if the file does not exist.
import type { ResourcePort } from "../../ports/ResourcePort";

interface Bridge {
  core: { invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> };
}
function bridge(): Bridge {
  const t = (window as unknown as { __TAURI__?: Bridge }).__TAURI__;
  if (!t) throw new Error("Tauri bridge unavailable");
  return t;
}

function fromBase64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export class TauriResource implements ResourcePort {
  async readBytes(baseUri: string | null, relPath: string): Promise<Uint8Array | null> {
    const b64 = await bridge()
      .core.invoke<string | null>("read_image_base64", { baseUri, relPath })
      .catch(() => null);
    return b64 ? fromBase64(b64) : null;
  }
}
