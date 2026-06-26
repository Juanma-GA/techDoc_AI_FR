import { useTranslation } from "react-i18next";

import { RichText } from "../components/RichText";

// Onglet Architecture, rendu identique au preview (.card / .arch-split /
// .arch-flow / .arch-step). Les libelles backend (arch.*) contiennent des
// balises <code> ; rendues via RichText (whitelist de tags surs), plus de
// dangerouslySetInnerHTML.
export function Architecture() {
  const { t } = useTranslation();
  const steps = ["arch.f1", "arch.f2", "arch.f3", "arch.f4", "arch.f5", "arch.f6"];

  return (
    <>
      <div className="page-header">
        <h1>{t("nav.architecture")}</h1>
        <p>{t("page.architecture")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("arch.split.title")}</h2>
        <div className="grid-2">
          <div className="arch-split">
            <div className="label mb-1.5 text-brand-blue-light">BACKEND</div>
            <div><RichText text={t("arch.split.back")} /></div>
          </div>
          <div className="arch-split">
            <div className="label mb-1.5 text-accent-teal">FRONTEND</div>
            <div><RichText text={t("arch.split.front")} /></div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">{t("arch.flowTitle")}</h2>
        <div className="arch-flow">
          {steps.map((key, i) => (
            <div className="arch-step" key={key}>
              <span className="step-n">{i + 1}.</span>
              <span><RichText text={t(key)} /></span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
