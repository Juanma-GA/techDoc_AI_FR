import { Badge, type BadgeProps } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { useHealth } from "../hooks/useHealth";

// Vert (ON) seulement si cle effective + test reussi + interrupteur ON (regle #13).
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

export function LlmBadge({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  const { data } = useHealth();
  const status = data?.llm;
  const variant = status ? (VARIANT[status] ?? "warning") : "default";
  const label = status && LABEL_KEY[status] ? t(LABEL_KEY[status]) : "?";

  return (
    <div className="flex items-center justify-between gap-1 text-sm text-fg-dim" title={t("llm.title")}>
      {!compact && <span className="font-mono text-xs uppercase">{t("llm.label")}</span>}
      <Badge variant={variant} data-testid="llm-badge">
        {label}
      </Badge>
    </div>
  );
}
