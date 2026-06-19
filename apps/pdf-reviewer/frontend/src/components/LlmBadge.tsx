import { useTranslation } from "react-i18next";

import { useHealth } from "../hooks/useHealth";

// Indicateur LLM du sidebar (.llm-status + .badge), regle CLAUDE.md #13.
// Vert (ON) seulement si cle effective + test reussi + interrupteur ON.
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
  const { data } = useHealth();
  const status = data?.llm;
  const badgeClass = status ? (BADGE_CLASS[status] ?? "badge warn") : "badge off";
  const label = status && LABEL_KEY[status] ? t(LABEL_KEY[status]) : "?";

  return (
    <div className="llm-status" title={t("llm.title")}>
      {t("llm.label")} <span className={badgeClass}>{label}</span>
    </div>
  );
}
