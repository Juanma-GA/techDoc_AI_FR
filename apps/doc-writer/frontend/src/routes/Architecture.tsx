import { useTranslation } from "react-i18next";

// Onglet Architecture, rendu pixel-identique au preview (classes .card /
// .arch-split / .arch-flow / .arch-step de preview-skin.css).
export function Architecture() {
  const { t } = useTranslation();
  const steps = (t("architecture.steps", { returnObjects: true }) as string[]) ?? [];

  return (
    <>
      <div className="page-header">
        <h1>{t("architecture.title")}</h1>
        <p>{t("architecture.subtitle")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("architecture.stackTitle")}</h2>
        <div className="grid-2">
          <div className="arch-split">
            <div className="label brand-color">{t("architecture.backend")}</div>
            <div>{t("architecture.backendBody")}</div>
          </div>
          <div className="arch-split">
            <div className="label accent-color">{t("architecture.frontend")}</div>
            <div>{t("architecture.frontendBody")}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">{t("architecture.workflowTitle")}</h2>
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
