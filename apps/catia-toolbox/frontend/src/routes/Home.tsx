import { useTranslation } from "react-i18next";

import { llmBadgeMeta, useHealth } from "../hooks/useHealth";

const LLM_BADGE_CLASS: Record<string, string> = {
  success: "ok",
  warning: "warn",
  danger: "danger",
  info: "info",
  default: "default",
};

export function Home() {
  const { t } = useTranslation();
  const { data: health } = useHealth();

  const steps = [t("home.step1"), t("home.step2"), t("home.step3"), t("home.step4")];
  const llm = llmBadgeMeta(health?.llm);

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <article className="card">
        <h2 className="card-title">{t("home.title")}</h2>
        <p className="hint">{t("home.subtitle")}</p>

        <ol className="mt-4 flex flex-col gap-2">
          {steps.map((s, i) => (
            <li
              key={i}
              className="item-row"
              style={{ borderLeft: "2px solid var(--brand)" }}
            >
              <span className="label">{i + 1}.</span>
              <span>{s}</span>
            </li>
          ))}
        </ol>

        <div className="row" style={{ marginTop: 16 }}>
          <span>{t("home.backendStatus")} :</span>
          {health ? (
            <span className="badge ok">{health.status}</span>
          ) : (
            <span className="badge warn">?</span>
          )}
          <span>&middot;</span>
          <span>LLM :</span>
          <span className={`badge ${LLM_BADGE_CLASS[llm.variant] ?? "default"}`}>{llm.label}</span>
          {health ? (
            <>
              <span>&middot;</span>
              <span className="label">v{health.version}</span>
            </>
          ) : null}
        </div>
      </article>
    </div>
  );
}
