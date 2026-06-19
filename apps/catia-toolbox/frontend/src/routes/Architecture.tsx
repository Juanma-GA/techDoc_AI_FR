import { useTranslation } from "react-i18next";

export function Architecture() {
  const { t } = useTranslation();

  const steps = [t("architecture.step1"), t("architecture.step2"), t("architecture.step3"), t("architecture.step4")];

  return (
    <div className="flex flex-col gap-4">
      <article className="card">
        <h2 className="card-title">{t("architecture.title")}</h2>
        <div className="arch-split">
          <div>
            <div className="label brand-color">{t("architecture.backend")}</div>
            <p className="hint">{t("architecture.backendDesc")}</p>
          </div>
          <div>
            <div className="label brand-color">{t("architecture.frontend")}</div>
            <p className="hint">{t("architecture.frontendDesc")}</p>
          </div>
        </div>
      </article>

      <article className="card">
        <h2 className="card-title">{t("architecture.workflowTitle")}</h2>
        <div className="arch-flow">
          {steps.map((step, idx) => (
            <div key={idx} className="arch-step">
              <span className="step-n">{idx + 1}</span>
              <span>{step}</span>
            </div>
          ))}
        </div>
      </article>
    </div>
  );
}
