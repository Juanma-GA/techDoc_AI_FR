import { PageHeader } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { DemoModeSettings } from "./DemoModeSettings";

export function Settings() {
  const { t } = useTranslation();

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <PageHeader title={t("settings.title")} description={t("settings.subtitle")} />
      <DemoModeSettings />
    </div>
  );
}