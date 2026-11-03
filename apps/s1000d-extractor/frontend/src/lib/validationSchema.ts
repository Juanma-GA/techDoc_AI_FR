import { z } from "zod";

export const validationViolationSchema = z.object({
  severity: z.enum(["error", "warning", "info"]), rule: z.string(), message: z.string(),
  path: z.string().optional(), line: z.number().nullable().optional(),
  column: z.number().nullable().optional(), brex_rule_id: z.string().nullable().optional(),
  brex_severity_level: z.string().nullable().optional(),
}).passthrough();
export const validationResultSchema = z.object({
  filename: z.string(), dmc: z.string(), issue: z.string().nullable(), schema: z.string().nullable(),
  status: z.enum(["valid", "invalid", "needs_issue", "unverifiable"]), error_count: z.number(),
  message: z.string().nullable().optional(), violations: z.array(validationViolationSchema),
}).passthrough();
export const validationBatchSchema = z.object({ results: z.array(validationResultSchema) });
export const generatedValidationBatchSchema = z.object({
  results: z.array(validationResultSchema.extend({ dm_id: z.string() })),
});
