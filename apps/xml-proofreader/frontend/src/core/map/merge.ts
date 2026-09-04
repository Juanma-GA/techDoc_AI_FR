// "Resolve all topics": assemble every topic referenced by a map into a single
// merged document. Each topic is detected + rendered by its own language
// profile, then concatenated. The merged view is READ-ONLY (offsets come from
// different files), so it is not annotatable — the store enforces that.
import { parseXml } from "../xml/parse";
import { detectLanguage } from "../lang/registry";
import { inlineText } from "../render/inlines";
import type { Block, RenderedDoc, Inline } from "../render/model";
import type { MapModel } from "./model";
import { mapHrefs } from "./model";

/** Provides the XML text for a referenced topic href, or null if unavailable. */
export type TopicProvider = (href: string) => Promise<string | null>;

function titleInline(text: string): Inline[] {
  return [{ kind: "text", text, srcStart: 0 }];
}

function placeholder(href: string): Block {
  return {
    kind: "note", id: `missing-${href}`, src: { start: 0, end: 0 },
    noteType: "warning", label: "Unresolved",
    inlines: titleInline(`Topic not resolved: ${href} (only available in the desktop app).`),
  };
}

export async function buildMergedDoc(map: MapModel, provide: TopicProvider): Promise<RenderedDoc> {
  const blocks: Block[] = [];
  const outline: { id: string; text: string; level: number }[] = [];

  for (const href of mapHrefs(map.nodes)) {
    const id = `topic-${href.replace(/[^\w.-]/g, "_")}`;
    let buffer: string | null = null;
    try { buffer = await provide(href); } catch { buffer = null; }
    if (!buffer) { blocks.push(placeholder(href)); continue; }
    try {
      const tree = parseXml(buffer);
      const { profile } = detectLanguage(tree, buffer);
      const doc = profile.buildRendered(tree, buffer);
      const titleText = doc.title ? inlineText(doc.title) : href;
      blocks.push({ kind: "heading", level: 2, id, src: { start: 0, end: 0 }, inlines: doc.title ?? titleInline(href) });
      outline.push({ id, text: titleText, level: 1 });
      blocks.push(...doc.blocks);
    } catch {
      blocks.push(placeholder(href));
    }
  }

  return { title: titleInline(map.title), subtitle: titleInline("Resolved publication — all topics merged"), blocks, outline };
}
