import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  exportUrl,
  identificationApi,
  type NomenclatureItemDto,
  type NomenclatureMapping,
  type NomenclaturePreviewDto,
  type NomenclatureRunDto,
  type ZipListDto,
} from "../lib/api";
import { FilePicker } from "../components/FilePicker";
import { useWorkspace } from "../stores/workspace";

const NOMEN_EXTS = [".xlsm", ".xlsx"];
const ZIP_EXTS = [".zip"];

// Champs de mapping (cle backend, cle i18n du libelle, obligatoire).
const MAPPING_FIELDS: { field: keyof NomenclatureMapping; labelKey: string; required: boolean }[] = [
  { field: "catpart", labelKey: "identification.fieldCatpart", required: true },
  { field: "sin", labelKey: "identification.fieldSin", required: false },
  { field: "version", labelKey: "identification.fieldVersion", required: false },
  { field: "to_treat", labelKey: "identification.fieldToTreat", required: false },
  { field: "color", labelKey: "identification.fieldColor", required: false },
  { field: "designation", labelKey: "identification.fieldDesignation", required: false },
];

function fileName(ref: string): string {
  return (ref || "").split(/[\\/]/).pop() ?? "";
}

function summaryNum(summary: Record<string, number | string[] | string>, key: string): number {
  const v = summary[key];
  return typeof v === "number" ? v : 0;
}

function detectedColumns(summary: Record<string, number | string[] | string>): string[] {
  const v = summary.detected_columns;
  return Array.isArray(v) ? v : [];
}

// Lettre de colonne tableur : 0 -> A, 1 -> B, 26 -> AA ...
function colLetter(idx: number): string {
  let s = "";
  let n = idx + 1;
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function colLabel(preview: NomenclaturePreviewDto, idx: number, headerRow: number): string {
  const hrow = preview.rows[headerRow - 1] ?? [];
  const name = (hrow[idx] == null ? "" : String(hrow[idx])).trim();
  return colLetter(idx) + (name ? ` - ${name}` : "");
}

/** Pastille de couleur affichee uniquement pour les pieces mono-couleur. */
function ColorDot({ item }: { item: NomenclatureItemDto }) {
  if (!item.mono_color) return null;
  const title = `${item.color_r},${item.color_g},${item.color_b}`;
  return (
    <span
      title={title}
      style={{
        display: "inline-block",
        height: 12,
        width: 12,
        borderRadius: 2,
        border: "1px solid var(--border)",
        verticalAlign: "middle",
        backgroundColor: `rgb(${item.color_r},${item.color_g},${item.color_b})`,
      }}
    />
  );
}

export function Identification() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  // ----- Carte nomenclature -------------------------------------------------
  // Chemin nomenclature memorise dans le workspace (pre-rempli au retour).
  const nomenPath = useWorkspace((s) => s.sources.nomenclature);
  const setNomenPath = (p: string) => useWorkspace.getState().setSource("nomenclature", p);
  const [nomenError, setNomenError] = useState<string | null>(null);
  const [nomenNotice, setNomenNotice] = useState<string | null>(null);

  const [preview, setPreview] = useState<NomenclaturePreviewDto | null>(null);
  const [sheet, setSheet] = useState("");
  const [headerRow, setHeaderRow] = useState(1);
  // mapping[field] = index de colonne ou undefined.
  const [mapping, setMapping] = useState<Record<string, number | undefined>>({});

  // Resultat (items de la nomenclature analysee).
  const [resultRunId, setResultRunId] = useState<string | null>(null);
  const [toTreatOnly, setToTreatOnly] = useState(false);

  // ----- Carte ZIP ----------------------------------------------------------
  const [zipPath, setZipPath] = useState("");
  const [zipError, setZipError] = useState<string | null>(null);
  const [zipNotice, setZipNotice] = useState<string | null>(null);

  const runsQuery = useQuery<NomenclatureRunDto[]>({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
  });
  const runs = runsQuery.data ?? [];

  const itemsQuery = useQuery<NomenclatureItemDto[]>({
    queryKey: ["identification", resultRunId, "items", toTreatOnly],
    queryFn: () => identificationApi.items(resultRunId!, toTreatOnly ? true : undefined),
    enabled: !!resultRunId,
  });
  const items = itemsQuery.data ?? [];

  const onMutationError = (setter: (m: string | null) => void) => (e: unknown) =>
    setter(e instanceof ApiClientError ? e.message : String(e));

  // Charge l'apercu (sheet optionnel) et initialise le mapping detecte.
  const previewMutation = useMutation({
    mutationFn: (s?: string) =>
      identificationApi.preview({ scope: "input", path: nomenPath.trim(), sheet: s, rows: 20 }),
    onSuccess: (data) => {
      setNomenError(null);
      setPreview(data);
      setSheet(data.sheet);
      const hr = data.header_row_detected > 0 ? data.header_row_detected : 1;
      setHeaderRow(hr);
      setMapping({ ...data.columns_map });
    },
    onError: onMutationError(setNomenError),
  });

  // Analyse rapide (sans mapping explicite) : "Analyser".
  const analyzeMutation = useMutation({
    mutationFn: () =>
      identificationApi.nomenclature({ scope: "input", path: nomenPath.trim(), sheet: sheet || undefined }),
    onSuccess: (run) => {
      setNomenError(null);
      setNomenNotice(
        t("identification.analyzed", {
          sheet: run.sheet,
          rows: summaryNum(run.summary, "rows"),
          toTreat: summaryNum(run.summary, "to_treat"),
          mono: summaryNum(run.summary, "mono_color"),
        }) +
          (detectedColumns(run.summary).length
            ? ` (${detectedColumns(run.summary).join(", ")})`
            : ""),
      );
      setResultRunId(run.id);
      setToTreatOnly(true);
      void qc.invalidateQueries({ queryKey: ["identification"] });
    },
    onError: onMutationError(setNomenError),
  });

  // Analyse avec le mapping de colonnes choisi : "Analyser avec ce mapping".
  const analyzeMappingMutation = useMutation({
    mutationFn: (body: NomenclatureMapping) =>
      identificationApi.nomenclature({
        scope: "input",
        path: nomenPath.trim(),
        sheet: sheet || undefined,
        mapping: body,
      }),
    onSuccess: (run) => {
      setNomenError(null);
      setNomenNotice(
        t("identification.analyzedShort", {
          rows: summaryNum(run.summary, "rows"),
          toTreat: summaryNum(run.summary, "to_treat"),
          mono: summaryNum(run.summary, "mono_color"),
        }),
      );
      setResultRunId(run.id);
      setToTreatOnly(false);
      void qc.invalidateQueries({ queryKey: ["identification"] });
    },
    onError: onMutationError(setNomenError),
  });

  const zipMutation = useMutation({
    mutationFn: () => identificationApi.zip({ scope: "input", path: zipPath.trim() }),
    onSuccess: (data) => {
      setZipError(null);
      setZipNotice(t("identification.zipDone", { count: data.count }));
    },
    onError: onMutationError(setZipError),
  });
  const zipResult: ZipListDto | undefined = zipMutation.data;

  const deleteMutation = useMutation({
    mutationFn: (id: string) => identificationApi.remove(id),
    onSuccess: (_d, id) => {
      if (resultRunId === id) setResultRunId(null);
      void qc.invalidateQueries({ queryKey: ["identification"] });
    },
  });

  // ----- Handlers nomenclature ---------------------------------------------
  const onPreview = () => {
    setNomenNotice(null);
    if (!nomenPath.trim()) {
      setNomenError(t("identification.pathRequired"));
      return;
    }
    previewMutation.mutate(sheet || undefined);
  };

  const onSheetChange = (s: string) => {
    setSheet(s);
    previewMutation.mutate(s);
  };

  const onAnalyze = () => {
    setNomenNotice(null);
    if (!nomenPath.trim()) {
      setNomenError(t("identification.pathRequired"));
      return;
    }
    analyzeMutation.mutate();
  };

  const onAnalyzeMapping = () => {
    setNomenNotice(null);
    if (mapping.catpart === undefined) {
      setNomenError(t("identification.catpartRequired"));
      return;
    }
    const body: NomenclatureMapping = { header_row: headerRow, catpart: mapping.catpart };
    for (const { field } of MAPPING_FIELDS) {
      if (field === "catpart") continue;
      const v = mapping[field];
      if (v !== undefined) body[field] = v;
    }
    analyzeMappingMutation.mutate(body);
  };

  const onZip = () => {
    setZipNotice(null);
    if (!zipPath.trim()) {
      setZipError(t("identification.pathRequired"));
      return;
    }
    zipMutation.mutate();
  };

  // Nombre max de colonnes dans l'apercu (pour les selects de mapping).
  const ncols = preview ? preview.rows.reduce((m, r) => Math.max(m, r.length), 0) : 0;

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      {/* ---- Carte 1 : analyse de la nomenclature .xlsm -------------------- */}
      <article className="card">
        <h2 className="card-title">{t("identification.nomenTitle")}</h2>
        <p className="banner info">{t("identification.nomenBanner")}</p>

        <div className="flex flex-col gap-3">
          <div>
            <label className="label">{t("identification.nomenFileLabel")}</label>
            <FilePicker exts={NOMEN_EXTS} value={nomenPath} onChange={setNomenPath} sheetPreview={false} />
          </div>

          <div className="row">
            <button
              type="button"
              className="btn secondary"
              onClick={onPreview}
              disabled={previewMutation.isPending}
            >
              {previewMutation.isPending ? <span className="spinner" /> : null}
              <span>{t("identification.preview")}</span>
            </button>
            <button
              type="button"
              className="btn primary"
              onClick={onAnalyze}
              disabled={analyzeMutation.isPending}
            >
              {analyzeMutation.isPending ? <span className="spinner" /> : null}
              <span>{t("identification.analyze")}</span>
            </button>
            {nomenNotice ? <span className="success">{nomenNotice}</span> : null}
            {nomenError ? <span className="error">{nomenError}</span> : null}
          </div>
        </div>

          {/* ---- Apercu / onglets + mapping ---- */}
          {preview ? (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="row" style={{ alignItems: "flex-end" }}>
                <div className="field">
                  <label htmlFor="nomen-sheet" className="field-label">
                    {t("identification.sheet")}
                  </label>
                  <select
                    id="nomen-sheet"
                    className="input"
                    value={sheet}
                    onChange={(e) => onSheetChange(e.target.value)}
                  >
                    {preview.sheets.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="nomen-headerrow" className="field-label">
                    {t("identification.headerRow")}
                  </label>
                  <select
                    id="nomen-headerrow"
                    className="input"
                    value={String(headerRow)}
                    onChange={(e) => setHeaderRow(parseInt(e.target.value, 10))}
                  >
                    {preview.rows.map((_r, i) => (
                      <option key={i} value={String(i + 1)}>
                        {String(i + 1)}
                      </option>
                    ))}
                  </select>
                </div>
                <span className="hint">
                  {t("identification.dataFromRow", { row: headerRow + 1 })}
                </span>
              </div>

              {/* Grille d'apercu */}
              <div style={{ maxHeight: 288, overflow: "auto", marginTop: 12 }}>
                <table className="preview-table">
                  <tbody>
                    {preview.rows.map((r, ri) => (
                      <tr key={ri} className={ri + 1 === headerRow ? "active" : ""}>
                        <td className="rownum">{ri + 1}</td>
                        {r.map((c, ci) => (
                          <td key={ci}>{c}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mapping des colonnes */}
              <p className="label" style={{ marginTop: 12, marginBottom: 8 }}>
                {t("identification.mappingTitle")}
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                  gap: 8,
                }}
              >
                {MAPPING_FIELDS.map(({ field, labelKey, required }) => {
                  const id = `nomen-map-${field}`;
                  const noneOption = required
                    ? []
                    : [{ value: "", label: t("identification.none") }];
                  const colOptions = Array.from({ length: ncols }, (_v, i) => ({
                    value: String(i),
                    label: colLabel(preview, i, headerRow),
                  }));
                  const current = mapping[field];
                  return (
                    <div key={field} className="field">
                      <label htmlFor={id} className="field-label">
                        {t(labelKey)}
                      </label>
                      <select
                        id={id}
                        className="input"
                        value={current === undefined ? "" : String(current)}
                        onChange={(e) =>
                          setMapping((m) => ({
                            ...m,
                            [field]: e.target.value === "" ? undefined : parseInt(e.target.value, 10),
                          }))
                        }
                      >
                        {[...noneOption, ...colOptions].map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>

              <div style={{ marginTop: 12 }}>
                <button
                  type="button"
                  className="btn primary"
                  onClick={onAnalyzeMapping}
                  disabled={analyzeMappingMutation.isPending}
                >
                  {analyzeMappingMutation.isPending ? <span className="spinner" /> : null}
                  <span>{t("identification.analyzeWithMapping")}</span>
                </button>
              </div>
            </div>
          ) : null}

          {/* ---- Resultat : items de la nomenclature ---- */}
          {resultRunId ? (
            <div style={{ marginTop: 16 }}>
              <div className="row" style={{ marginBottom: 8 }}>
                <button
                  type="button"
                  className="btn ghost small"
                  onClick={() => setToTreatOnly(false)}
                >
                  {t("identification.all")}
                </button>
                <button
                  type="button"
                  className="btn ghost small"
                  onClick={() => setToTreatOnly(true)}
                >
                  {t("identification.toTreat")}
                </button>
                <a href={exportUrl.identificationCsv(resultRunId, true)}>
                  {t("identification.exportToTreat")}
                </a>
                <span className="hint" style={{ marginLeft: "auto" }}>
                  {t("identification.lines", { count: items.length })}
                </span>
              </div>

              {itemsQuery.isLoading ? (
                <span className="spinner" />
              ) : itemsQuery.isError ? (
                <p className="error">
                  {itemsQuery.error instanceof Error
                    ? itemsQuery.error.message
                    : String(itemsQuery.error)}
                </p>
              ) : items.length ? (
                <div style={{ overflow: "auto" }}>
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>{t("identification.colCatpart")}</th>
                        <th>{t("identification.colSin")}</th>
                        <th>{t("identification.colVersion")}</th>
                        <th style={{ textAlign: "center" }}>
                          {t("identification.colToTreat")}
                        </th>
                        <th style={{ textAlign: "center" }}>
                          {t("identification.colColor")}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((it) => (
                        <tr key={it.id}>
                          <td>{it.catpart}</td>
                          <td>{it.sin}</td>
                          <td>{it.version}</td>
                          <td style={{ textAlign: "center" }}>
                            {it.to_treat ? (
                              <span className="badge ok">{t("common.yes")}</span>
                            ) : null}
                          </td>
                          <td style={{ textAlign: "center" }}>
                            <ColorDot item={it} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <h3 className="card-title">{t("identification.empty")}</h3>
                </div>
              )}
            </div>
          ) : null}
      </article>

      {/* ---- Carte 2 : donnees d'entree .zip ------------------------------- */}
      <article className="card">
        <h2 className="card-title">{t("identification.zipTitle")}</h2>
        <div className="flex flex-col gap-3">
          <div>
            <label className="label">{t("identification.zipFileLabel")}</label>
            <FilePicker exts={ZIP_EXTS} value={zipPath} onChange={setZipPath} />
          </div>
          <div className="row">
            <button
              type="button"
              className="btn secondary"
              onClick={onZip}
              disabled={zipMutation.isPending}
            >
              {zipMutation.isPending ? <span className="spinner" /> : null}
              <span>{t("identification.zipList")}</span>
            </button>
            {zipNotice ? <span className="success">{zipNotice}</span> : null}
            {zipError ? <span className="error">{zipError}</span> : null}
          </div>
        </div>

        {zipResult ? (
          <div style={{ marginTop: 12 }}>
            <p className="label" style={{ marginBottom: 8 }}>
              {t("identification.zipEntries", { count: zipResult.count })}
            </p>
            <div style={{ maxHeight: 288, overflow: "auto" }}>
              {zipResult.entries.slice(0, 50).map((e, i) => (
                <div key={i} className="label">
                  {e.name}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </article>

      {/* ---- Carte 3 : nomenclatures analysees ---------------------------- */}
      <article className="card">
        <h2 className="card-title">{t("identification.listTitle")}</h2>
        {runsQuery.isLoading ? (
          <span className="spinner" />
        ) : runs.length ? (
          <ul className="item-list">
            {runs.map((r) => (
              <li key={r.id} className="item-row">
                <span className="item-main grow" style={{ minWidth: 0 }}>
                  <span className="item-name">{fileName(r.source_ref)}</span>{" "}
                  <span className="badge info">
                    {t("identification.badgeLines", { count: summaryNum(r.summary, "rows") })}
                  </span>{" "}
                  <span className="badge ok">
                    {t("identification.badgeToTreat", { count: summaryNum(r.summary, "to_treat") })}
                  </span>{" "}
                  <span className="badge default">
                    {t("identification.badgeMono", { count: summaryNum(r.summary, "mono_color") })}
                  </span>
                </span>
                <span className="item-actions">
                  <button
                    type="button"
                    className="btn secondary small"
                    onClick={() => {
                      setResultRunId(r.id);
                      setToTreatOnly(false);
                    }}
                  >
                    {t("common.view")}
                  </button>
                  <button
                    type="button"
                    className="btn ghost small"
                    onClick={() => deleteMutation.mutate(r.id)}
                  >
                    {t("common.delete")}
                  </button>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty-state">
            <h3 className="card-title">{t("identification.empty")}</h3>
          </div>
        )}
      </article>
    </div>
  );
}
