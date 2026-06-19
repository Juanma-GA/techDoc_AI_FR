import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";

const WORKFLOW_KEYS = ["f1", "f2", "f3", "f4", "f5", "f6"] as const;

export function Architecture(): JSX.Element {
  const { t } = useTranslation();

  return (
    <div>
      <PageHeader title={t("arch.title")} subtitle={t("arch.subtitle")} />

      <Card title={t("arch.split.title")}>
        <div className="grid-2">
          <div className="arch-split">
            <div className="label brand-color">{t("arch.split.backLabel")}</div>
            <p>{t("arch.split.back")}</p>
          </div>
          <div className="arch-split">
            <div className="label brand-color">{t("arch.split.frontLabel")}</div>
            <p>{t("arch.split.front")}</p>
          </div>
        </div>
      </Card>

      <Card title={t("arch.workflow")}>
        <div className="arch-flow">
          {WORKFLOW_KEYS.map((key, idx) => (
            <div key={key} className="arch-step">
              <span className="step-n">{idx + 1}</span>
              <span>{t(`arch.${key}`)}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Card({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <article className="card">
      <h2 className="card-title">{title}</h2>
      {children}
    </article>
  );
}
