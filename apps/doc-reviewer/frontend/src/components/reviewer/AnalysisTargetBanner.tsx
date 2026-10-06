import { useTranslation } from "react-i18next";

import { useClientConfig } from "../../hooks/useClientConfig";
import { useFiltersStore } from "../../stores/filtersStore";

/**
 * Avertit quand aucune cible d'analyse n'est active (aucune norme, checklist
 * OFF, aucune unite) — le modele opt-in strict du backend (`rules_engine.
 * run_all`) ne fait alors tourner aucune regle, ce qui se traduit par une
 * analyse quasi instantanee et zero anomalie. Affiche dans le reviewer (ou la
 * liste) pour que ce ne soit jamais surprenant.
 */
export function AnalysisTargetBanner() {
  const { t } = useTranslation();
  const clientConfig = useClientConfig();
  const legacyChecklistActive = useFiltersStore((s) => s.checklistActive);
  const checklistActive =
    import.meta.env.VITE_LEGACY_RULES_UI === "true" && legacyChecklistActive;
  const targetUnits = useFiltersStore((s) => s.targetUnits);

  const hasActiveClientCatalog = (clientConfig.data?.catalogs.length ?? 0) > 0;
  const hasNoAnalysisTarget =
    !clientConfig.isLoading &&
    !hasActiveClientCatalog &&
    !checklistActive &&
    targetUnits.length === 0;

  if (!hasNoAnalysisTarget) return null;
  return <p className="banner warn">{t("documents.noAnalysisTarget")}</p>;
}
