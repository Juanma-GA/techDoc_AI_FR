import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { healthApi } from "../lib/api";
import type { HealthResponse } from "../lib/types";

// Indicateur LLM du sidebar, identique au preview (.llm-status + .badge).
const BADGE_CLASS: Record<string, string> = {
  ok: "badge ok",
  disabled: "badge off",
  untested: "badge warn",
  not_configured: "badge warn",
};
const LABEL_KEY: Record<string, string> = {
  ok: "llm.on",
  disabled: "llm.off",
  untested: "llm.untested",
  not_configured: "llm.noKey",
};

export function LlmBadge() {
  const { t } = useTranslation();
  const { data } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: healthApi.read,
    refetchInterval: 15_000,
  });
  const status = data?.llm;
  const badgeClass = status ? (BADGE_CLASS[status] ?? "badge warn") : "badge off";
  const label = status && LABEL_KEY[status] ? t(LABEL_KEY[status]) : "?";

  return (
    <div className="llm-status" title={t("llm.title")}>
      {t("llm.label")} <span className={badgeClass}>{label}</span>
    </div>
  );
}
