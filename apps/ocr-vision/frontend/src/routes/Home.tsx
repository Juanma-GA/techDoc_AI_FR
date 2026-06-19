import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { healthApi, type HealthDto } from "../lib/api";

export function Home() {
  const { t } = useTranslation();
  const { data: health } = useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.read,
  });

  return (
    <>
      <div className="page-header">
        <h1>{t("routes.home.title")}</h1>
        <p>{t("routes.home.sub")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("home.title")}</h2>
        <p>{t("home.bodyIntro")}</p>
        <ul>
          <li>
            <code>backend/app/api/</code> &mdash; {t("home.editApi")}
          </li>
          <li>
            <code>backend/app/db/models.py</code> &mdash; {t("home.editModels")}
          </li>
          <li>
            <code>frontend/src/routes/</code> &mdash; {t("home.editRoutes")}
          </li>
        </ul>
        <div className="banner">
          {t("home.statusBackend")} :{" "}
          {health ? (
            <span className="badge ok">{health.status}</span>
          ) : (
            <span className="badge warn">{t("home.statusUnknown")}</span>
          )}
          {health ? (
            <>
              {" · "}
              {t("home.statusLlm")} : <span className="badge">{health.llm}</span>
              {" · "}
              {t("home.statusVersion")} : <code>{health.version}</code>
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}
