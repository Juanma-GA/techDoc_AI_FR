// Map model for DITA maps/bookmaps and S1000D Publication Modules (PM).
// Produces a navigation hierarchy + a key map (for keyref resolution).
import type { PosNode } from "../model/types";
import { rootElement, firstByName } from "../xml/tree";

export interface MapNode {
  title: string;
  href: string | null;
  key?: string;
  children: MapNode[];
}

export interface MapModel {
  kind: "dita" | "s1000d-pm";
  title: string;
  nodes: MapNode[];
  /** key → { href, text } from DITA keydef elements (for keyref resolution). */
  keydefs: Record<string, { href?: string; text?: string }>;
}

const DITA_REF_GIS = new Set([
  "topicref", "chapter", "appendix", "part", "preface", "frontmatter", "backmatter",
  "notices", "mapref", "topichead", "topicgroup", "anchorref",
]);

function textOf(node: PosNode | null, buffer: string): string {
  if (!node) return "";
  return buffer.slice(node.innerStart ?? node.start, node.innerEnd ?? node.end)
    .replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
}

function navTitle(ref: PosNode, buffer: string): string {
  if (ref.attrs?.["navtitle"]) return ref.attrs["navtitle"];
  const topicmeta = firstByName(ref, "topicmeta");
  const nt = topicmeta ? firstByName(topicmeta, "navtitle") : null;
  if (nt) return textOf(nt, buffer);
  const href = ref.attrs?.["href"];
  if (href) return href.replace(/^.*[\\/]/, "");
  return ref.name ?? "topic";
}

export function isMapRoot(tree: PosNode): "dita" | "s1000d-pm" | null {
  const root = rootElement(tree);
  if (!root) return null;
  const gi = root.name ?? "";
  if (gi === "map" || gi === "bookmap") return "dita";
  if (gi === "pm") return "s1000d-pm";
  return null;
}

function ditaRefs(el: PosNode, buffer: string, keydefs: MapModel["keydefs"]): MapNode[] {
  const out: MapNode[] = [];
  for (const c of el.children ?? []) {
    if (c.kind !== "element") continue;
    const gi = c.name ?? "";
    if (gi === "keydef") {
      const keys = c.attrs?.["keys"];
      if (keys) keydefs[keys] = { href: c.attrs?.["href"], text: navTitle(c, buffer) };
      continue;
    }
    if (!DITA_REF_GIS.has(gi)) continue;
    out.push({
      title: navTitle(c, buffer),
      href: c.attrs?.["href"] ?? null,
      key: c.attrs?.["keys"],
      children: ditaRefs(c, buffer, keydefs),
    });
  }
  return out;
}

function pmRefs(el: PosNode, buffer: string): MapNode[] {
  const out: MapNode[] = [];
  for (const c of el.children ?? []) {
    if (c.kind !== "element") continue;
    const gi = c.name ?? "";
    if (gi === "pmEntry") {
      const titleEl = firstByName(c, "pmEntryTitle");
      out.push({
        title: titleEl ? textOf(titleEl, buffer) : "Section",
        href: null,
        children: pmRefs(c, buffer),
      });
    } else if (gi === "dmRef" || gi === "pmRef") {
      const dmTitle = firstByName(c, "dmTitle");
      const tech = dmTitle ? firstByName(dmTitle, "techName") : null;
      const info = dmTitle ? firstByName(dmTitle, "infoName") : null;
      const title = [textOf(tech, buffer), textOf(info, buffer)].filter(Boolean).join(" — ")
        || firstByName(c, "dmCode")?.attrs?.["systemDiffCode"] || "Data module";
      out.push({ title, href: refIdentToFilename(c), children: [] });
    }
  }
  return out;
}

/** Best-effort filename for an S1000D dmRef from its dmCode attributes. */
function refIdentToFilename(ref: PosNode): string | null {
  const code = firstByName(ref, "dmCode");
  if (!code?.attrs) return null;
  const a = code.attrs;
  const parts = [a["modelIdentCode"], a["systemDiffCode"], a["systemCode"], a["subSystemCode"], a["subSubSystemCode"]]
    .filter(Boolean);
  return parts.length ? `DMC-${parts.join("-")}.xml` : null;
}

export function parseMap(tree: PosNode, buffer: string): MapModel {
  const kind = isMapRoot(tree);
  const root = rootElement(tree)!;
  const keydefs: MapModel["keydefs"] = {};
  if (kind === "s1000d-pm") {
    const hasDirect = (root.children ?? []).some((c) => c.kind === "element" && c.name === "pmEntry");
    const content = hasDirect ? root : firstByName(root, "content") ?? root;
    return { kind, title: textOf(firstByName(root, "pmTitle"), buffer) || "Publication", nodes: pmRefs(content, buffer), keydefs };
  }
  const title = textOf(firstByName(root, "title"), buffer) || root.attrs?.["title"] || "Map";
  return { kind: "dita", title, nodes: ditaRefs(root, buffer, keydefs), keydefs };
}

/** Flatten the hierarchy into outline entries with indentation levels. */
export function mapOutline(nodes: MapNode[], level = 1): { title: string; href: string | null; level: number }[] {
  const out: { title: string; href: string | null; level: number }[] = [];
  for (const n of nodes) {
    out.push({ title: n.title, href: n.href, level });
    out.push(...mapOutline(n.children, level + 1));
  }
  return out;
}

/** All referenced topic hrefs in document order (for "Resolve all topics"). */
export function mapHrefs(nodes: MapNode[]): string[] {
  const out: string[] = [];
  for (const n of nodes) {
    if (n.href) out.push(n.href);
    out.push(...mapHrefs(n.children));
  }
  return out;
}
