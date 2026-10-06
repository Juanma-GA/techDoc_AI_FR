import { LlmStatus } from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { healthApi } from "../lib/api";
import type { HealthResponse } from "../lib/types";

export function LlmBadge() {
  const { t } = useTranslation();
  const { data } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: healthApi.read,
    refetchInterval: 15_000,
  });
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
