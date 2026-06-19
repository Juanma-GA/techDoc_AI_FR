import { useTranslation } from "react-i18next";

import type { Severity } from "../types/domain";

type Props = { severity: Severity };

export function SeverityBadge({ severity }: Props) {
  const { t } = useTranslation();
  return (
    <span className={`sev ${severity}`}>
      {t(`reviewer.suggestion.severity.${severity}`)}
    </span>
  );
}
