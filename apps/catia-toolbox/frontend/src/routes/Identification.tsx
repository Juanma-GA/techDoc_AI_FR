import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  exportUrl,
  identificationApi,
  type MonoCorpsResultDto,
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

// Mapping par defaut du gabarit, applique tant qu'aucun mapping n'a ete
// memorise : SIN en colonne B (index 1), Designation en colonne D (index 3).
const DEFAULT_MAPPING: Record<string, number> = { sin: 1, designation: 3 };

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
  {
    key: "mono_body",
    labelKey: "identification.colMonoBody",
    center: true,
    render: (it, tr) => (it.mono_body ? <span className="badge ok">{tr("common.yes")}</span> : null),
  },
  { key: "color", labelKey: "identification.colColor", center: true, render: (it) => <ColorDot item={it} /> },
];

// Colonnes affichees : les colonnes mappees + la colonne "mono_body" (drapeau
// renseigne par l'etape Mono-Corps, onglet Materiaux) toujours visible.
function displayColumns(columns: string[]): string[] {
  return [...columns, "mono_body"];
}

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

// La notion "remplacee" est filtrable des qu'une colonne dediee "Piece
// remplacee" est mappee, OU qu'OLD P/N + NEW P/N le sont (le backend derive
// alors replaced = old_pn != new_pn). Le cas courant en prod = OLD/NEW P/N.
function canFilterReplaced(columns: string[]): boolean {
  return (
    columns.includes("replaced") ||
    (columns.includes("old_pn") && columns.includes("new_pn"))
  );
}

// Filtre par defaut selon les colonnes mappees : "Pieces remplacees" si dispo,
// sinon toutes les lignes.
function defaultFilter(columns: string[]): "all" | "replaced" | "color" {
  return canFilterReplaced(columns) ? "replaced" : "all";
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

function detectFirstSlotColumn(preview: NomenclaturePreviewDto, headerRow: number): number | undefined {
  const header = preview.rows[headerRow - 1] ?? [];
  const column = header.findIndex((cell) => /^slot[\s_-]*1(?:\b|$)/.test(normalizedLabel(cell)));
  return column >= 0 ? column : undefined;
}

function normalizedLabel(value: unknown): string {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
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

// Champs d'identite pour relier une ligne "slots" a une piece.
type MonoIdentityField = "catpart" | "sin" | "old_pn" | "new_pn";

const MONO_IDENTITY_FIELDS: { field: MonoIdentityField; labelKey: string }[] = [
  { field: "catpart", labelKey: "identification.colCatpart" },
  { field: "sin", labelKey: "identification.colSin" },
  { field: "old_pn", labelKey: "identification.colOldPn" },
  { field: "new_pn", labelKey: "identification.colNewPn" },
];

/**
 * Etape Mono-Corps : onglet Materiaux separe. L'utilisateur choisit un onglet,
 * un champ d'identite, un nombre `n` de colonnes slots, puis mappe ces n
 * colonnes. Le backend calcule mono_body (1 valeur distincte parmi les slots)
 * et l'applique aux pieces du run par la valeur d'identite.
 */
function MonoCorpsCard({
  runId,
  sourcePath,
  runIdentityFields,
  runIdentityFieldsLoading,
}: {
  runId: string | null;
  sourcePath: string;
  runIdentityFields: string[];
  runIdentityFieldsLoading: boolean;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [path, setPath] = useState(sourcePath);
  const [preview, setPreview] = useState<NomenclaturePreviewDto | null>(null);
  const [sheet, setSheet] = useState("");
  const [headerRow, setHeaderRow] = useState(1);
  const [identityField, setIdentityField] = useState<MonoIdentityField>("sin");
  const [identityCol, setIdentityCol] = useState<number | undefined>(undefined);
  // 1re colonne Slot : comparee a toutes les colonnes suivantes.
  const [firstSlotCol, setFirstSlotCol] = useState<number | undefined>(undefined);
  const [result, setResult] = useState<MonoCorpsResultDto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    setPath(sourcePath);
    setPreview(null);
    setIdentityCol(undefined);
    setFirstSlotCol(undefined);
    setResult(null);
    setError(null);
    setNotice(null);
  }, [runId, sourcePath]);

  const previewMutation = useMutation({
    mutationFn: async (s?: string) => {
      if (s) {
        return identificationApi.preview({ scope: "input", path: path.trim(), sheet: s, rows: 20 });
      }
      const initial = await identificationApi.preview({
        scope: "input",
        path: path.trim(),
        rows: 20,
      });
      const materialsSheet = initial.sheets.find(
        (candidate) => normalizedLabel(candidate) === "materiaux",
      );
      return materialsSheet && materialsSheet !== initial.sheet
        ? identificationApi.preview({
            scope: "input",
            path: path.trim(),
            sheet: materialsSheet,
            rows: 20,
          })
        : initial;
    },
    onSuccess: (data) => {
      setError(null);
      setNotice(null);
      setPreview(data);
      setSheet(data.sheet);
      const detectedHeaderRow = data.header_row_detected > 0 ? data.header_row_detected : 1;
      setHeaderRow(detectedHeaderRow);
      const identityOrder = ["sin", "catpart", "old_pn", "new_pn"] as const;
      const detectedIdentityField = runId
        ? identityOrder.find((field) => runIdentityFields.includes(field)) ?? "sin"
        : identityOrder.find((field) => data.columns_map[field] !== undefined) ?? "sin";
      setIdentityField(detectedIdentityField);
      setIdentityCol(data.columns_map[detectedIdentityField]);
      setFirstSlotCol(detectFirstSlotColumn(data, detectedHeaderRow));
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  const analyzeMutation = useMutation({
    mutationFn: () =>
      identificationApi.monoCorps({
        path: path.trim(),
        sheet: sheet || undefined,
        header_row: headerRow,
        identity_field: identityField,
        identity_col: identityCol as number,
        // 1re colonne Slot : le backend compare de cette colonne a la derniere.
        first_slot_col: firstSlotCol as number,
        run_id: runId ?? undefined,
      }),
    onSuccess: (res) => {
      setError(null);
      setResult(res);
      const mono = Number(res.summary.mono) || 0;
      setNotice(
        res.summary.applied
          ? t("identification.monoDoneApplied", { mono, matched: Number(res.summary.matched) || 0 })
          : t("identification.monoDoneSolo", { mono, rows: Number(res.summary.rows) || 0 }),
      );
      if (res.summary.applied) void qc.invalidateQueries({ queryKey: ["identification"] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  const ncols = preview ? preview.rows.reduce((m, r) => Math.max(m, r.length), 0) : 0;
  const canAnalyze =
    !!path.trim() &&
    identityCol !== undefined &&
    firstSlotCol !== undefined &&
    (!runId || runIdentityFields.includes(identityField)) &&
    !previewMutation.isPending &&
    !previewMutation.isError;
  const monoItems = result?.items.filter((item) => item.mono_body) ?? [];
  const slotCount = monoItems.reduce((m, item) => Math.max(m, item.slots.length), 0);
  // Indices des colonnes slots reellement comparees (renseignes par le backend),
  // pour libeller les entetes du tableau resultat.
  const resultSlotCols = Array.isArray(result?.summary.slot_cols)
    ? (result.summary.slot_cols as number[])
    : [];
  const colOptions = Array.from({ length: ncols }, (_v, i) => ({
    value: String(i),
    label: preview ? colLabel(preview, i, headerRow) : String(i),
  }));
  const detectedIdentityCol =
    preview?.header_row_detected === headerRow ? preview.columns_map[identityField] : undefined;
  const needsIdentityColumnSelection = !!preview && detectedIdentityCol === undefined;
  const identityLabelKey =
    MONO_IDENTITY_FIELDS.find((option) => option.field === identityField)?.labelKey ??
    "identification.colSin";
  const identityLabel = t(identityLabelKey);
  const onPathChange = (nextPath: string) => {
    setPath(nextPath);
    setPreview(null);
    setSheet("");
    setHeaderRow(1);
    setIdentityCol(undefined);
    setFirstSlotCol(undefined);
    setResult(null);
    setError(null);
    setNotice(null);
  };

  return (
    <article className="card">
      <h2 className="card-title">{t("identification.monoTitle")}</h2>

      <div className="field">
        <label className="label">{t("identification.nomenFileLabel")}</label>
        <FilePicker exts={NOMEN_EXTS} value={path} onChange={onPathChange} sheetPreview={false} />
      </div>

      <div className="row" style={{ marginTop: 8 }}>
        <button
          type="button"
          className="btn secondary"
          onClick={() => previewMutation.mutate(sheet || undefined)}
          disabled={previewMutation.isPending || !path.trim() || runIdentityFieldsLoading || (!!runId && !runIdentityFields.length)}
        >
          {previewMutation.isPending ? <span className="spinner" /> : null}
          <span>{t("identification.preview")}</span>
        </button>
        {notice ? <span className="success">{notice}</span> : null}
        {error ? <span className="error">{error}</span> : null}
      </div>

      {preview ? (
        <div style={{ marginTop: 12 }}>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <div className="field">
              <label htmlFor="mono-sheet" className="field-label">{t("identification.sheet")}</label>
              <select
                id="mono-sheet"
                className="input"
                value={sheet}
                onChange={(e) => {
                  setResult(null);
                  previewMutation.mutate(e.target.value);
                }}
              >
                {preview.sheets.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="mono-header" className="field-label">{t("identification.headerRow")}</label>
              <select
                id="mono-header"
                className="input"
                value={String(headerRow)}
                onChange={(e) => {
                  const nextHeaderRow = parseInt(e.target.value, 10);
                  setHeaderRow(nextHeaderRow);
                  setIdentityCol(
                    preview.header_row_detected === nextHeaderRow
                      ? preview.columns_map[identityField]
                      : undefined,
                  );
                  setFirstSlotCol(preview ? detectFirstSlotColumn(preview, nextHeaderRow) : undefined);
                  setResult(null);
                }}
              >
                {preview.rows.map((_r, i) => (
                  <option key={i} value={String(i + 1)}>{String(i + 1)}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Apercu du contenu de l'onglet (comme la nomenclature). */}
          <div style={{ maxHeight: 240, overflow: "auto", marginTop: 12 }}>
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

          <div className="row" style={{ alignItems: "flex-end", marginTop: 8 }}>
            <div className="field">
              <label htmlFor="mono-identity-field" className="field-label">
                {t("identification.monoIdentityField")}
              </label>
              <select
                id="mono-identity-field"
                className="input"
                value={identityField}
                onChange={(e) => {
                  const field = e.target.value as MonoIdentityField;
                  setIdentityField(field);
                  setIdentityCol(
                    preview?.header_row_detected === headerRow
                      ? preview.columns_map[field]
                      : undefined,
                  );
                  setResult(null);
                }}
              >
                {MONO_IDENTITY_FIELDS.filter((f) => !runId || runIdentityFields.includes(f.field)).map((f) => (
                  <option key={f.field} value={f.field}>{t(f.labelKey)}</option>
                ))}
              </select>
            </div>
            {needsIdentityColumnSelection ? (
              <div className="field">
                <label htmlFor="mono-identity-col" className="field-label">
                  {t("identification.monoIdentityColumn")}
                </label>
                <select
                  id="mono-identity-col"
                  className="input"
                  value={identityCol === undefined ? "" : String(identityCol)}
                  onChange={(e) => {
                    setIdentityCol(e.target.value === "" ? undefined : parseInt(e.target.value, 10));
                    setResult(null);
                  }}
                >
                  <option value="">{t("identification.none")}</option>
                  {colOptions.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            ) : (
              <span className="hint" style={{ paddingBottom: 8 }}>
                {t("identification.monoIdentityDetected", {
                  field: identityLabel,
                  column: colLabel(preview!, detectedIdentityCol!, headerRow),
                })}
              </span>
            )}
            <div className="field">
              <label htmlFor="mono-first-slot" className="field-label">
                {t("identification.monoFirstSlotCol")}
              </label>
              <select
                id="mono-first-slot"
                className="input"
                value={firstSlotCol === undefined ? "" : String(firstSlotCol)}
                onChange={(e) => {
                  setFirstSlotCol(e.target.value === "" ? undefined : parseInt(e.target.value, 10));
                  setResult(null);
                }}
              >
                <option value="">{t("identification.none")}</option>
                {colOptions.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="row" style={{ marginTop: 12 }}>
            <button
              type="button"
              className="btn primary"
              onClick={() => analyzeMutation.mutate()}
              disabled={analyzeMutation.isPending || !canAnalyze}
            >
              {analyzeMutation.isPending ? <span className="spinner" /> : null}
              <span>{t("identification.monoAnalyze")}</span>
            </button>
            {!canAnalyze ? <span className="hint">{t("identification.monoRequired")}</span> : null}
          </div>

          {/* Resultat : pieces analysees (identite + slots + mono-corps). */}
          {result ? (
            <div style={{ marginTop: 16 }}>
              <div className="row" style={{ marginBottom: 8 }}>
                <span className="hint">
                  {t("identification.monoResultInfo", {
                    mono: Number(result.summary.mono) || 0,
                    rows: Number(result.summary.rows) || 0,
                  })}
                </span>
              </div>
              {monoItems.length ? (
                <div style={{ maxHeight: "30rem", overflow: "auto" }}>
                  <table className="tbl" style={{ whiteSpace: "nowrap" }}>
                    <thead>
                      <tr>
                        <th style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                          {t("identification.monoIdentityCol")}
                        </th>
                        {Array.from({ length: slotCount }, (_v, i) => (
                          <th
                            key={i}
                            style={{ position: "sticky", top: 0, background: "var(--bg-2)", textAlign: "center" }}
                          >
                            {preview && resultSlotCols[i] !== undefined
                              ? colLabel(preview, resultSlotCols[i]!, headerRow)
                              : t("identification.monoSlotN", { n: i + 1 })}
                          </th>
                        ))}
                        <th style={{ position: "sticky", top: 0, background: "var(--bg-2)", textAlign: "center" }}>
                          {t("identification.colMonoBody")}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {monoItems.map((it, ri) => (
                        <tr key={`${it.identity}-${ri}`}>
                          <td>{it.identity}</td>
                          {Array.from({ length: slotCount }, (_v, i) => (
                            <td key={i} style={{ textAlign: "center" }}>{it.slots[i] ?? ""}</td>
                          ))}
                          <td style={{ textAlign: "center" }}>
                            {it.mono_body ? <span className="badge ok">{t("common.yes")}</span> : null}
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
        </div>
      ) : null}
    </article>
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
  const [resultRunId, setResultRunId] = useState<string | null>(
    () => useWorkspace.getState().nomenclatureRunId,
  );
  // Colonnes reellement mappees pour ce resultat : le tableau n'affiche QUE
  // celles-ci (strictement le contenu du mapping).
  const [resultColumns, setResultColumns] = useState<string[]>([]);
  // Filtres d'affichage : "Pieces remplacees" par defaut (champ de filtre choisi
  // via une liste deroulante), + avec couleur / toutes.
  type ItemFilter = "all" | "replaced" | "monoBody" | "color";
  const [filter, setFilter] = useState<ItemFilter>("replaced");

  const runsQuery = useQuery<NomenclatureRunDto[]>({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
  });
  const runs = runsQuery.data ?? [];
  const activeRun = runs.find((run) => run.id === resultRunId);
  const runIdentityFields = activeRun
    ? detectedColumns(activeRun.summary).filter((field) =>
        MONO_IDENTITY_FIELDS.some((identity) => identity.field === field),
      )
    : [];

  useEffect(() => {
    if (!resultRunId) return;
    const currentRun = runs.find((run) => run.id === resultRunId);
    if (!currentRun) return;
    const columns = detectedColumns(currentRun.summary);
    setResultColumns((current) => (current.length ? current : columns));
    setFilter((current) =>
      current === "replaced" && !canFilterReplaced(columns) ? defaultFilter(columns) : current,
    );
  }, [resultRunId, runs]);

  const itemsQuery = useQuery<NomenclatureItemDto[]>({
    queryKey: ["identification", resultRunId, "items", filter],
    queryFn: () =>
      identificationApi.items(resultRunId!, {
        replaced: filter === "replaced" ? true : undefined,
        monoBody: filter === "monoBody" ? true : undefined,
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
      // Pre-remplit avec le dernier mapping memorise si present, sinon la
      // detection automatique par mots-cles d'en-tete.
      const saved = useWorkspace.getState().nomenMapping;
      const hr = saved?.headerRow ?? (data.header_row_detected > 0 ? data.header_row_detected : 1);
      setHeaderRow(hr);
      // Priorite : mapping memorise > detection auto completee par le defaut
      // du gabarit (SIN=B, Designation=D).
      setMapping(saved ? { ...saved.cols } : { ...data.columns_map, ...DEFAULT_MAPPING });
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
      useWorkspace.getState().setNomenclatureRun(run.id);
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
      if (resultRunId === id) {
        setResultRunId(null);
        useWorkspace.getState().setNomenclatureRun(null);
      }
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
    const cols: Record<string, number> = {};
    for (const { field } of MAPPING_FIELDS) {
      const v = mapping[field];
      if (v !== undefined) {
        body[field] = v;
        cols[field] = v;
      }
    }
    // Memorise ce mapping pour le pre-remplir au prochain preview.
    useWorkspace.getState().setNomenMapping({ headerRow, cols });
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
                    {canFilterReplaced(resultColumns) ? (
                      <option value="replaced">{t("identification.replacedOnly")}</option>
                    ) : null}
                    <option value="monoBody">{t("identification.monoBodyOnly")}</option>
                    {resultColumns.includes("color") ? (
                      <option value="color">{t("identification.withColor")}</option>
                    ) : null}
                  </select>
                </div>
                <a
                  href={exportUrl.identificationCsv(
                    resultRunId,
                    filter === "replaced"
                      ? { replaced: true }
                      : filter === "monoBody"
                        ? { monoBody: true }
                        : undefined,
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
                        {COLUMN_DEFS.filter((c) => displayColumns(resultColumns).includes(c.key)).map((c) => (
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
                          {COLUMN_DEFS.filter((c) => displayColumns(resultColumns).includes(c.key)).map((c) => (
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

      {/* ---- Carte Mono-Corps : autonome (onglet Materiaux + n slots) ---- */}
      <MonoCorpsCard
        runId={resultRunId}
        sourcePath={activeRun?.source_ref ?? nomenPath}
        runIdentityFields={runIdentityFields}
        runIdentityFieldsLoading={!!resultRunId && runsQuery.isLoading}
      />

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
                  <span className="badge ok">
                    {t("identification.badgeMonoBody", { count: summaryNum(r.summary, "mono_body") })}
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
                      useWorkspace.getState().setNomenclatureRun(r.id);
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
