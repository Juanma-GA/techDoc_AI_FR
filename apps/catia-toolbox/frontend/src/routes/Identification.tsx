import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  exportUrl,
  identificationApi,
  type NomenclatureItemDto,
  type NomenclatureMapping,
  type NomenclaturePreviewDto,
  type NomenclatureRunDto,
} from "../lib/api";
import { FilePicker } from "../components/FilePicker";
import { useWorkspace } from "../stores/workspace";

const NOMEN_EXTS = [".xlsm", ".xlsx"];

// Champs de mapping exposes : SIN, Designation, Piece remplacee, OLD/NEW P/N,
// OLD/NEW REV, Ref Couleur. Aucun n'est individuellement obligatoire, mais il
// faut au moins une colonne d'identite (SIN ou OLD/NEW P/N).
const MAPPING_FIELDS: { field: keyof NomenclatureMapping; labelKey: string; required: boolean }[] = [
  { field: "sin", labelKey: "identification.fieldSin", required: false },
  { field: "designation", labelKey: "identification.fieldDesignation", required: false },
  { field: "replaced", labelKey: "identification.fieldReplaced", required: false },
  { field: "old_pn", labelKey: "identification.fieldOldPn", required: false },
  { field: "new_pn", labelKey: "identification.fieldNewPn", required: false },
  { field: "old_rev", labelKey: "identification.fieldOldRev", required: false },
  { field: "new_rev", labelKey: "identification.fieldNewRev", required: false },
  { field: "color_ref", labelKey: "identification.fieldColorRef", required: false },
];

// Colonnes qui suffisent a identifier une piece (au moins une requise).
const IDENTITY_FIELDS: (keyof NomenclatureMapping)[] = ["sin", "old_pn", "new_pn"];

// Registre des colonnes affichables (cle = cle backend du mapping). Le tableau
// n'affiche QUE les colonnes reellement mappees (summary.detected_columns).
// L'ordre ci-dessous est l'ordre d'affichage.
type ColDef = {
  key: string;
  labelKey: string;
  center?: boolean;
  render: (it: NomenclatureItemDto, tr: (k: string) => string) => ReactNode;
};
const COLUMN_DEFS: ColDef[] = [
  { key: "catpart", labelKey: "identification.colCatpart", render: (it) => it.catpart },
  { key: "designation", labelKey: "identification.colDesignation", render: (it) => it.designation },
  { key: "sin", labelKey: "identification.colSin", render: (it) => it.sin },
  { key: "version", labelKey: "identification.colVersion", render: (it) => it.version },
  {
    key: "replaced",
    labelKey: "identification.colReplaced",
    center: true,
    render: (it, tr) => (it.replaced ? <span className="badge warn">{tr("common.yes")}</span> : null),
  },
  { key: "old_pn", labelKey: "identification.colOldPn", render: (it) => it.old_pn },
  { key: "new_pn", labelKey: "identification.colNewPn", render: (it) => it.new_pn },
  { key: "old_rev", labelKey: "identification.colOldRev", center: true, render: (it) => it.old_rev },
  { key: "new_rev", labelKey: "identification.colNewRev", center: true, render: (it) => it.new_rev },
  { key: "color_ref", labelKey: "identification.colColorRef", render: (it) => it.color_ref },
  { key: "materials", labelKey: "identification.colMateriaux", render: (it) => it.materials },
  { key: "color", labelKey: "identification.colColor", center: true, render: (it) => <ColorDot item={it} /> },
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

// Filtre par defaut selon les colonnes mappees : "Pieces remplacees" si dispo,
// sinon toutes les lignes.
function defaultFilter(columns: string[]): "all" | "replaced" | "color" {
  return columns.includes("replaced") ? "replaced" : "all";
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
  // Colonnes reellement mappees pour ce resultat : le tableau n'affiche QUE
  // celles-ci (strictement le contenu du mapping).
  const [resultColumns, setResultColumns] = useState<string[]>([]);
  // Filtres d'affichage : "Pieces remplacees" par defaut (champ de filtre choisi
  // via une liste deroulante), + avec couleur / toutes.
  type ItemFilter = "all" | "replaced" | "color";
  const [filter, setFilter] = useState<ItemFilter>("replaced");

  const runsQuery = useQuery<NomenclatureRunDto[]>({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
  });
  const runs = runsQuery.data ?? [];

  const itemsQuery = useQuery<NomenclatureItemDto[]>({
    queryKey: ["identification", resultRunId, "items", filter],
    queryFn: () =>
      identificationApi.items(resultRunId!, {
        replaced: filter === "replaced" ? true : undefined,
        hasColor: filter === "color" ? true : undefined,
      }),
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
          replaced: summaryNum(run.summary, "replaced"),
          mono: summaryNum(run.summary, "mono_color"),
        }),
      );
      setResultRunId(run.id);
      const cols = detectedColumns(run.summary);
      setResultColumns(cols);
      // Filtre par defaut sur "Pieces remplacees" quand la colonne est mappee,
      // sinon toutes les lignes.
      setFilter(defaultFilter(cols));
      void qc.invalidateQueries({ queryKey: ["identification"] });
    },
    onError: onMutationError(setNomenError),
  });

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

  const onAnalyzeMapping = () => {
    setNomenNotice(null);
    if (!IDENTITY_FIELDS.some((f) => mapping[f] !== undefined)) {
      setNomenError(t("identification.identityRequired"));
      return;
    }
    const body: NomenclatureMapping = { header_row: headerRow };
    for (const { field } of MAPPING_FIELDS) {
      const v = mapping[field];
      if (v !== undefined) body[field] = v;
    }
    analyzeMappingMutation.mutate(body);
  };

  // Nombre max de colonnes dans l'apercu (pour les selects de mapping).
  const ncols = preview ? preview.rows.reduce((m, r) => Math.max(m, r.length), 0) : 0;
  // Le mapping est "configure" des qu'au moins une colonne d'identite est choisie.
  const hasIdentity = IDENTITY_FIELDS.some((f) => mapping[f] !== undefined);

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
              className="btn primary"
              onClick={onPreview}
              disabled={previewMutation.isPending}
            >
              {previewMutation.isPending ? <span className="spinner" /> : null}
              <span>{t("identification.preview")}</span>
            </button>
            <span className="hint">{t("identification.previewHint")}</span>
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

              <div className="row" style={{ marginTop: 12 }}>
                <button
                  type="button"
                  className="btn primary"
                  onClick={onAnalyzeMapping}
                  disabled={analyzeMappingMutation.isPending || !hasIdentity}
                >
                  {analyzeMappingMutation.isPending ? <span className="spinner" /> : null}
                  <span>{t("identification.analyze")}</span>
                </button>
                {!hasIdentity ? (
                  <span className="hint">{t("identification.identityRequired")}</span>
                ) : null}
              </div>
            </div>
          ) : null}

          {/* ---- Resultat : items de la nomenclature (colonnes = mapping) ---- */}
          {resultRunId ? (
            <div style={{ marginTop: 16 }}>
              <div className="row" style={{ marginBottom: 8, alignItems: "flex-end" }}>
                <div className="field">
                  <label htmlFor="nomen-filter" className="field-label">
                    {t("identification.filterLabel")}
                  </label>
                  <select
                    id="nomen-filter"
                    className="input"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value as ItemFilter)}
                  >
                    <option value="all">{t("identification.all")}</option>
                    {resultColumns.includes("replaced") ? (
                      <option value="replaced">{t("identification.replacedOnly")}</option>
                    ) : null}
                    {resultColumns.includes("color") ? (
                      <option value="color">{t("identification.withColor")}</option>
                    ) : null}
                  </select>
                </div>
                <a
                  href={exportUrl.identificationCsv(
                    resultRunId,
                    filter === "replaced" ? { replaced: true } : undefined,
                  )}
                >
                  {t("common.exportCsv")}
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
                // ~15 lignes visibles puis scroll vertical ; scroll horizontal
                // quand les colonnes depassent la largeur.
                <div style={{ maxHeight: "30rem", overflow: "auto" }}>
                  <table className="tbl" style={{ whiteSpace: "nowrap" }}>
                    <thead>
                      <tr>
                        {COLUMN_DEFS.filter((c) => resultColumns.includes(c.key)).map((c) => (
                          <th
                            key={c.key}
                            style={{
                              position: "sticky",
                              top: 0,
                              background: "var(--bg-2)",
                              ...(c.center ? { textAlign: "center" } : {}),
                            }}
                          >
                            {t(c.labelKey)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((it) => (
                        <tr key={it.id}>
                          {COLUMN_DEFS.filter((c) => resultColumns.includes(c.key)).map((c) => (
                            <td key={c.key} style={c.center ? { textAlign: "center" } : undefined}>
                              {c.render(it, t)}
                            </td>
                          ))}
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

      {/* ---- Carte 2 : nomenclatures analysees ---------------------------- */}
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
                  <span className="badge warn">
                    {t("identification.badgeReplaced", { count: summaryNum(r.summary, "replaced") })}
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
                      const cols = detectedColumns(r.summary);
                      setResultColumns(cols);
                      setFilter(defaultFilter(cols));
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
