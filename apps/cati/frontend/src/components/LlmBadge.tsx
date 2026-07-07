import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Badge, type BadgeProps } from "@internal/ui";

import { healthApi, type HealthDto } from "../lib/api";

const VARIANT: Record<string, BadgeProps["variant"]> = {
  ok: "success",
  disabled: "default",
  untested: "warning",
  not_configured: "warning",
};
const LABEL_KEY: Record<string, string> = {
  ok: "llm.on",
  disabled: "llm.off",
  untested: "llm.untested",
  not_configured: "llm.noKey",
};

export function LlmBadge() {
  const { t } = useTranslation();
  const { data } = useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.read,
    refetchInterval: 15_000,
  });
  const status = data?.llm;
  const variant = status ? (VARIANT[status] ?? "warning") : "default";
  const label = status && LABEL_KEY[status] ? t(LABEL_KEY[status]) : "?";

  return (
    <div className="flex items-center gap-2" title={t("llm.title")}>
      <span className="label">{t("llm.label")}</span>
      <Badge variant={variant}>{label}</Badge>
    </div>
  );
}
