// LinkResolver — resolves DITA xref/conref/conkeyref/keyref and S1000D
// internalRef/dmRef/pmRef. Core-pure: receives a `provide` async function for
// external bytes; performs no IO itself.
import type { PosNode } from "../model/types";
import type { MapModel } from "./model";
import { firstByName } from "../xml/tree";

/** Async function that returns the text content of an external file, or null. */
export type Provide = (href: string) => Promise<string | null>;

export type LinkResult =
  | { kind: "internal"; targetId: string }
  | { kind: "external"; href: string; anchor?: string }
  | { kind: "conref"; content: string }
  | { kind: "unresolved"; reason: string };

function splitHref(href: string): { file: string; anchor: string } {
  const idx = href.indexOf("#");
  if (idx < 0) return { file: href, anchor: "" };
  return { file: href.slice(0, idx), anchor: href.slice(idx + 1) };
}

/** Extract the last segment of a DITA anchor (topic/section → section). */
function anchorId(anchor: string): string {
  return anchor.split("/").pop() ?? anchor;
}

/** Best-effort text extraction from raw XML by @id attribute. */
function extractById(xml: string, id: string): string | null {
  // Matches the innermost element with id="..." and strips tags.
  const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pat = new RegExp(`id=["']${escaped}["'][^>]*>([\\s\\S]*?)<\\/`, "i");
  const m = xml.match(pat);
  if (!m) return null;
  return m[1].replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim() || null;
}

export class LinkResolver {
  constructor(
    private readonly keydefs: MapModel["keydefs"],
    private readonly provide: Provide
  ) {}

  /**
   * Resolve a DITA @href + optional @keyref on the same element.
   * Keyref is looked up in the map's keydefs first; if found and it carries
   * a href, that href is used. Falls back to the raw href.
   */
  resolveHref(href: string | undefined, keyref?: string): LinkResult {
    let resolved = href ?? "";

    if (keyref) {
      const def = this.keydefs[keyref];
      if (def?.href) {
        resolved = def.href;
      } else if (!resolved) {
        return { kind: "unresolved", reason: `keyref "${keyref}" not found in map context` };
      }
    }

    if (!resolved) return { kind: "unresolved", reason: "empty href" };

    const { file, anchor } = splitHref(resolved);

    if (!file) {
      // Same-document fragment: "#topic/section" or "#id"
      return { kind: "internal", targetId: anchorId(anchor) };
    }

    return { kind: "external", href: file, anchor: anchorId(anchor) || undefined };
  }

  /**
   * Resolve a DITA @keyref standalone (no @href on the element).
   */
  resolveKeyref(keyref: string): LinkResult {
    const def = this.keydefs[keyref];
    if (!def) return { kind: "unresolved", reason: `keyref "${keyref}" not found` };
    if (def.href) return this.resolveHref(def.href);
    // Key exists but has no href (e.g. keyword variable) — unresolved as link
    return { kind: "unresolved", reason: `keyref "${keyref}" has no href` };
  }

  /**
   * Resolve a DITA @conref attribute.
   * Forms: "file.dita#topicid/elemid" — external
   *        "#topicid/elemid"           — same-doc (returns internal)
   *        "file.dita#topicid"         — topic conref (returns external/internal)
   */
  async resolveConref(conref: string): Promise<LinkResult> {
    const { file, anchor } = splitHref(conref);
    const id = anchorId(anchor);

    if (!file) {
      // Same-document reference
      return id ? { kind: "internal", targetId: id } : { kind: "unresolved", reason: "empty conref anchor" };
    }

    const bytes = await this.provide(file).catch(() => null);
    if (!bytes) return { kind: "unresolved", reason: `Cannot fetch "${file}"` };

    if (id) {
      const content = extractById(bytes, id);
      if (content) return { kind: "conref", content };
      return { kind: "unresolved", reason: `Element "${id}" not found in "${file}"` };
    }

    // Topic-level conref: return the whole file as content (first ~200 chars)
    const stripped = bytes.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
    return { kind: "conref", content: stripped.slice(0, 200) };
  }

  /**
   * Resolve a DITA @conkeyref attribute: "key/elementId" where `key` is
   * looked up in keydefs to get the file.
   */
  async resolveConkeyref(conkeyref: string): Promise<LinkResult> {
    const slash = conkeyref.indexOf("/");
    const key = slash < 0 ? conkeyref : conkeyref.slice(0, slash);
    const elemId = slash < 0 ? "" : conkeyref.slice(slash + 1);
    const def = this.keydefs[key];
    if (!def?.href) return { kind: "unresolved", reason: `conkeyref key "${key}" not found` };
    const conref = elemId ? `${def.href}#${key}/${elemId}` : def.href;
    return this.resolveConref(conref);
  }

  /** Resolve an S1000D internalRef element (same-document anchor). */
  resolveS1000dInternalRef(node: PosNode): LinkResult {
    const id = node.attrs?.["internalRefId"] ?? "";
    if (!id) return { kind: "unresolved", reason: "missing internalRefId" };
    return { kind: "internal", targetId: id };
  }

  /** Resolve an S1000D dmRef or pmRef element to a filename. */
  resolveS1000dExternalRef(node: PosNode): LinkResult {
    const codeEl = firstByName(node, "dmCode") ?? firstByName(node, "pmCode");
    if (!codeEl?.attrs) return { kind: "unresolved", reason: "no dmCode/pmCode in ref" };
    const a = codeEl.attrs;
    const parts = [
      a["modelIdentCode"], a["systemDiffCode"], a["systemCode"],
      a["subSystemCode"], a["subSubSystemCode"],
    ].filter(Boolean);
    if (!parts.length) return { kind: "unresolved", reason: "empty dmCode/pmCode attributes" };
    const prefix = codeEl.name === "pmCode" ? "PMC" : "DMC";
    return { kind: "external", href: `${prefix}-${parts.join("-")}.xml` };
  }
}
