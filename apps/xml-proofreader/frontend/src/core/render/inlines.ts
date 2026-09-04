// Shared inline-content builder used by all language profiles. Converts a list
// of child nodes into decorated text runs, threading oxy highlight/comment
// decorations so annotations render regardless of the document language.
import type { PosNode, HighlightColor } from "../model/types";
import { rgbToColor } from "../model/types";
import type { Inline, TextRun, LinkRun } from "./model";

const CDATA_OPEN = "<![CDATA[";

// Inline elements emitted as a navigable LinkRun instead of unwrapping their
// children. This is the single source of truth for *inline-link* detection in
// the renderer; the per-language LinkPolicy (lang/*) declares the same refs as
// a contract for LinkResolver (see ADR-0006). Value = function extracting the
// raw href and optional keyref from the element's attrs.
const LINK_ELEMENTS: Record<string, (attrs: Record<string, string>) => { href: string; keyref?: string }> = {
  xref: (a) => ({ href: a["href"] ?? "", keyref: a["keyref"] }),
  internalRef: (a) => ({ href: a["internalRefId"] ? `#${a["internalRefId"]}` : "" }),
};

interface Deco {
  colors: { color: HighlightColor; offset: number }[];
  comments: number[];
}

function colorFromCustomStart(value: string | undefined): HighlightColor {
  const m = value?.match(/color="([^"]+)"/);
  return m ? rgbToColor(m[1]) : "yellow";
}

function run(text: string, srcStart: number, deco: Deco): TextRun {
  const r: TextRun = { kind: "text", text, srcStart };
  if (deco.colors.length) r.color = deco.colors[deco.colors.length - 1].color;
  if (deco.comments.length) r.commentKey = deco.comments[0]; // root of thread (not innermost reply)
  else if (deco.colors.length) r.commentKey = deco.colors[deco.colors.length - 1].offset;
  return r;
}

function scan(nodes: PosNode[], out: Inline[], deco: Deco): void {
  for (const node of nodes) {
    switch (node.kind) {
      case "text":
        if (node.value) out.push(run(node.value, node.start, deco));
        break;
      case "cdata": {
        const inner = (node.value ?? "").replace(/^<!\[CDATA\[/, "").replace(/\]\]>$/, "");
        out.push(run(inner, node.start + CDATA_OPEN.length, deco));
        break;
      }
      case "pi":
        if (node.name === "oxy_comment_start") deco.comments.push(node.start);
        else if (node.name === "oxy_comment_end") deco.comments.pop();
        else if (node.name === "oxy_custom_start")
          deco.colors.push({ color: colorFromCustomStart(node.value), offset: node.start });
        else if (node.name === "oxy_custom_end") deco.colors.pop();
        break;
      case "element": {
        const gi = node.name ?? "";
        const linkFn = LINK_ELEMENTS[gi];
        if (linkFn) {
          const { href, keyref } = linkFn(node.attrs ?? {});
          // Collect child runs for the link label.
          const childRuns: Inline[] = [];
          scan(node.children ?? [], childRuns, deco);
          const childText = childRuns.map((r) => r.text).join("").trim();
          // Offset of the link's first visible character. Falls back to the
          // element's inner/outer start for empty (self-closing) links. Using
          // the text offset (not the element's "<") keeps selection→buffer
          // mapping correct when a selection touches xref text (R2).
          const srcStart = childRuns[0]?.srcStart ?? node.innerStart ?? node.start;
          // Empty links get a neutral label rather than dumping the raw href.
          const link: LinkRun = { kind: "link", text: childText || "↗ link", srcStart, href };
          if (keyref) link.keyref = keyref;
          if (deco.colors.length) link.color = deco.colors[deco.colors.length - 1].color;
          if (deco.comments.length) link.commentKey = deco.comments[0]; // root of thread (not innermost reply)
          else if (deco.colors.length) link.commentKey = deco.colors[deco.colors.length - 1].offset;
          out.push(link);
        } else {
          scan(node.children ?? [], out, deco);
        }
        break;
      }
    }
  }
}

// `_buffer` is accepted (and ignored) so existing DITA call sites that thread a
// buffer compile unchanged; run offsets come from the nodes themselves.
export function buildInlines(nodes: PosNode[], _buffer?: string): Inline[] {
  const out: Inline[] = [];
  scan(nodes, out, { colors: [], comments: [] });
  return out;
}

export function inlineText(inlines: Inline[]): string {
  return inlines.map((i) => i.text).join("");
}

export function hasVisibleText(inlines: Inline[]): boolean {
  return inlines.some((i) => i.text.trim().length > 0);
}
