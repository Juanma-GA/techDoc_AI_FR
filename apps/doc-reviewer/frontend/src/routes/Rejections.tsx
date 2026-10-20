import { useTranslation } from "react-i18next";

import { RejectionsSummaryCard } from "../components/RejectionsSummaryCard";
import { PageHeader } from "../components/PageHeader";

export function Rejections(): JSX.Element {
  const { t } = useTranslation();

  return (
    <div>
      <PageHeader title={t("data.rejects.title")} subtitle={t("data.rejects.subtitle")} />
      <RejectionsSummaryCard />
    </div>
  );
}