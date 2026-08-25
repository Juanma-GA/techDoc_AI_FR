// Resolves image references (DITA @href, S1000D ICN) to a displayable URL.
// - data: and http(s): pass through unchanged.
// - Relative paths are read through a ResourcePort and inlined as data URIs.
// - S1000D ICNs (no extension) probe common graphic extensions.
// Results are cached per (baseUri, href).
import type { ResourcePort } from "../../ports/ResourcePort";

const MIME: Record<string, string> = {
  svg: "image/svg+xml", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
  gif: "image/gif", webp: "image/webp", bmp: "image/bmp", tif: "image/tiff", tiff: "image/tiff",
};
const GRAPHIC_EXTS = ["svg", "png", "jpg", "jpeg", "gif", "webp", "tif", "tiff", "cgm"];

function extOf(path: string): string {
  const m = path.toLowerCase().match(/\.([a-z0-9]+)$/);
  return m ? m[1] : "";
}
function mimeForPath(path: string): string {
  return MIME[extOf(path)] ?? "application/octet-stream";
}

function base64(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  // btoa exists in browser and Node 16+ (global)
  return typeof btoa === "function" ? btoa(bin) : Buffer.from(bytes).toString("base64");
}

/** Candidate file names to try. ICNs (no extension) probe known graphic types. */
export function candidatePaths(href: string): string[] {
  if (extOf(href)) return [href];
  return GRAPHIC_EXTS.map((e) => `${href}.${e}`);
}

export class ResourceResolver {
  private cache = new Map<string, string | null>();
  constructor(private port: ResourcePort) {}

  async resolveImage(href: string | null, baseUri: string | null): Promise<string | null> {
    if (!href) return null;
    if (href.startsWith("data:") || /^https?:\/\//i.test(href)) return href;

    const key = `${baseUri ?? ""}|${href}`;
    if (this.cache.has(key)) return this.cache.get(key)!;

    for (const path of candidatePaths(href)) {
      const bytes = await this.port.readBytes(baseUri, path).catch(() => null);
      if (bytes && bytes.length) {
        const mime = mimeForPath(path);
        const url =
          mime === "image/svg+xml"
            ? `data:image/svg+xml;utf8,${encodeURIComponent(new TextDecoder().decode(bytes))}`
            : `data:${mime};base64,${base64(bytes)}`;
        this.cache.set(key, url);
        return url;
      }
    }
    this.cache.set(key, null);
    return null;
  }

  clear() {
    this.cache.clear();
  }
}
