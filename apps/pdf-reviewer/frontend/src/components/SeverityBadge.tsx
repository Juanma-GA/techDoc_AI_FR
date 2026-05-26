import { useTranslation } from "react-i18next";

import type { Severity } from "../types/domain";

const STYLES: Record<Severity, string> = {
  error: "bg-danger/15 text-danger ring-1 ring-danger/40",
  warning: "bg-warning/15 text-warning ring-1 ring-warning/40",
  info: "bg-info/15 text-info ring-1 ring-info/40",
};

type Props = { severity: Severity };

export function SeverityBadge({ severity }: Props) {
  const { t } = useTranslation();
  return (
    <span
      className={[
        "inline-flex items-center rounded-sm px-2 py-0.5 text-[0.65rem] font-mono uppercase tracking-wider",
        STYLES[severity],
      ].join(" ")}
    >
      {t(`reviewer.suggestion.severity.${severity}`)}
    </span>
  );
}
