// S1000D language profile, covering issues 3.0 / 4.0 / 4.1 / 4.2 (one common
// builder; the issue is detected from the document). Handles descriptive and
// procedural data modules and publication modules (PM). The issue mainly drives
// schema/BREX rules; the rendered structure is shared across issues.
import type { PosNode } from "../model/types";
import { firstByName } from "../xml/tree";
import { buildInlines, inlineText, hasVisibleText } from "../render/inlines";
import { buildTableBlock } from "../render/table";
import type { Block, Inline, RenderedDoc } from "../render/model";
import type { LanguageProfile, Detection, LinkPolicy, RefAttrDef } from "./profile";

const SUPPORTED_ISSUES = new Set(["3.0", "4.0", "4.1", "4.2"]);

const INLINE_GI = new Set([
  "emphasis", "internalRef", "dmRef", "pmRef", "externalPubRef", "caption",
  "verbatimText", "acronym", "acronymTerm", "footnote", "ref", "xref",
]);

const NOTE_LABEL: Record<string, string> = {
  warning: "Warning", caution: "Caution", note: "Note", attentionListItem: "Attention",
};

function makeId(n: PosNode): string {
  // Prefer the element @id so S1000D internalRef ("#id") scrolls to its target.
  return n.attrs?.["id"] ?? `n${n.start}`;
}

function detectIssue(root: PosNode, buffer: string): string {
  const loc =
    root.attrs?.["xsi:noNamespaceSchemaLocation"] ??
    root.attrs?.["noNamespaceSchemaLocation"] ??
    root.attrs?.["xsi:schemaLocation"] ??
    "";
  const m = (loc + " " + buffer.slice(0, 600)).match(/S1000D[_\- ]?(\d)[._\-](\d)/i);
  if (m) {
    const v = `${m[1]}.${m[2]}`;
    if (SUPPORTED_ISSUES.has(v)) return v;
  }
  const issAttr = root.attrs?.["issue"] ?? root.attrs?.["issueNumber"] ?? "";
  if (SUPPORTED_ISSUES.has(issAttr)) return issAttr;
  return ""; // S1000D recognized, issue unknown
}

const BLOCK_GI = new Set([
  "para", "simplePara", "title", "warning", "caution", "note", "table", "figure",
  "levelledPara", "proceduralStep", "step", "mainProcedure", "procedure", "isolationProcedure",
  "randomList", "sequentialList", "unorderedList", "orderedList", "listItem",
  "description", "content", "preliminaryRqmts", "closeRqmts",
]);

function isInlineS(el: PosNode): boolean {
  const gi = el.name ?? "";
  if (BLOCK_GI.has(gi)) return false;
  if (INLINE_GI.has(gi)) return true;
  return !(el.children ?? []).some((c) => c.kind === "element" && !isInlineS(c));
}

function s1000dTitle(root: PosNode): Inline[] | null {
  const dmTitle = firstByName(root, "dmTitle");
  if (dmTitle) {
    const tech = firstByName(dmTitle, "techName");
    const info = firstByName(dmTitle, "infoName");
    const parts: string[] = [];
    if (tech) parts.push(inlineText(buildInlines(tech.children ?? [])));
    if (info) parts.push(inlineText(buildInlines(info.children ?? [])));
    const txt = parts.filter(Boolean).join(" — ");
    if (txt) return [{ kind: "text", text: txt, srcStart: dmTitle.start }];
  }
  const pmTitle = firstByName(root, "pmTitle");
  if (pmTitle) return buildInlines(pmTitle.children ?? []);
  const t = firstByName(root, "title");
  return t ? buildInlines(t.children ?? []) : null;
}

function note(el: PosNode, type: "danger" | "warning" | "" , label: string): Block {
  return { kind: "note", id: makeId(el), src: { start: el.start, end: el.end }, noteType: type || "note", label,
    inlines: buildInlines(el.children ?? []) };
}

function buildTable(el: PosNode, id: string, src: { start: number; end: number }): Block {
  const { caption, columns, headRows, bodyRows } = buildTableBlock(el);
  return { kind: "table", id, src, caption, columns, headRows, bodyRows };
}

const STEP_GIS = new Set(["proceduralStep", "step"]);
const STEPS_GIS = new Set(["mainProcedure", "procedure", "isolationProcedure"]);
const LIST_GIS = new Set(["randomList", "sequentialList", "unorderedList", "orderedList"]);

function buildBlockList(el: PosNode, buffer: string): Block[] {
  const gi = el.name ?? "";
  const id = makeId(el);
  const src = { start: el.start, end: el.end };

  if (gi === "para" || gi === "simplePara") return [{ kind: "para", id, src, inlines: buildInlines(el.children ?? []) }];
  if (gi === "title") return [{ kind: "heading", id, src, level: 2, inlines: buildInlines(el.children ?? []) }];
  if (gi === "warning") return [note(el, "danger", NOTE_LABEL.warning)];
  if (gi === "caution") return [note(el, "warning", NOTE_LABEL.caution)];
  if (gi === "note") return [note(el, "", NOTE_LABEL.note)];
  if (gi === "table") return [buildTable(el, id, src)];
  if (gi === "figure") {
    const graphic = firstByName(el, "graphic");
    const titleEl = (el.children ?? []).find((c) => c.kind === "element" && c.name === "title");
    return [{ kind: "figure", id, src,
      caption: titleEl ? buildInlines(titleEl.children ?? []) : null,
      imageHref: graphic?.attrs?.["infoEntityIdent"] ?? graphic?.attrs?.["href"] ?? null }];
  }
  if (LIST_GIS.has(gi)) {
    const ordered = gi === "sequentialList" || gi === "orderedList";
    const items = (el.children ?? []).filter((c) => c.kind === "element" && /listItem$/i.test(c.name ?? ""))
      .map((li) => buildBlocks(li, buffer));
    return [{ kind: "list", id, src, ordered, items }];
  }
  if (STEPS_GIS.has(gi)) {
    const steps = (el.children ?? []).filter((c) => c.kind === "element" && STEP_GIS.has(c.name ?? ""))
      .map((s) => buildBlocks(s, buffer));
    return [{ kind: "steps", id, src, steps }];
  }
  if (gi === "levelledPara" || gi === "proceduralStep" || gi === "step") {
    // container with an optional title heading + nested content
    const out: Block[] = [];
    const titleEl = (el.children ?? []).find((c) => c.kind === "element" && c.name === "title");
    if (titleEl) out.push({ kind: "heading", id: makeId(titleEl), level: gi === "levelledPara" ? 2 : 3,
      src: { start: titleEl.start, end: titleEl.end }, inlines: buildInlines(titleEl.children ?? []) });
    out.push(...buildBlocks({ ...el, children: (el.children ?? []).filter((c) => c !== titleEl) }, buffer));
    return out;
  }
  // generic container / leaf
  const hasBlockChild = (el.children ?? []).some((c) => c.kind === "element" && !isInlineS(c));
  if (hasBlockChild) return buildBlocks(el, buffer);
  const inl = buildInlines(el.children ?? []);
  return hasVisibleText(inl) ? [{ kind: "para", id, src, inlines: inl }] : [];
}

function buildBlocks(container: PosNode, buffer: string): Block[] {
  const blocks: Block[] = [];
  let pending: PosNode[] = [];
  const flush = () => {
    if (!pending.length) return;
    const inl = buildInlines(pending);
    if (hasVisibleText(inl)) blocks.push({ kind: "para", id: `n${pending[0].start}`,
      src: { start: pending[0].start, end: pending[pending.length - 1].end }, inlines: inl });
    pending = [];
  };
  for (const child of container.children ?? []) {
    if (child.kind === "element" && !isInlineS(child)) { flush(); blocks.push(...buildBlockList(child, buffer)); }
    else if (child.kind === "comment" || child.kind === "doctype") { /* skip */ }
    else pending.push(child);
  }
  flush();
  return blocks;
}

function buildRendered(tree: PosNode, buffer: string): RenderedDoc {
  const root = (tree.children ?? []).find((c) => c.kind === "element");
  if (!root) return { title: null, subtitle: null, blocks: [], outline: [] };
  const title = s1000dTitle(root);
  // body: content/description or content/procedure; fall back to content or root
  const content = firstByName(root, "content");
  const bodyRoot = content
    ? (firstByName(content, "description") ?? firstByName(content, "procedure") ?? content)
    : root;
  const blocks = buildBlocks(bodyRoot, buffer);
  const outline = blocks.filter((b): b is Extract<Block, { kind: "heading" }> => b.kind === "heading")
    .map((b) => ({ id: b.id, text: inlineText(b.inlines), level: b.level }));
  return { title, subtitle: null, blocks, outline };
}

const s1000dLinkPolicy: LinkPolicy = {
  refAttrsFor(gi: string): RefAttrDef[] {
    if (gi === "internalRef") return [{ kind: "s1000d-internal", attr: "internalRefId" }];
    if (gi === "dmRef") return [{ kind: "s1000d-dm", attr: "" }];
    if (gi === "pmRef") return [{ kind: "s1000d-pm", attr: "" }];
    return [];
  },
};

export const s1000dProfile: LanguageProfile = {
  id: "s1000d",
  language: "S1000D",
  detect(root: PosNode): Detection | null {
    const gi = root.name ?? "";
    if (gi !== "dmodule" && gi !== "pm") return null;
    // version comes from the document; resolved via the buffer below
    return { language: "S1000D", version: "", profileId: "s1000d" };
  },
  buildRendered,
  linkPolicy: s1000dLinkPolicy,
};

// exported so the registry can refine the issue from the buffer
export { detectIssue };
