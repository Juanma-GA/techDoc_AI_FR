// DITA 1.3 language profile. Detection by root element / @class / DOCTYPE.
// Rendering delegates to the existing DITA presentation builder, so behaviour
// is unchanged from before profiles were introduced.
import type { PosNode } from "../model/types";
import { buildRenderedDoc } from "../render/ditaModel";
import type { LanguageProfile, Detection, LinkPolicy, RefAttrDef } from "./profile";

const DITA_ROOTS = new Set([
  "concept", "task", "reference", "topic", "glossentry", "glossgroup", "dita",
  "map", "bookmap", "subjectScheme",
  "learningContent", "learningOverview", "learningSummary", "learningAssessment", "learningPlan",
]);

function doctype(buffer: string): string {
  const m = buffer.match(/<!DOCTYPE[^>]*>/i);
  return m ? m[0] : "";
}

const HREF_GIS = new Set(["xref", "link", "image", "topicref"]);

const ditaLinkPolicy: LinkPolicy = {
  refAttrsFor(gi: string): RefAttrDef[] {
    const defs: RefAttrDef[] = [
      { kind: "conref", attr: "conref" },
      { kind: "keyref", attr: "keyref" },
      { kind: "conkeyref", attr: "conkeyref" },
    ];
    if (HREF_GIS.has(gi)) defs.push({ kind: "href", attr: "href" });
    return defs;
  },
};

export const ditaProfile: LanguageProfile = {
  id: "dita-1.3",
  language: "DITA",
  detect(root: PosNode, buffer: string): Detection | null {
    const gi = root.name ?? "";
    const cls = root.classAttr ?? "";
    const dt = doctype(buffer);
    const isDita =
      DITA_ROOTS.has(gi) ||
      cls.includes("topic/") ||
      cls.includes("map/") ||
      /\bDITA\b/i.test(dt);
    if (!isDita) return null;
    return { language: "DITA", version: "1.3", profileId: "dita-1.3" };
  },
  buildRendered: (tree, buffer) => buildRenderedDoc(tree, buffer),
  linkPolicy: ditaLinkPolicy,
};
