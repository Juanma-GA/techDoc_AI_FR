import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";

export function Dashboard() {
  const { t } = useTranslation();
  return (
    <div className="px-8 py-6">
      <PageHeader
        title={t("routes.dashboard.title")}
        subtitle={t("routes.dashboard.subtitle")}
      />
      <div className="rounded-lg border bg-card p-8 text-center text-fg-dim shadow-card">
        {t("common.empty")}
      </div>
    </div>
  );
}
