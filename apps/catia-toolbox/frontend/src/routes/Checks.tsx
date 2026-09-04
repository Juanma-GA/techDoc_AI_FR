import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiClientError, checksApi, exportUrl, type CheckResultDto, type CheckRunDto } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

function sevVariant(severity: string): "danger" | "warn" | "info" {
  if (severity === "danger") return "danger";
  if (severity === "info") return "info";
  return "warn";
}

export function Checks() {
  const { t } = useTranslation();
  const { importId } = useWorkspace();
  const [maxDepth, setMaxDepth] = useState(6);
  const [run, setRun] = useState<CheckRunDto | null>(null);
  const [results, setResults] = useState<CheckResultDto[]>([]);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const r = await checksApi.run(importId as string, { max_depth: maxDepth });
      const res = await checksApi.results(r.id);
      return { r, res };
    },
    onSuccess: ({ r, res }) => {
      setError(null);
      setRun(r);
      setResults(res);
    },
    onError: (e) => {
      setError(e instanceof ApiClientError ? e.message : String(e));
    },
  });

  if (!importId) {
    return (
      <div className="empty-state">
        <h3 className="card-title">{t("checks.noImport")}</h3>
        <p className="hint">{t("tree.noImportDesc")}</p>
      </div>
    );
  }

  return (
    <div className="form" style={{ maxWidth: "56rem" }}>
      <article className="card">
        <h2 className="card-title">{t("checks.runTitle")}</h2>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field">
            <span className="field-label">{t("checks.maxDepth")}</span>
            <input
              type="number"
              className="input"
              min={1}
              max={20}
              value={maxDepth}
              onChange={(e) => setMaxDepth(Number(e.target.value) || 6)}
              style={{ width: "6rem" }}
            />
          </label>
          <button type="button" className="btn primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {t("checks.run")}
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </article>

      <article className="card">
        {run ? (
          <div className="form">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 className="card-title">{t("checks.resultTitle", { count: results.length })}</h2>
              <a href={exportUrl.checksCsv(run.id)}>
                <button type="button" className="btn secondary small">
                  {t("common.exportCsv")}
                </button>
              </a>
            </div>
            {results.length ? (
              <ul className="item-list">
                {results.map((r) => (
                  <li key={r.id} className="item-row">
                    <span className={`badge ${sevVariant(r.severity)}`}>{r.rule}</span>
                    <div className="item-main">
                      <span className="item-name">{r.rel_path || "(global)"}</span>
                      <span className="item-meta">{r.message}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hint">{t("checks.none")}</p>
            )}
          </div>
        ) : (
          <p className="hint">{t("checks.runTitle")}.</p>
        )}
      </article>
    </div>
  );
}
