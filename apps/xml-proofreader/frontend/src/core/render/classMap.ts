// ============================================================
// DITA element vocabulary → presentation roles.
//
// Robustness to *any* DITA 1.3 specialization comes from resolving each
// element to its base type via @class (the specialization ancestry), with a
// generic-identifier (GI) fallback for raw, unvalidated files where @class
// (a DTD-defaulted attribute) may be absent. Unknown elements degrade
// gracefully rather than breaking the render.
// ============================================================

/** Render roles consumed by the viewer. */
export type BlockRole =
  | "doc-title"
  | "subtitle"
  | "heading"
  | "para"
  | "note"
  | "list"
  | "listitem"
  | "steps"
  | "step"
  | "table"
  | "figure"
  | "image"
  | "container"
  | "generic";

/** GI → base type, for files without @class defaults applied. */
export const GI_TO_BASE: Record<string, string> = {
  // structural roots & bodies
  topic: "topic/topic", concept: "topic/topic", task: "topic/topic",
  reference: "topic/topic", glossentry: "topic/topic",
  body: "topic/body", conbody: "topic/body", taskbody: "topic/body",
  refbody: "topic/body",
  // titles / descriptions
  title: "topic/title", shortdesc: "topic/shortdesc", abstract: "topic/abstract",
  // sections & containers
  section: "topic/section", example: "topic/example",
  context: "topic/section", result: "topic/section", prereq: "topic/section",
  postreq: "topic/section", refsyn: "topic/section",
  // blocks
  p: "topic/p", note: "topic/note", lq: "topic/lq",
  // lists
  ul: "topic/ul", ol: "topic/ol", sl: "topic/ul", li: "topic/li", sli: "topic/li",
  // task steps
  steps: "task/steps", "steps-unordered": "task/steps", step: "task/step",
  cmd: "task/cmd", info: "topic/p", substeps: "task/steps", substep: "task/step",
  // tables
  table: "topic/table", simpletable: "topic/simpletable",
  tgroup: "topic/tgroup", thead: "topic/thead", tbody: "topic/tbody",
  row: "topic/row", strow: "topic/strow", entry: "topic/entry", stentry: "topic/entry",
  // figures / media
  fig: "topic/fig", image: "topic/image",
  // inline
  ph: "topic/ph", xref: "topic/xref", term: "topic/term", keyword: "topic/keyword",
  b: "hi-d/b", i: "hi-d/i", u: "hi-d/u", sup: "hi-d/sup", sub: "hi-d/sub",
  codeph: "pr-d/codeph", uicontrol: "ui-d/uicontrol", cite: "topic/cite",
  q: "topic/q", tt: "hi-d/tt",
};

/** Base type → render role. */
export const BASE_ROLE: Record<string, BlockRole> = {
  "topic/title": "heading",
  "topic/shortdesc": "subtitle",
  "topic/abstract": "subtitle",
  "topic/p": "para",
  "topic/lq": "para",
  "topic/note": "note",
  "topic/ul": "list",
  "topic/ol": "list",
  "topic/li": "listitem",
  "task/steps": "steps",
  "task/step": "step",
  "topic/section": "container",
  "topic/example": "container",
  "topic/body": "container",
  "topic/table": "table",
  "topic/simpletable": "table",
  "topic/fig": "figure",
  "topic/image": "image",
};

/** Base types (and GIs) rendered inline rather than as blocks. */
export const INLINE_BASE = new Set<string>([
  "topic/ph", "topic/xref", "topic/term", "topic/keyword", "topic/cite",
  "topic/q", "hi-d/b", "hi-d/i", "hi-d/u", "hi-d/sup", "hi-d/sub", "hi-d/tt",
  "pr-d/codeph", "ui-d/uicontrol", "pr-d/apiname", "pr-d/parmname",
]);

export const INLINE_GI = new Set<string>([
  "ph", "xref", "term", "keyword", "cite", "q", "b", "i", "u", "sup", "sub",
  "tt", "codeph", "uicontrol", "apiname", "parmname", "wintitle", "menucascade",
  "varname", "filepath", "userinput", "systemoutput", "cmdname", "msgph",
]);
