import { LlmStatus } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { useHealth } from "../hooks/useHealth";

export function LlmBadge() {
  const { t } = useTranslation();
  const { data } = useHealth();

  return (
    <LlmStatus
      status={data?.llm}
      labels={{
        label: t("llm.label"),
        title: t("llm.title"),
        on: t("llm.on"),
        off: t("llm.off"),
        untested: t("llm.untested"),
        noKey: t("llm.noKey"),
      }}
    />
  );
}
