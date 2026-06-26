import { useTranslation } from "react-i18next";

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
      <RulesCatalogCard />
    </>
  );
}
