import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  colorizationApi,
  exportUrl,
  type ColorizationItemDto,
  type ColorizationRunDto,
  type DiffRunDto,
} from "../lib/api";
import { useWorkspace } from "../stores/workspace";

export function Colorization() {
  const { t } = useTranslation();
  const { importId } = useWorkspace();
  const [strategy, setStrategy] = useState("by_type");
  const [diffRunId, setDiffRunId] = useState("");
  const [run, setRun] = useState<ColorizationRunDto | null>(null);
  const [items, setItems] = useState<ColorizationItemDto[]>([]);
  const [error, setError] = useState<string | null>(null);

  const diffsQuery = useQuery<DiffRunDto[]>({
    queryKey: ["diffs", importId],
    queryFn: () => colorizationApi.diffs(importId as string),
    enabled: !!importId,
  });

  const mutation = useMutation({
    mutationFn: async () => {
      const body = strategy === "by_change" ? { strategy, diff_run_id: diffRunId } : { strategy };
      const r = await colorizationApi.run(importId as string, body);
      const it = await colorizationApi.items(r.id);
      return { r, it };
    },
    onSuccess: ({ r, it }) => {
      setError(null);
      setRun(r);
      setItems(it);
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  if (!importId) {
    return (
      <div className="empty-state">
        <h3 className="card-title">{t("colorization.noImport")}</h3>
        <p className="hint">{t("tree.noImportDesc")}</p>
      </div>
    );
  }

  const textOn = (r: number, g: number, b: number) =>
    (r * 299 + g * 587 + b * 114) / 1000 > 140 ? "black" : "white";

  const diffs = diffsQuery.data ?? [];
  const stratOptions = [
    { value: "by_type", label: t("colorization.byType") },
    { value: "by_depth", label: t("colorization.byDepth") },
    { value: "by_change", label: t("colorization.byChange") },
  ];

  return (
    <div className="form" style={{ maxWidth: "56rem" }}>
      <article className="card">
        <h2 className="card-title">{t("colorization.runTitle")}</h2>
        <p className="banner warn">
          <strong>{t("export.dryRunTitle")}</strong> {t("colorization.dryRun")}
        </p>
        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
          <label className="field grow">
            <span className="field-label">{t("colorization.strategy")}</span>
            <select className="input" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
              {stratOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          {strategy === "by_change" ? (
            <label className="field grow">
              <span className="field-label">{t("colorization.comparison")}</span>
              <select
                className="input"
                value={diffRunId || diffs[0]?.id || ""}
                onChange={(e) => setDiffRunId(e.target.value)}
              >
                {(diffs.length
                  ? diffs.map((d) => ({ value: d.id, label: `${t("nav.diff")} ${d.id.slice(0, 8)}` }))
                  : [{ value: "", label: t("colorization.noDiff") }]
                ).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <button
            type="button"
            className="btn primary"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || (strategy === "by_change" && !diffs.length)}
          >
            {t("colorization.run")}
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </article>

      {run ? (
        <article className="card">
          <h2 className="card-title">{t("colorization.resultTitle", { count: items.length })}</h2>
          <div className="row" style={{ flexWrap: "wrap", marginBottom: "0.75rem" }}>
            <a href={exportUrl.colorizationCsv(run.id)}>
              <button type="button" className="btn secondary small">{t("common.exportCsv")}</button>
            </a>
            <a href={exportUrl.colorizationComposer(run.id)}>
              <button type="button" className="btn secondary small">{t("colorization.composerScript")}</button>
            </a>
            <a href={exportUrl.colorizationMacro(run.id)}>
              <button type="button" className="btn secondary small">{t("colorization.macro")}</button>
            </a>
            <a href={exportUrl.colorizationSvg(run.id)} target="_blank" rel="noreferrer">
              <button type="button" className="btn secondary small">{t("colorization.svg")}</button>
            </a>
          </div>

          {/* Simulation : chaque piece dans sa couleur attribuee. */}
          <p className="hint">{t("colorization.simulation")}</p>
          <div className="grid-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(10rem, 1fr))" }}>
            {items.map((it) => (
              <div
                key={it.id}
                style={{
                  overflow: "hidden",
                  borderRadius: "4px",
                  padding: "0.5rem",
                  fontSize: "0.75rem",
                  backgroundColor: `rgb(${it.color_r}, ${it.color_g}, ${it.color_b})`,
                  color: textOn(it.color_r, it.color_g, it.color_b),
                }}
                title={it.rel_path}
              >
                <div className="label" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {it.rel_path.split("/").pop()}
                </div>
                <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", opacity: 0.8 }}>
                  {it.reason}
                </div>
              </div>
            ))}
          </div>
        </article>
      ) : null}
    </div>
  );
}
