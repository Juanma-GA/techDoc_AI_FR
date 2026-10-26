import { useTranslation } from "react-i18next";

import { ChecklistImportCard } from "../components/settings/ChecklistImportCard";
import { CustomRulesCard } from "../components/settings/CustomRulesCard";
import { DemoModeSettings } from "../components/settings/DemoModeSettings";
import { MistralForm } from "../components/settings/MistralForm";
import { SpecGenerateCard } from "../components/settings/SpecGenerateCard";

export function Settings() {
  const { t } = useTranslation();
  return (
    <>
      <div className="page-header">
        <h1>{t("nav.settings")}</h1>
        <p>{t("page.settings")}</p>
      </div>
      <DemoModeSettings />
      <MistralForm />
      <div className="settings-pair">
        <ChecklistImportCard />
        <SpecGenerateCard />
      </div>
      <CustomRulesCard />
    </>
  );
}
