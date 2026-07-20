import { useTranslation } from "react-i18next";

import { ChecklistImportCard } from "../components/settings/ChecklistImportCard";
import { CustomRulesCard } from "../components/settings/CustomRulesCard";
import { MistralForm } from "../components/settings/MistralForm";
import { RulesCatalogCard } from "../components/settings/RulesCatalogCard";

export function Settings() {
  const { t } = useTranslation();
  return (
    <>
      <div className="page-header">
        <h1>{t("nav.settings")}</h1>
        <p>{t("page.settings")}</p>
      </div>
      <MistralForm />
      <ChecklistImportCard />
      <CustomRulesCard />
      <RulesCatalogCard />
    </>
  );
}
