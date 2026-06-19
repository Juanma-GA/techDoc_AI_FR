import { Ruler } from "lucide-react";
import { useTranslation } from "react-i18next";

export function UnitChip() {
  const { t } = useTranslation();
  return (
    <span
      className="badge"
      style={{ color: "var(--accent-teal)", borderColor: "var(--accent-teal)", gap: 4 }}
    >
      <Ruler size={11} aria-hidden="true" />
      {t("reviewer.suggestion.type.units")}
    </span>
  );
}
