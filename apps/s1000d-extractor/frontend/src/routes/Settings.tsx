import { useTranslation } from "react-i18next";
import { PageHeader } from "@internal/ui";

import { DemoModeSettings } from "../components/DemoModeSettings";
import { PreliminaryRulesSettings } from "../components/business/PreliminaryRulesSettings";

export function Settings() {
  const { t } = useTranslation();

  return (
    <>
      <PageHeader title={t("settings.title")} description={t("settings.subtitle")} />

      <div className="space-y-6" data-testid="settings-sections">
        <DemoModeSettings />
        <PreliminaryRulesSettings />
      </div>
    </>
  );
}
