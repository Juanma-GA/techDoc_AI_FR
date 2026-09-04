import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Badge } from "@internal/ui";

import { healthApi, type HealthDto } from "../lib/api";

type LlmStatus = "ok" | "disabled" | "untested" | "not_configured";

const BADGE_VARIANT: Record<LlmStatus, "success" | "danger" | "warning" | "info"> = {
  ok: "success",
  disabled: "danger",
  untested: "warning",
  not_configured: "warning",
};

const LABEL_KEY: Record<LlmStatus, string> = {
  ok: "llm.on",
  disabled: "llm.off",
  untested: "llm.untested",
  not_configured: "llm.noKey",
};

export function llmBadgeVariant(status: LlmStatus): "success" | "danger" | "warning" | "info" {
  return BADGE_VARIANT[status];
}

export function llmBadgeLabelKey(status: LlmStatus): string {
  return LABEL_KEY[status];
}

/**
 * POC-specific LLM status badge.
 * Uses @internal/ui Badge component for consistent styling (Rule #3).
 */
export function LlmBadge() {
  const { t } = useTranslation();
  const { data } = useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.read,
    refetchInterval: 15_000,
  });
  const status = (data?.llm ?? "not_configured") as LlmStatus;
  const variant = llmBadgeVariant(status);
  const label = llmBadgeLabelKey(status) ? t(llmBadgeLabelKey(status)) : "?";

  return (
    <div className="flex flex-col items-start gap-2 p-4">
      <span className="text-sm font-medium text-muted-foreground">{t("llm.label")}</span>
      <Badge variant={variant} title={t("llm.title")}>
        {label}
      </Badge>
    </div>
  );
}
