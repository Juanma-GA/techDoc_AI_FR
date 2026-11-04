import { z } from "zod";
import { reviewDestinations } from "./preliminaryTypes";
import type { PreliminaryState } from "./preliminaryTypes";
import type { TreeNode, WizardState } from "./wizardTypes";
import { validationViolationSchema as violation } from "./validationSchema";

const optionalText = z.string().nullish().transform((value) => value ?? undefined);
export const treeSchema: z.ZodType<TreeNode, z.ZodTypeDef, unknown> = z.lazy(() => z.object({
  id: z.string(), kind: z.string(), text: z.string().default(""),
  context: z.string().default("unknown"), confidence: z.number().nullable().default(1),
  candidates: z.array(z.object({
    element: z.string(), score: z.number().nullish().transform((value) => value ?? undefined),
    rationale: z.string().optional(),
  }).passthrough()).default([]),
  children: z.array(treeSchema).default([]),
  level: z.number().nullable().optional(), page: z.number().nullable().optional(),
  zone: z.string().optional(), icn: z.string().nullable().optional(),
  table_header: z.array(z.string()).nullable().optional(),
  refs: z.array(z.object({
    kind: z.string(), target: optionalText, target_kind: optionalText, text: optionalText,
  }).passthrough()).nullable().optional(),
}).passthrough());

const preliminarySchema: z.ZodType<PreliminaryState, z.ZodTypeDef, unknown> = z.object({
  revision: z.number().int(), active_dm_id: z.string().nullable(),
  source_format: z.string(), source_changed: z.boolean(),
  reviews: z.record(z.object({
    fingerprint: z.string(), rules_revision: z.number().optional(),
    status: z.enum(["pending", "reviewed", "skipped", "stale"]),
    partial: z.boolean().optional(),
    saved_at: z.string().nullable(),
    position: z.object({ page: z.number(), scroll_top: z.number(), selected_id: z.string().nullable() }),
    passages: z.array(z.object({
      id: z.string(), node_id: z.string(), row: z.number().nullable(),
      start: z.number(), end: z.number(), source_text: z.string(), text: z.string(),
      page: z.number().nullable(), kind: z.string(),
      role: z.enum(["content", "heading", "table-header", "marker", "layout", "caption"]).optional(),
      phase: z.enum(["unknown", "preliminary", "main", "common", "closing"]).optional(),
      suggested: z.enum([...reviewDestinations, "review"]),
      rule: z.enum(["keywords", "heading", "multiple", "unmatched", "main", "closing", "common",
        "action", "structure", "admonition"]),
      decision: z.enum(reviewDestinations).nullable(),
    }).passthrough()),
  }).passthrough()),
}).passthrough();
const snippet = z.object({
  text: z.string(), page: z.number().nullable(), kind: z.string(), zone: optionalText,
}).passthrough();
const preview = z.object({ head: z.array(snippet), tail: z.array(snippet), total: z.number() });
const step = z.enum(["dmrl", "split", "type", "structure", "preliminary", "generate"]);
const dmType = z.enum(["descriptive", "procedural", "ipd"]);
export const wizardStateSchema: z.ZodType<WizardState, z.ZodTypeDef, unknown> = z.object({
  step, split_level: z.enum(["chapter", "section", "subsection"]), steps: z.array(step).optional(),
  dmrl_dm_count: z.number().optional(), can_undo: z.boolean().optional(),
  has_brex_profile: z.boolean().optional(), illustration_errors: z.number().optional(),
  dms: z.array(z.object({
    dm_id: z.string(), title: z.string(), dm_type: dmType, node_count: z.number(),
    dmc: z.string().optional(), is_orphan: z.boolean().optional(),
    tree: treeSchema.nullish().transform((value) => value ?? undefined),
    preview: preview.nullish().transform((value) => value ?? undefined),
    violation_count: z.number().optional(), has_xml: z.boolean().optional(),
    missing_fields: z.array(z.string()).optional(),
    xsd_valid: z.boolean().nullish().transform((value) => value ?? undefined),
    xsd_violations: z.array(violation).optional(), brex_violations: z.array(violation).optional(),
    cir_unresolved: z.array(z.string()).optional(),
  }).passthrough()),
  resources: z.object({
    dmrl_count: z.number(), has_cir: z.boolean(), has_brex_rules: z.boolean(),
    has_dm_header: z.boolean(), errors: z.array(z.string()).optional(),
  }).passthrough().nullish().transform((value) => value ?? undefined),
  dmrl: z.array(z.object({
    index: z.number(), arbo: z.string(), dmc: z.string(), title: z.string(), dm_type: z.string(),
    dmrl_type: z.string().optional(), info_code: z.string().optional(),
    info_code_schema: z.string().optional(), info_code_dm_type: z.string().optional(),
    type_conflict: z.boolean().optional(),
    type_issue: z.enum(["", "missing_info_code", "unmapped_info_code", "unsupported_schema"]).optional(),
    icn: z.string().optional(), is_pm_title: z.boolean().optional(), matched: z.boolean(),
    match_rank: z.enum(["", "exact", "prefix", "contains"]), page: z.number().nullable(),
    matched_text: z.string(),
  }).passthrough()).nullish().transform((value) => value ?? undefined),
  preliminary: preliminarySchema.nullish().transform((value) => value ?? undefined),
}).passthrough().superRefine((state, context) => {
  if (state.step === "preliminary" && !state.preliminary) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["preliminary"], message: "Missing procedural review." });
  }
  if (state.step === "dmrl" && !state.dmrl) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["dmrl"], message: "Missing DMRL review." });
  }
  state.dms.forEach((dm, index) => {
    if (state.step === "structure" && !dm.tree) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["dms", index, "tree"], message: "Missing structure tree." });
    }
    if (state.step === "generate" &&
        (dm.has_xml === undefined || dm.xsd_valid === undefined || dm.missing_fields === undefined)) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["dms", index], message: "Missing generation diagnostics." });
    }
  });
});

export const parseWizardState = (value: unknown) => wizardStateSchema.parse(value);
export const parsePmcResult = (value: unknown) => z.object({
  document_id: z.string(), entries: z.number().int().nonnegative(), pmc: z.string(),
}).passthrough().parse(value);
