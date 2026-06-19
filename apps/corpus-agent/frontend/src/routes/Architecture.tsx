import { useTranslation } from "react-i18next";

// Onglet Architecture, rendu identique au preview (.card / .arch-split /
// .arch-flow / .arch-step). Les libellés backend (arch.*) contiennent des
// balises <code> (clés data-i18n-html du preview) → rendu HTML de confiance.
export function Architecture() {
  const { t } = useTranslation();
  const html = (key: string) => ({ __html: t(key) });
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
            {/* eslint-disable-next-line react/no-danger -- i18n statique de confiance */}
            <div dangerouslySetInnerHTML={html("arch.split.back")} />
          </div>
          <div className="arch-split">
            <div className="label mb-1.5 text-accent-teal">FRONTEND</div>
            {/* eslint-disable-next-line react/no-danger -- i18n statique de confiance */}
            <div dangerouslySetInnerHTML={html("arch.split.front")} />
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">{t("arch.flowTitle")}</h2>
        <div className="arch-flow">
          {steps.map((key, i) => (
            <div className="arch-step" key={key}>
              <span className="step-n">{i + 1}.</span>
              {/* eslint-disable-next-line react/no-danger -- i18n statique de confiance */}
              <span dangerouslySetInnerHTML={html(key)} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
