import { useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { ClientRule } from "./useClientConfig";

export type DocumentNormInfo = { code: string; label: string };

export type DocumentNorm = {
  detected_norm: string | null;
  default_norm: string | null;
  norms: DocumentNormInfo[];
  /** False when the norm of the document does not follow modified pages (S1000D). */
  page_revision_tracking: boolean;
};

export function useDocumentNorm(documentId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["document-norm", documentId],
    queryFn: () => api.get<DocumentNorm>(`/documents/${documentId}/norm`),
    enabled: Boolean(documentId) && enabled,
  });
}

/** Active verification rules per norm of the client bundle. */
export function activeRuleCounts(
  rules: ClientRule[],
  norms: DocumentNormInfo[],
): Record<string, number> {
  return Object.fromEntries(
    norms.map((norm) => [
      norm.code,
      rules.filter(
        (rule) => rule.scope === "verification" && rule.bundle_code === norm.code && rule.active,
      ).length,
    ]),
  );
}

/** The analysis would run nothing for the detected norm: the user has to choose. */
export function normNeedsChoice(
  detection: DocumentNorm | undefined,
  rules: ClientRule[] | undefined,
): boolean {
  if (!detection?.detected_norm || detection.norms.length < 2 || !rules) return false;
  return activeRuleCounts(rules, detection.norms)[detection.detected_norm] === 0;
}
