import { Ruler } from "lucide-react";
import { useTranslation } from "react-i18next";

export function UnitChip() {
  const { t } = useTranslation();
  return (
    <span className="inline-flex items-center gap-1 rounded-sm bg-accent-teal/15 px-2 py-0.5 text-[0.65rem] font-mono uppercase tracking-wider text-accent-teal ring-1 ring-accent-teal/40">
      <Ruler size={11} aria-hidden="true" />
      {t("reviewer.suggestion.type.units")}
    </span>
  );
}
