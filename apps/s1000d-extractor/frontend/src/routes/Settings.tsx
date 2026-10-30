import { useTranslation } from "react-i18next";

import { DemoModeSettings } from "../components/DemoModeSettings";
import { PreliminaryRulesSettings } from "../components/business/PreliminaryRulesSettings";

export function Settings() {
  const { t } = useTranslation();

  return (
    <>
      <div className="page-header">
        <h1>{t("settings.title")}</h1>
        <p>{t("settings.subtitle")}</p>
      </div>

      <div className="space-y-6" data-testid="settings-sections">
        <DemoModeSettings />
        <PreliminaryRulesSettings />
      </div>
    </>
  );
}
