import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  diffApi,
  exportUrl,
  identificationApi,
  importsApi,
  type DiffEntryDto,
  type DiffRunDto,
  type ImportDto,
  type NomenclatureCompareDto,
  type NomenclatureRunDto,
} from "../lib/api";

const CHANGE_VARIANT: Record<string, "ok" | "danger" | "warn"> = {
  added: "ok",
  removed: "danger",
  modified: "warn",
};

/** Onglet 1 : comparaison de deux dossiers importés (existant). */
function FoldersDiff() {
  const { t } = useTranslation();
  const importsQuery = useQuery<ImportDto[]>({ queryKey: ["imports"], queryFn: importsApi.list });
  const imports = importsQuery.data ?? [];
  const [base, setBase] = useState("");
  const [other, setOther] = useState("");
  const [run, setRun] = useState<DiffRunDto | null>(null);
  const [entries, setEntries] = useState<DiffEntryDto[]>([]);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const r = await diffApi.create(base || imports[0]!.id, other || imports[1]!.id);
      const e = await diffApi.entries(r.id);
      return { r, e };
    },
    onSuccess: ({ r, e }) => {
      setError(null);
      setRun(r);
      setEntries(e);
    },
    onError: (err) => setError(err instanceof ApiClientError ? err.message : String(err)),
  });

  if (imports.length < 2) {
    return (
      <div className="empty-state">
        <h3 className="card-title">{t("diff.needTwo")}</h3>
        <p className="hint">{t("diff.needTwoDesc")}</p>
      </div>
    );
  }

  const opts = imports.map((i) => ({ value: i.id, label: `${i.root_label} (${i.node_count})` }));

  return (
    <div className="form" style={{ maxWidth: "56rem" }}>
      <article className="card">
        <h2 className="card-title">{t("diff.compareTitle")}</h2>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field grow">
            <span className="field-label">{t("diff.base")}</span>
            <select className="input" value={base || opts[0]!.value} onChange={(e) => setBase(e.target.value)}>
              {opts.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <label className="field grow">
            <span className="field-label">{t("diff.other")}</span>
            <select className="input" value={other || opts[1]!.value} onChange={(e) => setOther(e.target.value)}>
              {opts.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <button type="button" className="btn primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {t("diff.compare")}
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </article>

      <article className="card">
        {run ? (
          <>
            <h2 className="card-title">{t("diff.resultTitle")}</h2>
            <div className="kpi-grid grid-2" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
              <div className="kpi">
                <span className="label">{t("diff.added")}</span>
                <span className="kpi-value">{run.summary.added ?? 0}</span>
              </div>
              <div className="kpi">
                <span className="label">{t("diff.removed")}</span>
                <span className="kpi-value">{run.summary.removed ?? 0}</span>
              </div>
              <div className="kpi">
                <span className="label">{t("diff.modified")}</span>
                <span className="kpi-value">{run.summary.modified ?? 0}</span>
              </div>
            </div>
            <a href={exportUrl.diffCsv(run.id)}>
              <button type="button" className="btn secondary small">
                {t("common.exportCsv")}
              </button>
            </a>
            {entries.length > 0 ? (
              <ul className="item-list">
                {entries.map((e) => (
                  <li key={e.id} className="item-row">
                    <span className={`badge ${CHANGE_VARIANT[e.change_type] ?? "default"}`}>{e.change_type}</span>
                    <div className="item-main">
                      <span className="item-name">{e.rel_path}</span>
                      {e.detail ? <span className="item-meta">{`— ${e.detail}`}</span> : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <h3 className="card-title">{t("diff.noDifference")}</h3>
              </div>
            )}
          </>
        ) : (
          <div className="empty-state">
            <h3 className="card-title">{t("diff.runPrompt")}</h3>
          </div>
        )}
      </article>
    </div>
  );
}

/** Onglet 2 : comparaison de deux nomenclatures (par SIN). */
function NomenclatureDiff() {
  const { t } = useTranslation();
  const runsQuery = useQuery<NomenclatureRunDto[]>({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
  });
  const runs = runsQuery.data ?? [];
  const [base, setBase] = useState("");
  const [other, setOther] = useState("");
  const [result, setResult] = useState<NomenclatureCompareDto | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => identificationApi.compare(base || runs[0]!.id, other || runs[1]!.id),
    onSuccess: (data) => {
      setError(null);
      setResult(data);
    },
    onError: (err) => setError(err instanceof ApiClientError ? err.message : String(err)),
  });

  if (runs.length < 2) {
    return (
      <div className="empty-state">
        <h3 className="card-title">{t("diff.nomenNeedTwo")}</h3>
        <p className="hint">{t("diff.nomenNeedTwoDesc")}</p>
      </div>
    );
  }

  const fileName = (ref: string) => (ref || "").split(/[\\/]/).pop() ?? ref;
  const opts = runs.map((r) => ({ value: r.id, label: fileName(r.source_ref) || r.id.slice(0, 8) }));
  const baseId = base || opts[0]!.value;
  const otherId = other || opts[1]!.value;

  return (
    <div className="form" style={{ maxWidth: "56rem" }}>
      <article className="card">
        <h2 className="card-title">{t("diff.nomenCompareTitle")}</h2>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field grow">
            <span className="field-label">{t("diff.nomenBase")}</span>
            <select className="input" value={baseId} onChange={(e) => setBase(e.target.value)}>
              {opts.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <label className="field grow">
            <span className="field-label">{t("diff.nomenOther")}</span>
            <select className="input" value={otherId} onChange={(e) => setOther(e.target.value)}>
              {opts.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <button type="button" className="btn primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {t("diff.compare")}
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </article>

      {result ? (
        <article className="card">
          <div className="row" style={{ marginBottom: 8 }}>
            <h2 className="card-title" style={{ margin: 0 }}>{t("diff.resultTitle")}</h2>
            <a href={exportUrl.nomenclatureCompareCsv(baseId, otherId)} style={{ marginLeft: "auto" }}>
              <button type="button" className="btn secondary small">{t("diff.exportCsv")}</button>
            </a>
          </div>
          <p className="hint">
            {t("diff.nomenSummary", {
              added: result.summary.added ?? 0,
              removed: result.summary.removed ?? 0,
              changed: result.summary.changed ?? 0,
            })}
          </p>

          <h3 className="label" style={{ marginTop: 12 }}>{t("diff.sinAdded")}</h3>
          <table className="tbl">
            <thead>
              <tr>
                <th>{t("diff.colSin")}</th>
                <th>{t("diff.colPn")}</th>
                <th>{t("diff.colDesignation")}</th>
              </tr>
            </thead>
            <tbody>
              {result.added_sin.map((e) => (
                <tr key={`a-${e.sin}`}>
                  <td>{e.sin}</td>
                  <td>{e.pn}</td>
                  <td>{e.designation}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 className="label" style={{ marginTop: 12 }}>{t("diff.sinRemoved")}</h3>
          <table className="tbl">
            <thead>
              <tr>
                <th>{t("diff.colSin")}</th>
                <th>{t("diff.colPn")}</th>
                <th>{t("diff.colDesignation")}</th>
              </tr>
            </thead>
            <tbody>
              {result.removed_sin.map((e) => (
                <tr key={`r-${e.sin}`}>
                  <td>{e.sin}</td>
                  <td>{e.pn}</td>
                  <td>{e.designation}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 className="label" style={{ marginTop: 12 }}>{t("diff.pnChanged")}</h3>
          <table className="tbl">
            <thead>
              <tr>
                <th>{t("diff.colSin")}</th>
                <th>{t("diff.colOldPn")}</th>
                <th>{t("diff.colDesignation")}</th>
              </tr>
            </thead>
            <tbody>
              {result.changed_pn.map((e) => (
                <tr key={`c-${e.sin}`}>
                  <td>{e.sin}</td>
                  <td>{e.old_pn}</td>
                  <td>{e.designation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      ) : (
        <article className="card">
          <div className="empty-state">
            <h3 className="card-title">{t("diff.runPrompt")}</h3>
          </div>
        </article>
      )}
    </div>
  );
}

export function Diff() {
  const { t } = useTranslation();
  // Focus sur la comparaison de nomenclatures (SIN / PN) par defaut.
  const [tab, setTab] = useState<"folders" | "nomenclatures">("nomenclatures");

  return (
    <div className="flex flex-col gap-4">
      <div className="row">
        <button
          type="button"
          className={`btn small ${tab === "folders" ? "secondary" : "ghost"}`}
          onClick={() => setTab("folders")}
        >
          {t("diff.tabFolders")}
        </button>
        <button
          type="button"
          className={`btn small ${tab === "nomenclatures" ? "secondary" : "ghost"}`}
          onClick={() => setTab("nomenclatures")}
        >
          {t("diff.tabNomenclatures")}
        </button>
      </div>
      {tab === "folders" ? <FoldersDiff /> : <NomenclatureDiff />}
    </div>
  );
}
