import { useTranslation } from "react-i18next";

export function Architecture() {
  const { t } = useTranslation();
  const steps = (t("arch.steps", { returnObjects: true }) as string[]) ?? [];

  return (
    <>
      <div className="page-header">
        <h1>{t("routes.architecture.title")}</h1>
        <p>{t("routes.architecture.sub")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("arch.title")}</h2>
        <div className="grid-2">
          <div className="arch-split">
            <div className="label brand-color">{t("arch.backend")}</div>
            <div>{t("arch.backendBody")}</div>
          </div>
          <div className="arch-split">
            <div className="label accent-color">{t("arch.frontend")}</div>
            <div>{t("arch.frontendBody")}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">{t("arch.workflowTitle")}</h2>
        <div className="arch-flow">
          {steps.map((step, i) => (
            <div className="arch-step" key={i}>
              <span className="step-n">{i + 1}.</span>
              <span>{step}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
