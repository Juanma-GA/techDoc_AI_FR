import { Badge, Button, Select, Spinner } from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ScanLine, Search } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
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
  { field: "optimized", labelKey: "identification.fieldOptimized", required: false },
];

// Colonnes qui suffisent a identifier une piece (au moins une requise).
const IDENTITY_FIELDS: (keyof NomenclatureMapping)[] = ["sin", "old_pn", "new_pn"];

// Mapping du gabarit si les en-tetes du fichier ne sont pas reconnus :
// SIN en colonne B (index 1), Designation en colonne D (index 3).
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
    render: (it, tr) => (it.replaced ? <Badge variant="warning">{tr("common.yes")}</Badge> : null),
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
    render: (it, tr) => (it.mono_body ? <Badge variant="success">{tr("common.yes")}</Badge> : null),
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

function downloadCsv(rows: Array<Array<string | number>>, filename: string): void {
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(";"))
    .join("\r\n");
  const url = URL.createObjectURL(
    new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function comparablePath(path: string): string {
  return path.replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
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

function AnalysisInfoBox({ message, complete }: { message: string; complete: boolean }) {
  return (
    <div className={complete ? "analysis-info complete" : "analysis-info"} role="status">
      {message}
    </div>
  );
}

function AnalysisAction({
  mode,
  pending,
  disabled,
  error,
  hint,
  onClick,
  extraAction,
}: {
  mode: "preview" | "analyze";
  pending: boolean;
  disabled: boolean;
  error: string | null;
  hint?: string | null;
  onClick: () => void;
  extraAction?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="analysis-preview-controls">
      <Button
        type="button"
        variant={mode === "analyze" ? "primary" : "secondary"}
        onClick={onClick}
        disabled={disabled}
      >
        {pending ? <Spinner aria-label={t("common.loading")} /> : mode === "analyze" ? <ScanLine size={16} aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}
        <span>{t(mode === "analyze" ? "identification.analyze" : "identification.preview")}</span>
      </Button>
      {extraAction}
      {hint ? <span className="hint">{hint}</span> : null}
      {error ? <span className="error">{error}</span> : null}
    </div>
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

type NomenPreviewRequest = { path: string; sheet?: string; requestId: number };
type MonoPreviewRequest = { path: string; sheet?: string; requestId: number };

/**
 * Etape Mono-Corps : onglet Materiaux separe. L'utilisateur choisit un onglet,
 * un champ d'identite, un nombre `n` de colonnes slots, puis mappe ces n
 * colonnes. Le backend calcule mono_body (1 valeur distincte parmi les slots)
 * et l'applique aux pieces du run par la valeur d'identite.
 */
function MonoCorpsCard({
  runId,
  sourcePath,
  analysisStatus,
  runIdentityFields,
  runIdentityFieldsLoading,
}: {
  runId: string | null;
  sourcePath: string;
  analysisStatus: { matched: number; mono: number } | null;
  runIdentityFields: string[];
  runIdentityFieldsLoading: boolean;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
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
  const previewRequestId = useRef(0);
  const [previewSourcePath, setPreviewSourcePath] = useState("");

  useEffect(() => {
    previewRequestId.current += 1;
    setPreview(null);
    setPreviewSourcePath("");
    setSheet("");
    setHeaderRow(1);
    setIdentityCol(undefined);
    setFirstSlotCol(undefined);
    setResult(null);
    setError(null);
    setNotice(null);
    return () => { previewRequestId.current += 1; };
  }, [runId, sourcePath]);

  const previewMutation = useMutation({
    mutationFn: async ({ path: previewPath, sheet: previewSheet, requestId }: MonoPreviewRequest) => {
      let data: NomenclaturePreviewDto;
      if (previewSheet) {
        data = await identificationApi.preview({
          scope: "input",
          path: previewPath.trim(),
          sheet: previewSheet,
          rows: 20,
        });
      } else {
        const initial = await identificationApi.preview({
          scope: "input",
          path: previewPath.trim(),
          rows: 20,
        });
        const materialsSheet = initial.sheets.find(
          (candidate) => normalizedLabel(candidate) === "materiaux",
        );
        data = materialsSheet && materialsSheet !== initial.sheet
          ? await identificationApi.preview({
              scope: "input",
              path: previewPath.trim(),
              sheet: materialsSheet,
              rows: 20,
            })
          : initial;
      }
      return { data, path: previewPath, requestId };
    },
    onSuccess: ({ data, path, requestId }) => {
      if (requestId !== previewRequestId.current) return;
      setError(null);
      setNotice(null);
      setPreview(data);
      setPreviewSourcePath(path);
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
    onError: (e, request) => {
      if (request.requestId === previewRequestId.current) {
        setError(e instanceof ApiClientError ? e.message : String(e));
      }
    },
  });
  const mutatePreview = previewMutation.mutate;

  const requestPreview = (requestedSheet?: string) => {
    const requestId = ++previewRequestId.current;
    mutatePreview({ path: sourcePath.trim(), sheet: requestedSheet, requestId });
  };

  const analyzeMutation = useMutation({
    mutationFn: () =>
      identificationApi.monoCorps({
        path: sourcePath.trim(),
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

  const savedMonoItemsQuery = useQuery<NomenclatureItemDto[]>({
    queryKey: ["identification", runId, "saved-mono-body"],
    queryFn: () => identificationApi.items(runId!, { monoBody: true }),
    enabled: !!runId && !!analysisStatus && !result,
  });
  const savedMonoItems = savedMonoItemsQuery.data ?? [];

  const ncols = preview ? preview.rows.reduce((m, r) => Math.max(m, r.length), 0) : 0;
  const canAnalyze =
    !!sourcePath.trim() &&
    !!preview &&
    comparablePath(previewSourcePath) === comparablePath(sourcePath) &&
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
  const resultSlotLabels = Array.from({ length: slotCount }, (_v, i) =>
    preview && resultSlotCols[i] !== undefined
      ? colLabel(preview, resultSlotCols[i]!, headerRow)
      : t("identification.monoSlotN", { n: i + 1 }),
  );
  const exportMonoCsv = () => {
    const rows: Array<Array<string | number>> = [
      [
        t("identification.monoIdentityCol"),
        t("identification.colOldPn"),
        ...resultSlotLabels,
        t("identification.colMonoBody"),
      ],
      ...monoItems.map((item) => [
        item.identity,
        item.old_pn,
        ...Array.from({ length: resultSlotLabels.length }, (_v, i) => item.slots[i] ?? ""),
        item.mono_body ? 1 : 0,
      ]),
    ];
    downloadCsv(rows, "mono-corps.csv");
  };
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
  const analysisInfo = analysisStatus
    ? { message: t("identification.monoAlreadyApplied", analysisStatus), complete: true }
    : notice
      ? { message: notice, complete: true }
      : {
          message: runId
            ? t("identification.monoNotApplied")
            : t(sourcePath.trim() ? "identification.monoAwaitingRun" : "identification.noSourceStatus"),
          complete: false,
        };
  const actionMode =
    preview &&
    comparablePath(previewSourcePath) === comparablePath(sourcePath) &&
    !previewMutation.isError
      ? "analyze"
      : "preview";
  return (
    <section className="workflow-section">
      <h2 className="section-title">{t("identification.monoTitle")}</h2>
      <AnalysisInfoBox {...analysisInfo} />
      <AnalysisAction
        mode={actionMode}
        pending={previewMutation.isPending || analyzeMutation.isPending}
        disabled={
          previewMutation.isPending ||
          analyzeMutation.isPending ||
          !sourcePath.trim() ||
          (actionMode === "analyze"
            ? !canAnalyze
            : runIdentityFieldsLoading || (!!runId && !runIdentityFields.length))
        }
        error={error}
        hint={actionMode === "analyze" && !canAnalyze ? t("identification.monoRequired") : null}
        onClick={() => {
          if (actionMode === "analyze") analyzeMutation.mutate();
          else requestPreview(sheet || undefined);
        }}
        extraAction={result && monoItems.length ? (
          <Button type="button" variant="secondary" size="sm" onClick={exportMonoCsv}>
            {t("common.exportCsv")}
          </Button>
        ) : null}
      />

      {preview ? (
        <div style={{ marginTop: 12 }}>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <div className="field">
              <label htmlFor="mono-sheet" className="field-label">{t("identification.sheet")}</label>
              <Select options={[]}
                id="mono-sheet"

                value={sheet}
                onChange={(e) => {
                  setResult(null);
                  requestPreview(e.target.value);
                }}
              >
                {preview.sheets.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </Select>
            </div>
            <div className="field">
              <label htmlFor="mono-header" className="field-label">{t("identification.headerRow")}</label>
              <Select options={[]}
                id="mono-header"

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
              </Select>
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
              <Select options={[]}
                id="mono-identity-field"

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
              </Select>
            </div>
            {needsIdentityColumnSelection ? (
              <div className="field">
                <label htmlFor="mono-identity-col" className="field-label">
                  {t("identification.monoIdentityColumn")}
                </label>
                <Select options={[]}
                  id="mono-identity-col"

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
                </Select>
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
              <Select options={[]}
                id="mono-first-slot"

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
              </Select>
            </div>
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
                        <th style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>
                          {t("identification.colOldPn")}
                        </th>
                        {Array.from({ length: slotCount }, (_v, i) => (
                          <th
                            key={i}
                            style={{ position: "sticky", top: 0, background: "var(--bg-2)", textAlign: "center" }}
                          >
                            {resultSlotLabels[i]}
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
                          <td>{it.old_pn}</td>
                          {Array.from({ length: slotCount }, (_v, i) => (
                            <td key={i} style={{ textAlign: "center" }}>{it.slots[i] ?? ""}</td>
                          ))}
                          <td style={{ textAlign: "center" }}>
                            {it.mono_body ? <Badge variant="success">{t("common.yes")}</Badge> : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <h3 className="section-title">{t("identification.empty")}</h3>
                </div>
              )}
            </div>
          ) : null}
          {!result && analysisStatus ? (
            <div style={{ marginTop: 16 }}>
              {savedMonoItemsQuery.isLoading ? (
                <Spinner aria-label={t("common.loading")} />
              ) : savedMonoItemsQuery.isError ? (
                <p className="error">
                  {savedMonoItemsQuery.error instanceof Error
                    ? savedMonoItemsQuery.error.message
                    : String(savedMonoItemsQuery.error)}
                </p>
              ) : savedMonoItems.length ? (
                <div style={{ maxHeight: "30rem", overflow: "auto" }}>
                  <table className="tbl" style={{ whiteSpace: "nowrap" }}>
                    <thead>
                      <tr>
                        <th>{identityLabel}</th>
                        <th>{t("identification.colOldPn")}</th>
                        <th>{t("identification.colCatpart")}</th>
                        <th>{t("identification.colDesignation")}</th>
                        <th style={{ textAlign: "center" }}>{t("identification.colMonoBody")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {savedMonoItems.map((item) => (
                        <tr key={item.id}>
                          <td>{item[identityField] || item.sin || item.catpart || item.old_pn || item.new_pn}</td>
                          <td>{item.old_pn}</td>
                          <td>{item.catpart}</td>
                          <td>{item.designation}</td>
                          <td style={{ textAlign: "center" }}>
                            <Badge variant="success">{t("common.yes")}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <h3 className="section-title">{t("identification.empty")}</h3>
                </div>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
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
  const nomenPreviewRequestId = useRef(0);
  const [nomenPreviewPath, setNomenPreviewPath] = useState("");

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
  type ItemFilter = "all" | "replaced" | "monoBody" | "color" | "optimized";
  const [filter, setFilter] = useState<ItemFilter>("replaced");

  const runsQuery = useQuery<NomenclatureRunDto[]>({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
  });
  const runs = runsQuery.data ?? [];
  const activeRun = runs.find((run) =>
    run.id === resultRunId && comparablePath(run.source_ref) === comparablePath(nomenPath),
  );
  const sourceRuns = nomenPath.trim()
    ? runs.filter((run) => comparablePath(run.source_ref) === comparablePath(nomenPath))
    : [];
  const runIdentityFields = activeRun
    ? detectedColumns(activeRun.summary).filter((field) =>
        MONO_IDENTITY_FIELDS.some((identity) => identity.field === field),
      )
    : [];
  const monoAnalysisStatus =
    activeRun && typeof activeRun.summary.mono_matched === "number"
      ? {
          matched: activeRun.summary.mono_matched,
          mono: summaryNum(activeRun.summary, "mono_body"),
        }
      : null;
  const nomenAnalysisInfo = activeRun
    ? {
        message: t("identification.analyzedShort", {
          rows: summaryNum(activeRun.summary, "rows"),
          replaced: summaryNum(activeRun.summary, "replaced"),
          mono: summaryNum(activeRun.summary, "mono_color"),
        }),
        complete: true,
      }
    : nomenNotice
      ? { message: nomenNotice, complete: true }
      : {
          message: t(nomenPath.trim() ? "identification.nomenNotAnalyzed" : "identification.noSourceStatus"),
          complete: false,
        };
  const selectRun = (run: NomenclatureRunDto) => {
    if (run.id !== resultRunId || comparablePath(run.source_ref) !== comparablePath(nomenPath)) {
      nomenPreviewRequestId.current += 1;
      previewMutation.reset();
      analyzeMappingMutation.reset();
      setPreview(null);
      setNomenPreviewPath("");
      setSheet("");
      setHeaderRow(1);
      setMapping({});
    }
    setNomenNotice(null);
    setNomenError(null);
    setResultRunId(run.id);
    useWorkspace.getState().setNomenclatureRun(run.id);
    setNomenPath(run.source_ref);
    const columns = detectedColumns(run.summary);
    setResultColumns(columns);
    setFilter(defaultFilter(columns));
  };

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
        optimized: filter === "optimized" ? true : undefined,
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
    mutationFn: async ({ path, sheet: requestedSheet, requestId }: NomenPreviewRequest) => ({
      data: await identificationApi.preview({
        scope: "input",
        path: path.trim(),
        sheet: requestedSheet,
        rows: 20,
      }),
      path,
      requestId,
    }),
    onSuccess: ({ data, path, requestId }) => {
      if (requestId !== nomenPreviewRequestId.current) return;
      setNomenError(null);
      setPreview(data);
      setNomenPreviewPath(path);
      setSheet(data.sheet);
      setHeaderRow(data.header_row_detected > 0 ? data.header_row_detected : 1);
      setMapping({ ...DEFAULT_MAPPING, ...data.columns_map });
    },
    onError: (e, request) => {
      if (request.requestId === nomenPreviewRequestId.current) {
        setNomenError(e instanceof ApiClientError ? e.message : String(e));
      }
    },
  });
  const mutateNomenPreview = previewMutation.mutate;
  const requestNomenPreview = (path: string, requestedSheet?: string) => {
    const requestId = ++nomenPreviewRequestId.current;
    mutateNomenPreview({ path, sheet: requestedSheet, requestId });
  };

  useEffect(() => () => { nomenPreviewRequestId.current += 1; }, []);

  // Analyse avec le mapping de colonnes choisi : "Analyser avec ce mapping".
  const analyzeMappingMutation = useMutation({
    mutationFn: (request: NomenPreviewRequest & { mapping: NomenclatureMapping }) =>
      identificationApi.nomenclature({
        scope: "input",
        path: request.path,
        sheet: request.sheet,
        mapping: request.mapping,
      }),
    onSuccess: (run, request) => {
      void qc.invalidateQueries({ queryKey: ["identification"] });
      if (request.requestId !== nomenPreviewRequestId.current) return;
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
    },
    onError: (error, request) => {
      if (request.requestId === nomenPreviewRequestId.current) {
        onMutationError(setNomenError)(error);
      }
    },
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
  const onNomenPathChange = (nextPath: string) => {
    nomenPreviewRequestId.current += 1;
    previewMutation.reset();
    analyzeMappingMutation.reset();
    const matchedRun = nextPath.trim()
      ? runs.find((run) => comparablePath(run.source_ref) === comparablePath(nextPath))
      : undefined;
    if (matchedRun) {
      selectRun(matchedRun);
      return;
    }
    setResultRunId(null);
    useWorkspace.getState().setNomenclatureRun(null);
    setNomenPath(nextPath);
    setResultColumns([]);
    setFilter("all");
    setPreview(null);
    setNomenPreviewPath("");
    setSheet("");
    setHeaderRow(1);
    setMapping({});
    setNomenError(null);
    setNomenNotice(null);
  };

  const onPreview = () => {
    if (!nomenPath.trim()) {
      setNomenError(t("identification.pathRequired"));
      return;
    }
    requestNomenPreview(nomenPath, sheet || undefined);
  };

  const onSheetChange = (s: string) => {
    setSheet(s);
    requestNomenPreview(nomenPath, s);
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
      if (v !== undefined) {
        body[field] = v;
      }
    }
    analyzeMappingMutation.mutate({
      path: nomenPath.trim(),
      sheet: sheet || undefined,
      mapping: body,
      requestId: nomenPreviewRequestId.current,
    });
  };

  // Nombre max de colonnes dans l'apercu (pour les selects de mapping).
  const ncols = preview ? preview.rows.reduce((m, r) => Math.max(m, r.length), 0) : 0;
  // Le mapping est "configure" des qu'au moins une colonne d'identite est choisie.
  const hasIdentity = IDENTITY_FIELDS.some((f) => mapping[f] !== undefined);
  const nomenPreviewReady =
    !!preview &&
    comparablePath(nomenPreviewPath) === comparablePath(nomenPath) &&
    !previewMutation.isError;
  const nomenActionMode = nomenPreviewReady ? "analyze" : "preview";

  return (
    <div className="identification-layout">
      <section className="workflow-section">
        <h2 className="section-title">{t("identification.sourceTitle")}</h2>
        <div className="identification-top-grid">
          <div>
            <label className="label">{t("identification.nomenFileLabel")}</label>
            <FilePicker exts={NOMEN_EXTS} value={nomenPath} onChange={onNomenPathChange} sheetPreview={false} />
            <p className="hint" style={{ margin: "10px 0 0" }}>
              {t("identification.sharedSourceHint")}
            </p>
          </div>

          <div className="identification-import-list">
            <h3 className="section-sub" style={{ marginTop: 0 }}>{t("identification.importedListTitle")}</h3>
            {runsQuery.isLoading ? (
              <Spinner aria-label={t("common.loading")} />
            ) : runs.length || nomenPath.trim() ? (
              <ul className="item-list identification-run-list">
                {nomenPath.trim() && sourceRuns.length === 0 ? (
                  <li
                    className="item-row"
                    aria-current="true"
                  >
                    <span className="item-main grow" style={{ minWidth: 0 }}>
                      <span className="item-name">{fileName(nomenPath)}</span>
                    </span>
                    <Badge variant="warning">{t("identification.sourceNotAnalyzed")}</Badge>
                  </li>
                ) : null}
                {runs.map((r) => (
                  <li
                    key={r.id}
                    className="item-row clickable"
                    aria-current={r.id === resultRunId ? "true" : undefined}
                    onClick={() => selectRun(r)}
                  >
                    <span className="item-main grow" style={{ minWidth: 0 }}>
                      <span className="item-name">{fileName(r.source_ref)}</span>{" "}
                      <Badge variant="info">
                        {t("identification.badgeLines", { count: summaryNum(r.summary, "rows") })}
                      </Badge>{" "}
                      <Badge variant="warning">
                        {t("identification.badgeReplaced", { count: summaryNum(r.summary, "replaced") })}
                      </Badge>{" "}
                      <Badge variant="success">
                        {t("identification.badgeMonoBody", { count: summaryNum(r.summary, "mono_body") })}
                      </Badge>{" "}
                      <Badge variant="default">
                        {t("identification.badgeMono", { count: summaryNum(r.summary, "mono_color") })}
                      </Badge>
                    </span>
                    <span className="item-actions">
                      <Button type="button" variant="secondary" size="sm">
                        {t("common.view")}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost" size="sm"
                        onClick={(event) => {
                          event.stopPropagation();
                          deleteMutation.mutate(r.id);
                        }}
                      >
                        {t("common.delete")}
                      </Button>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <p className="hint">{t("identification.importListEmpty")}</p>
              </div>
            )}
          </div>
        </div>
      </section>

      <div className="identification-analysis-grid">
      {/* ---- Analyse de la nomenclature ----------------------------------- */}
      <section className="workflow-section">
        <h2 className="section-title">{t("identification.nomenTitle")}</h2>
        <AnalysisInfoBox {...nomenAnalysisInfo} />
        <AnalysisAction
          mode={nomenActionMode}
          pending={previewMutation.isPending || analyzeMappingMutation.isPending}
          disabled={
            previewMutation.isPending ||
            analyzeMappingMutation.isPending ||
            !nomenPath.trim() ||
            (nomenActionMode === "analyze" && !hasIdentity)
          }
          error={nomenError}
          hint={nomenActionMode === "analyze" && !hasIdentity ? t("identification.identityRequired") : null}
          onClick={() => {
            if (nomenActionMode === "analyze") onAnalyzeMapping();
            else onPreview();
          }}
        />

          {/* ---- Apercu / onglets + mapping ---- */}
          {preview ? (
            <div style={{ marginTop: 16 }}>
              <div className="row" style={{ alignItems: "flex-end" }}>
                <div className="field">
                  <label htmlFor="nomen-sheet" className="field-label">
                    {t("identification.sheet")}
                  </label>
                  <Select options={[]}
                    id="nomen-sheet"

                    value={sheet}
                    onChange={(e) => onSheetChange(e.target.value)}
                  >
                    {preview.sheets.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="field">
                  <label htmlFor="nomen-headerrow" className="field-label">
                    {t("identification.headerRow")}
                  </label>
                  <Select options={[]}
                    id="nomen-headerrow"

                    value={String(headerRow)}
                    onChange={(e) => setHeaderRow(parseInt(e.target.value, 10))}
                  >
                    {preview.rows.map((_r, i) => (
                      <option key={i} value={String(i + 1)}>
                        {String(i + 1)}
                      </option>
                    ))}
                  </Select>
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
                      <Select options={[]}
                        id={id}

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
                      </Select>
                    </div>
                  );
                })}
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
                  <Select options={[]}
                    id="nomen-filter"

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
                    {resultColumns.includes("optimized") ? (
                      <option value="optimized">{t("identification.optimizedOnly")}</option>
                    ) : null}
                  </Select>
                </div>
                <a
                  href={exportUrl.identificationCsv(
                    resultRunId,
                    filter === "replaced"
                      ? { replaced: true }
                      : filter === "monoBody"
                        ? { monoBody: true }
                        : filter === "optimized"
                          ? { optimized: true }
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
                <Spinner aria-label={t("common.loading")} />
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
                  <h3 className="section-title">{t("identification.empty")}</h3>
                </div>
              )}
            </div>
          ) : null}
      </section>

      {/* ---- Carte Mono-Corps : onglet Materiaux + n slots ---------------- */}
      <MonoCorpsCard
        key={`${nomenPath}:${resultRunId ?? ""}`}
        runId={resultRunId}
        sourcePath={nomenPath}
        analysisStatus={monoAnalysisStatus}
        runIdentityFields={runIdentityFields}
        runIdentityFieldsLoading={!!resultRunId && (!activeRun || runsQuery.isLoading)}
      />
      </div>
    </div>
  );
}
