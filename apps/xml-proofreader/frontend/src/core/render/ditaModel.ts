// ============================================================
// Build the presentation model from the positional DITA tree.
//
// Resolution is driven by base type (@class) with GI fallback, so any DITA
// 1.3 specialization renders. Unknown elements degrade: containers are
// unwrapped, leaf-ish elements render their text as a paragraph — content is
// never dropped. Inline oxy highlight/comment regions become decorated runs.
// ============================================================

import type { PosNode } from "../model/types";
import { resolveBaseType, isInline } from "./fallback";
import { BASE_ROLE, type BlockRole } from "./classMap";
import type { Block, RenderedDoc } from "./model";
import { buildInlines, inlineText, hasVisibleText } from "./inlines";
import { buildTableBlock } from "./table";

function makeId(node: PosNode): string {
  // Prefer the DITA @id attribute so xref "#id" fragments scroll to the right element.
  return node.attrs?.["id"] ?? `n${node.start}`;
}

function roleOf(el: PosNode): BlockRole {
  const base = resolveBaseType(el);
  if (base && BASE_ROLE[base]) return BASE_ROLE[base];
  return isInline(el) ? "generic" : "container";
}

// ---------- block construction ----------

const NOTE_LABEL: Record<string, string> = {
  note: "Note", tip: "Tip", important: "Important", remember: "Remember",
  attention: "Attention", caution: "Caution", warning: "Warning",
  danger: "Danger", notice: "Notice", restriction: "Restriction",
  fastpath: "Fastpath", trouble: "Trouble",
};

function childrenByBase(el: PosNode, base: string): PosNode[] {
  return (el.children ?? []).filter((c) => c.kind === "element" && resolveBaseType(c) === base);
}
function firstChildByBase(el: PosNode, base: string): PosNode | null {
  return childrenByBase(el, base)[0] ?? null;
}

function buildBlockList(el: PosNode, buffer: string): Block[] {
  const role = roleOf(el);
  const id = makeId(el);
  const src = { start: el.start, end: el.end };

  switch (role) {
    case "para":
      return [{ kind: "para", id, src, inlines: buildInlines(el.children ?? [], buffer) }];

    case "note": {
      const t = (el.attrs?.["type"] ?? "note").toLowerCase();
      return [{
        kind: "note", id, src, noteType: t, label: NOTE_LABEL[t] ?? "Note",
        inlines: buildInlines(el.children ?? [], buffer),
      }];
    }

    case "list": {
      const ordered = resolveBaseType(el) === "topic/ol";
      const items = childrenByBase(el, "topic/li").map((li) => buildBlocks(li, buffer));
      return [{ kind: "list", id, src, ordered, items }];
    }

    case "steps": {
      const steps = (el.children ?? [])
        .filter((c) => c.kind === "element" && resolveBaseType(c) === "task/step")
        .map((step) => buildBlocks(step, buffer));
      return [{ kind: "steps", id, src, steps }];
    }

    case "table":
      return [buildTable(el, id, src)];

    case "figure": {
      const titleEl = firstChildByBase(el, "topic/title");
      const imageEl = firstChildByBase(el, "topic/image");
      return [{
        kind: "figure", id, src,
        caption: titleEl ? buildInlines(titleEl.children ?? [], buffer) : null,
        imageHref: imageEl?.attrs?.["href"] ?? null,
        imageScale: imageEl?.attrs?.["scale"] ? parseInt(imageEl.attrs["scale"], 10) : undefined,
      }];
    }

    case "image":
      return [{ kind: "figure", id, src, caption: null, imageHref: el.attrs?.["href"] ?? null,
        imageScale: el.attrs?.["scale"] ? parseInt(el.attrs["scale"], 10) : undefined }];

    case "heading":
      return [{ kind: "heading", id, src, level: 2, inlines: buildInlines(el.children ?? [], buffer) }];

    case "container":
      return buildContainer(el, buffer);

    case "generic":
    default: {
      const hasBlockChild = (el.children ?? []).some((c) => c.kind === "element" && !isInline(c));
      if (hasBlockChild) return buildBlocks(el, buffer);
      const inlines = buildInlines(el.children ?? [], buffer);
      return hasVisibleText(inlines)
        ? [{ kind: "para", id, src, inlines }]
        : [];
    }
  }
}

function buildContainer(el: PosNode, buffer: string): Block[] {
  const out: Block[] = [];
  const titleEl = firstChildByBase(el, "topic/title");
  if (titleEl) {
    out.push({
      kind: "heading", id: makeId(titleEl), level: 2,
      src: { start: titleEl.start, end: titleEl.end },
      inlines: buildInlines(titleEl.children ?? [], buffer),
    });
  }
  const rest = (el.children ?? []).filter((c) => c !== titleEl);
  out.push(...buildBlocks({ ...el, children: rest }, buffer));
  return out;
}

function buildTable(el: PosNode, id: string, src: { start: number; end: number }): Block {
  const { caption, columns, headRows, bodyRows } = buildTableBlock(el);
  return { kind: "table", id, src, caption, columns, headRows, bodyRows };
}

function buildBlocks(container: PosNode, buffer: string): Block[] {
  const blocks: Block[] = [];
  let pending: PosNode[] = [];

  const flush = () => {
    if (!pending.length) return;
    const inlines = buildInlines(pending, buffer);
    if (hasVisibleText(inlines)) {
      blocks.push({
        kind: "para",
        id: `n${pending[0].start}`,
        src: { start: pending[0].start, end: pending[pending.length - 1].end },
        inlines,
      });
    }
    pending = [];
  };

  for (const child of container.children ?? []) {
    if (child.kind === "element" && !isInline(child)) {
      flush();
      blocks.push(...buildBlockList(child, buffer));
    } else if (child.kind === "comment" || child.kind === "doctype") {
      // not rendered
    } else {
      pending.push(child); // text, cdata, inline elements, pis
    }
  }
  flush();
  return blocks;
}

// ---------- entry point ----------

export function buildRenderedDoc(tree: PosNode, buffer: string): RenderedDoc {
  const root = (tree.children ?? []).find((c) => c.kind === "element") ?? null;
  if (!root) return { title: null, subtitle: null, blocks: [], outline: [] };

  const titleEl = firstChildByBase(root, "topic/title");
  const descEl =
    firstChildByBase(root, "topic/shortdesc") ?? firstChildByBase(root, "topic/abstract");
  const title = titleEl ? buildInlines(titleEl.children ?? [], buffer) : null;
  const subtitle = descEl ? buildInlines(descEl.children ?? [], buffer) : null;

  // Body container, or the root's remaining children if no recognized body.
  const bodyEl = (root.children ?? []).find(
    (c) => c.kind === "element" && resolveBaseType(c) === "topic/body"
  );
  let blocks: Block[];
  if (bodyEl) {
    blocks = buildBlocks(bodyEl, buffer);
  } else {
    const rest = (root.children ?? []).filter((c) => c !== titleEl && c !== descEl);
    blocks = buildBlocks({ ...root, children: rest }, buffer);
  }

  const outline = blocks
    .filter((b): b is Extract<Block, { kind: "heading" }> => b.kind === "heading")
    .map((b) => ({ id: b.id, text: inlineText(b.inlines), level: b.level }));

  return { title, subtitle, blocks, outline };
}
