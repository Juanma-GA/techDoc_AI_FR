/**
 * Projects — vue liste + vue detail par projet.
 * Vue detail : informations projet, referentiels ATM/BASL + editeur de mapping
 * des colonnes, fichiers FTM avec detection doublons SHA-256, et lancement de
 * l'analyse avec synthese des resultats par type d'anomalie.
 * Navigation : ?pid=<id> dans l'URL ouvre directement la fiche projet
 * (point d'entree depuis le raccourci Manager → Ouvrir la fiche projet).
 */
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  KpiCard,
} from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import {
  resources,
  type AnalysisRunOut,
  type FileOut,
  type Project,
  type ProjectUpdate,
  type ReferenceColumnDef,
  type SheetColumnOut,
} from "../lib/api";

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const ANALYSIS_KPI_TYPES = [
  "script", "granule", "texte", "ordre_taches", "tache_induite",
  "orthographe", "rechange", "outillage", "infrastructure", "entete",
  "securite", "preliminaire", "valeur_numerique", "serrage",
  "complementaire", "illustration", "personnalisee",
] as const;

// ─────────────────────────────────────────────────────────────────────────────
// AnalysisResult — parse run.summary JSON, affiche KPIs par type d'anomalie
// ─────────────────────────────────────────────────────────────────────────────

function AnalysisResult({ run }: { run: AnalysisRunOut }) {
  const { t } = useTranslation();
  let s: Record<string, number> = {};
  try { s = JSON.parse(run.summary || "{}") as Record<string, number>; } catch { /* noop */ }

  const total = ANALYSIS_KPI_TYPES.reduce((acc, typ) => acc + (s[typ] ?? 0), 0);
  const indexed = s["indexed_chunks"] ?? 0;
  const totalCls = total === 0 ? "text-success" : total < 5 ? "text-info" : total < 20 ? "text-warning" : "text-danger";
  const nonZeroTypes = ANALYSIS_KPI_TYPES.filter((typ) => (s[typ] ?? 0) > 0);

  return (
    <div className="mt-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <KpiCard
          label={t("projects.kpi.totalAnomalies")}
          value={<span className={totalCls}>{total}</span>}
        />
        <KpiCard
          label={t("projects.kpi.indexed")}
          value={<span className={indexed > 0 ? "text-success" : ""}>{indexed}</span>}
        />
        {nonZeroTypes.map((typ) => (
          <KpiCard
            key={typ}
            label={t(`projects.kpi.type.${typ}`)}
            value={<span className="text-warning">{s[typ]}</span>}
          />
        ))}
      </div>
      {total === 0 && (
        <div className="mt-2 rounded-lg border border-dashed p-3 text-sm text-fg-muted">
          {t("projects.kpi.noAnomaliesDetected")}
        </div>
      )}
      <div className="mt-2 text-xs text-fg-muted">
        {t("projects.analysisFinishedAt")}{" "}
        {run.finished_at ? new Date(run.finished_at).toLocaleString() : "—"}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// AnalysisCard — lancer / réinitialiser l'analyse, afficher le résultat
// ─────────────────────────────────────────────────────────────────────────────

function AnalysisCard({ pid }: { pid: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [result, setResult] = useState<AnalysisRunOut | null>(null);
  const [armed, setArmed] = useState(false);
  const armTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runMutation = useMutation({
    mutationFn: () => resources.analysis.run(pid),
    onSuccess: (run) => {
      setResult(run);
      void qc.invalidateQueries({ queryKey: ["kpis"] });
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => resources.analysis.reset(pid),
    onSuccess: () => {
      setResult(null);
      void qc.invalidateQueries({ queryKey: ["kpis"] });
    },
  });

  const handleReset = () => {
    if (armed) {
      if (armTimer.current) clearTimeout(armTimer.current);
      setArmed(false);
      resetMutation.mutate();
    } else {
      if (armTimer.current) clearTimeout(armTimer.current);
      setArmed(true);
      armTimer.current = setTimeout(() => setArmed(false), 3000);
    }
  };

  return (
    <Card>
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-base">{t("projects.analysis")}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || resetMutation.isPending}
          >
            {t("projects.runAnalysis")}
          </Button>
          <Button
            variant={armed ? "danger" : "ghost"}
            size="sm"
            onClick={handleReset}
            disabled={resetMutation.isPending || runMutation.isPending}
          >
            {armed ? t("common.confirmDelete") : t("projects.reset")}
          </Button>
        </div>

        {runMutation.isPending && (
          <div className="mt-3 rounded-lg border border-info/30 bg-bg-2 p-3">
            <div className="font-medium text-info">{t("projects.analysisRunning")}</div>
            <div className="mt-1 text-xs text-fg-muted">{t("projects.analysisRunningHint")}</div>
          </div>
        )}

        {runMutation.isError && (
          <div className="mt-3 text-sm text-danger">{t("errors.generic")}</div>
        )}

        {result && <AnalysisResult run={result} />}
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FileRow — une ligne de fichier avec badge doublon et bouton suppression
// ─────────────────────────────────────────────────────────────────────────────

function FileRow({
  file, pid, isDuplicate, duplicateOf,
}: {
  file: FileOut;
  pid: string;
  isDuplicate: boolean;
  duplicateOf: string[];
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [armed, setArmed] = useState(false);
  const armTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const deleteMutation = useMutation({
    mutationFn: () => resources.files.delete(pid, file.id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["files", pid] }),
  });

  const handleDelete = () => {
    if (armed) {
      if (armTimer.current) clearTimeout(armTimer.current);
      setArmed(false);
      deleteMutation.mutate();
    } else {
      if (armTimer.current) clearTimeout(armTimer.current);
      setArmed(true);
      armTimer.current = setTimeout(() => setArmed(false), 3000);
    }
  };

  const latest = [...file.versions].sort((a, b) =>
    a.uploaded_at < b.uploaded_at ? -1 : 1,
  ).at(-1);

  return (
    <div className="flex items-center justify-between gap-3 border-b py-2 last:border-0">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="min-w-0 truncate text-sm text-fg">{file.current_name}</span>
          {isDuplicate && (
            <Badge
              variant="danger"
              title={`${t("files.duplicateOf")}: ${duplicateOf.join(", ")}`}
            >
              {t("files.duplicate")}
            </Badge>
          )}
        </div>
        <div className="mt-0.5 text-xs text-fg-muted">
          {file.versions.length} v · {file.mime_type || "?"}
          {latest ? ` · ${latest.size} B` : ""}
        </div>
      </div>
      <Button
        variant={armed ? "danger" : "ghost"}
        size="sm"
        onClick={handleDelete}
        disabled={deleteMutation.isPending}
      >
        {armed ? t("common.confirmDelete") : "×"}
      </Button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FilesCard — upload multi-fichiers + liste avec détection doublons SHA-256
// ─────────────────────────────────────────────────────────────────────────────

function FilesCard({ pid }: { pid: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadMsg, setUploadMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const { data: files = [], isLoading } = useQuery({
    queryKey: ["files", pid],
    queryFn: () => resources.files.list(pid),
  });

  const uploadMutation = useMutation({
    mutationFn: (fd: FormData) => resources.files.upload(pid, fd),
    onSuccess: (res) => {
      const msgs = res.uploaded.map((u) =>
        u.ok
          ? `✓ ${u.filename}${u.skipped ? ` (${u.skipped})` : ""}`
          : `✗ ${u.filename}: ${u.error ?? ""}`,
      );
      setUploadMsg({ ok: true, text: msgs.join("\n") });
      if (fileInputRef.current) fileInputRef.current.value = "";
      void qc.invalidateQueries({ queryKey: ["files", pid] });
    },
    onError: (err) => {
      setUploadMsg({
        ok: false,
        text: err instanceof Error ? err.message : t("errors.generic"),
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setUploadMsg(null);
    const fl = fileInputRef.current?.files;
    if (!fl?.length) return;
    const fd = new FormData();
    Array.from(fl).forEach((f) => fd.append("files", f));
    uploadMutation.mutate(fd);
  };

  // Détection doublons SHA-256 : sha → liste des noms de fichiers
  const byHash: Record<string, string[]> = {};
  for (const f of files) {
    const latest = [...f.versions].sort((a, b) =>
      a.uploaded_at < b.uploaded_at ? -1 : 1,
    ).at(-1);
    if (!latest?.sha256) continue;
    (byHash[latest.sha256] ??= []).push(f.current_name);
  }
  const dupSha = new Set(
    Object.keys(byHash).filter((sha) => (byHash[sha]?.length ?? 0) > 1),
  );

  return (
    <Card>
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-base">{t("projects.files")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="mb-3 flex flex-wrap items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            required
            className="min-w-0 flex-1 text-sm text-fg file:mr-2 file:rounded file:border file:border-border file:bg-bg-2 file:px-2 file:py-0.5 file:text-xs file:text-fg"
          />
          <Button type="submit" variant="secondary" disabled={uploadMutation.isPending}>
            {t("projects.upload")}
          </Button>
        </form>

        {uploadMsg && (
          <pre
            className={[
              "mb-3 whitespace-pre-wrap rounded border p-2 text-xs",
              uploadMsg.ok ? "border-success/30 text-success" : "border-danger/30 text-danger",
            ].join(" ")}
          >
            {uploadMsg.text}
          </pre>
        )}

        {isLoading && <p className="text-sm text-fg-muted">{t("common.loading")}</p>}

        {!isLoading && files.length === 0 && (
          <div className="py-4 text-center text-sm text-fg-muted">—</div>
        )}

        {files.map((f) => {
          const latest = [...f.versions].sort((a, b) =>
            a.uploaded_at < b.uploaded_at ? -1 : 1,
          ).at(-1);
          const isDup = !!(latest?.sha256 && dupSha.has(latest.sha256));
          const otherNames = isDup && latest?.sha256
            ? (byHash[latest.sha256] ?? []).filter((n) => n !== f.current_name)
            : [];
          return (
            <FileRow
              key={f.id}
              file={f}
              pid={pid}
              isDuplicate={isDup}
              duplicateOf={otherNames}
            />
          );
        })}
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MappingEditor — éditeur de mapping colonnes de référence (onglet + colonne)
// ─────────────────────────────────────────────────────────────────────────────

type RefRow = { name: string; sheet: string; column: string; builtin: boolean };

function MappingEditor({
  pid, sheets, initialRows,
}: {
  pid: string;
  sheets: string[];
  initialRows: RefRow[];
}) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<RefRow[]>(initialRows);
  const colCacheRef = useRef<Record<string, SheetColumnOut[]>>({});
  const [colCache, setColCache] = useState<Record<string, SheetColumnOut[]>>({});
  const [feedback, setFeedback] = useState("");

  useEffect(() => { setRows(initialRows); }, [initialRows]);

  const fetchCols = useCallback(async (sheet: string) => {
    if (!sheet || colCacheRef.current[sheet] !== undefined) return;
    colCacheRef.current[sheet] = [];
    try {
      const cols = await resources.reference.getColumns(pid, sheet);
      colCacheRef.current[sheet] = cols;
    } catch { /* keep empty */ }
    setColCache({ ...colCacheRef.current });
  }, [pid]);

  useEffect(() => {
    const uniqueSheets = [...new Set(rows.map((r) => r.sheet).filter(Boolean))];
    uniqueSheets.forEach((s) => void fetchCols(s));
  }, [rows, fetchCols]);

  const updateRow = (i: number, patch: Partial<RefRow>) => {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
    if (patch.sheet) void fetchCols(patch.sheet);
  };

  const addRow = () => {
    setRows((prev) => [...prev, { name: "", sheet: "", column: "", builtin: false }]);
  };

  const removeRow = (i: number) => {
    setRows((prev) => prev.filter((_, idx) => idx !== i));
  };

  const save = async () => {
    setFeedback("…");
    try {
      await resources.reference.updateMapping(pid, {
        columns: rows.map(({ name, sheet, column }) => ({ name, sheet, column })),
      });
      setFeedback(t("referentiel.mappingSaved"));
    } catch (err) {
      setFeedback(`✗ ${err instanceof Error ? err.message : t("errors.generic")}`);
    }
  };

  const inputCls =
    "w-full rounded border border-border bg-bg-2 px-1.5 py-0.5 text-xs text-fg focus:outline-none focus:ring-1 focus:ring-brand-blue-light";

  return (
    <div className="mt-3">
      <div className="mb-2 text-xs text-fg-muted">{t("referentiel.mappingHint")}</div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left text-fg-muted">
              <th className="pb-1 pr-2 font-medium">{t("referentiel.hdrName")}</th>
              <th className="pb-1 pr-2 font-medium">{t("referentiel.hdrSheet")}</th>
              <th className="pb-1 pr-2 font-medium">{t("referentiel.hdrColumn")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b last:border-0">
                <td className="py-1 pr-2">
                  {row.builtin ? (
                    <span
                      className="rounded bg-brand/10 px-1.5 py-0.5 font-medium text-brand-blue-light"
                      title={t("referentiel.builtinHint")}
                    >
                      {row.name}
                    </span>
                  ) : (
                    <input
                      className={inputCls}
                      value={row.name}
                      placeholder={t("referentiel.namePh")}
                      onChange={(e) => updateRow(i, { name: e.target.value })}
                    />
                  )}
                </td>
                <td className="py-1 pr-2">
                  <select
                    className={inputCls}
                    value={row.sheet}
                    onChange={(e) => updateRow(i, { sheet: e.target.value, column: "" })}
                  >
                    <option value="">—</option>
                    {sheets.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </td>
                <td className="py-1 pr-2">
                  <select
                    className={inputCls}
                    value={row.column}
                    onChange={(e) => updateRow(i, { column: e.target.value })}
                  >
                    <option value="">—</option>
                    {(colCache[row.sheet] ?? []).map((c) => (
                      <option key={c.letter} value={c.letter}>
                        {c.letter}{c.header ? ` · ${c.header}` : ""}
                      </option>
                    ))}
                    {/* Colonne déjà sauvegardée mais onglet pas encore chargé */}
                    {row.column &&
                      !(colCache[row.sheet] ?? []).some((c) => c.letter === row.column) && (
                        <option value={row.column}>{row.column}</option>
                      )}
                  </select>
                </td>
                <td className="py-1">
                  {!row.builtin && (
                    <button
                      type="button"
                      onClick={() => removeRow(i)}
                      className="text-danger hover:underline"
                    >
                      ×
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={addRow}>
          {t("referentiel.addColumn")}
        </Button>
        <Button type="button" variant="primary" size="sm" onClick={() => void save()}>
          {t("referentiel.saveMapping")}
        </Button>
        {feedback && <span className="text-xs text-fg-muted">{feedback}</span>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ReferentialsCard — ATM (avec mapping) + BASL
// ─────────────────────────────────────────────────────────────────────────────

function ReferentialsCard({ pid }: { pid: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const atmRef = useRef<HTMLInputElement>(null);
  const baslRef = useRef<HTMLInputElement>(null);
  const [refError, setRefError] = useState("");

  const { data: ref } = useQuery({
    queryKey: ["reference", pid],
    queryFn: () => resources.reference.get(pid),
  });

  const { data: basl } = useQuery({
    queryKey: ["basl", pid],
    queryFn: () => resources.basl.get(pid),
  });

  const uploadRefMutation = useMutation({
    mutationFn: (fd: FormData) => resources.reference.upload(pid, fd),
    onSuccess: () => {
      if (atmRef.current) atmRef.current.value = "";
      void qc.invalidateQueries({ queryKey: ["reference", pid] });
    },
    onError: (err) => setRefError(err instanceof Error ? err.message : t("errors.generic")),
  });

  const uploadBaslMutation = useMutation({
    mutationFn: (fd: FormData) => resources.basl.upload(pid, fd),
    onSuccess: () => {
      if (baslRef.current) baslRef.current.value = "";
      void qc.invalidateQueries({ queryKey: ["basl", pid] });
    },
    onError: (err) => setRefError(err instanceof Error ? err.message : t("errors.generic")),
  });

  const handleAtmSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setRefError("");
    const file = atmRef.current?.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    uploadRefMutation.mutate(fd);
  };

  const handleBaslSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setRefError("");
    const file = baslRef.current?.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    uploadBaslMutation.mutate(fd);
  };

  const fileInputCls =
    "min-w-0 flex-1 text-xs text-fg file:mr-2 file:rounded file:border file:border-border file:bg-bg-2 file:px-2 file:py-0.5 file:text-xs file:text-fg";

  const hasRef = !!ref?.path;
  const hasBasl = !!basl?.path;
  const refStatus = hasRef
    ? `${t("referentiel.loaded")} — ${ref.sheets.join(", ") || "(aucun)"}`
    : t("referentiel.none");
  const baslStatus = hasBasl
    ? `${t("referentiel.loaded")} — ${basl.sheets.join(", ") || "(aucun)"}`
    : t("referentiel.baslNone");

  const refRows: RefRow[] = (ref?.columns ?? []).map(
    (c: ReferenceColumnDef) => ({
      name: c.name, sheet: c.sheet, column: c.column, builtin: c.builtin,
    }),
  );

  return (
    <Card>
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-base">Référentiels</CardTitle>
      </CardHeader>
      <CardContent>
        {/* ATM */}
        <div className="mb-1 text-xs font-medium uppercase tracking-wide text-fg-muted">
          {t("referentiel.atmTitle")}
        </div>
        <div className="mb-2 text-xs text-fg-muted">{refStatus}</div>
        <form onSubmit={handleAtmSubmit} className="flex flex-wrap items-center gap-2">
          <input
            ref={atmRef}
            type="file"
            name="file"
            accept=".xlsx,.xlsm"
            required
            className={fileInputCls}
          />
          <Button type="submit" variant="secondary" size="sm" disabled={uploadRefMutation.isPending}>
            {t("referentiel.upload")}
          </Button>
        </form>

        {hasRef && ref && (
          <MappingEditor pid={pid} sheets={ref.sheets} initialRows={refRows} />
        )}

        {/* BASL */}
        <div className="mb-1 mt-5 text-xs font-medium uppercase tracking-wide text-fg-muted">
          BASL — rechanges, outillages, infrastructure, en-tête
        </div>
        <div className="mb-2 text-xs text-fg-muted">{baslStatus}</div>
        <form onSubmit={handleBaslSubmit} className="flex flex-wrap items-center gap-2">
          <input
            ref={baslRef}
            type="file"
            name="file"
            accept=".xlsx,.xlsm"
            required
            className={fileInputCls}
          />
          <Button type="submit" variant="secondary" size="sm" disabled={uploadBaslMutation.isPending}>
            Téléverser la BASL
          </Button>
        </form>

        {refError && <div className="mt-2 text-xs text-danger">{refError}</div>}
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// InfoCard — meta KPIs + formulaire d'édition inline
// ─────────────────────────────────────────────────────────────────────────────

function InfoCard({
  project, pid, editOpen, onEditClose,
}: {
  project: Project;
  pid: string;
  editOpen: boolean;
  onEditClose: () => void;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);
  const [vision, setVision] = useState(project.vision_enabled);
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    if (editOpen) {
      setName(project.name);
      setDescription(project.description);
      setVision(project.vision_enabled);
      setFeedback("");
    }
  }, [editOpen, project]);

  const updateMutation = useMutation({
    mutationFn: (body: ProjectUpdate) => resources.projects.update(pid, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["project", pid] });
      void qc.invalidateQueries({ queryKey: ["projects"] });
      onEditClose();
    },
    onError: (err) => {
      setFeedback(`✗ ${err instanceof Error ? err.message : t("errors.generic")}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    updateMutation.mutate({ name: name.trim(), description, vision_enabled: vision });
  };

  const inputCls =
    "w-full rounded border border-border bg-bg px-3 py-2 text-sm text-fg placeholder-fg-muted focus:outline-none focus:ring-2 focus:ring-brand-blue-light";

  return (
    <Card>
      <CardContent className="pt-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-bg-2 p-3">
            <div className="text-xs uppercase tracking-wide text-fg-muted">Description</div>
            <div className="mt-1 text-sm text-fg">
              {project.description || <span className="text-fg-muted">—</span>}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg-2 p-3">
            <div className="text-xs uppercase tracking-wide text-fg-muted">Vision</div>
            <div
              className={[
                "mt-1 font-mono text-base font-bold",
                project.vision_enabled ? "text-success" : "text-info",
              ].join(" ")}
            >
              {project.vision_enabled ? "ON" : "OFF"}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg-2 p-3">
            <div className="text-xs uppercase tracking-wide text-fg-muted">
              {new Date(project.created_at).toLocaleDateString()}
            </div>
            <div className="mt-1 font-mono text-xs text-fg-muted">
              {project.id.substring(0, 8)}…
            </div>
          </div>
        </div>

        {editOpen && (
          <form
            onSubmit={handleSubmit}
            className="mt-4 rounded-lg border border-info/30 bg-bg-2 p-4"
          >
            <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-muted">
              {t("projects.editTitle")}
            </div>
            <div className="flex flex-col gap-2">
              <input
                autoFocus
                className={inputCls}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("projects.namePh")}
                required
                maxLength={255}
              />
              <input
                className={inputCls}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("projects.descPh")}
                maxLength={4000}
              />
              <label className="flex cursor-pointer items-center gap-2 text-sm text-fg">
                <input
                  type="checkbox"
                  checked={vision}
                  onChange={(e) => setVision(e.target.checked)}
                  className="h-4 w-4 rounded"
                />
                {t("projects.vision")}
              </label>
              <div className="flex items-center gap-2">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={updateMutation.isPending || !name.trim()}
                >
                  {t("projects.save")}
                </Button>
                <Button type="button" variant="ghost" onClick={onEditClose}>
                  {t("projects.cancel")}
                </Button>
                {feedback && <span className="text-xs text-danger">{feedback}</span>}
              </div>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ProjectDetail — vue détail d'un projet (header + 4 cards)
// ─────────────────────────────────────────────────────────────────────────────

function ProjectDetail({ pid, onBack }: { pid: string; onBack: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteArmed, setDeleteArmed] = useState(false);
  const deleteTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data: project, isLoading } = useQuery({
    queryKey: ["project", pid],
    queryFn: () => resources.projects.get(pid),
  });

  const deleteMutation = useMutation({
    mutationFn: () => resources.projects.delete(pid),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
      onBack();
    },
  });

  const handleDelete = () => {
    if (deleteArmed) {
      if (deleteTimer.current) clearTimeout(deleteTimer.current);
      setDeleteArmed(false);
      deleteMutation.mutate();
    } else {
      if (deleteTimer.current) clearTimeout(deleteTimer.current);
      setDeleteArmed(true);
      deleteTimer.current = setTimeout(() => setDeleteArmed(false), 3000);
    }
  };

  if (isLoading) return <p className="text-sm text-fg-muted">{t("common.loading")}</p>;
  if (!project) return null;

  return (
    <div>
      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button variant="ghost" onClick={onBack}>
          {t("projects.back")}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(`/?pid=${pid}`)}
        >
          {t("projects.dashboard")}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setEditOpen(true)}
          disabled={editOpen}
        >
          {t("projects.edit")}
        </Button>
        <Button
          variant="danger"
          size="sm"
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
        >
          {deleteArmed ? t("common.confirmDelete") : t("projects.delete")}
        </Button>
      </div>

      <h2 className="mb-4 text-xl font-bold text-fg">{project.name}</h2>

      <div className="flex flex-col gap-4">
        <InfoCard
          project={project}
          pid={pid}
          editOpen={editOpen}
          onEditClose={() => setEditOpen(false)}
        />
        <ReferentialsCard pid={pid} />
        <FilesCard pid={pid} />
        <AnalysisCard pid={pid} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CreateForm — formulaire de création de projet (inchangé)
// ─────────────────────────────────────────────────────────────────────────────

function CreateForm({ onCancel }: { onCancel: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [vision, setVision] = useState(false);

  const mutation = useMutation({
    mutationFn: resources.projects.create,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
      onCancel();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    mutation.mutate({ name: name.trim(), description, vision_enabled: vision });
  };

  const inputCls =
    "w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-fg placeholder-fg-muted focus:outline-none focus:ring-2 focus:ring-brand-blue-light";

  return (
    <form onSubmit={handleSubmit} className="mb-6 rounded-lg border border-border bg-card p-5 shadow-card">
      <div className="mb-3">
        <label className="mb-1 block text-sm font-medium text-fg">{t("projects.name")}</label>
        <input
          autoFocus
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("projects.namePlaceholder")}
          className={inputCls}
          maxLength={255}
          required
        />
      </div>
      <div className="mb-3">
        <label className="mb-1 block text-sm font-medium text-fg">{t("projects.description")}</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("projects.descriptionPlaceholder")}
          rows={2}
          className={inputCls}
          maxLength={4000}
        />
      </div>
      <label className="mb-4 flex cursor-pointer items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={vision}
          onChange={(e) => setVision(e.target.checked)}
          className="h-4 w-4 rounded"
        />
        {t("projects.visionEnabled")}
      </label>
      {mutation.isError && (
        <p className="mb-3 text-sm text-danger">{t("errors.generic")}</p>
      )}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={mutation.isPending || !name.trim()}>
          {mutation.isPending ? t("common.loading") : t("projects.create")}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
      </div>
    </form>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ProjectRow — ligne cliquable + double-clic suppression
// ─────────────────────────────────────────────────────────────────────────────

function ProjectRow({
  project, onOpen,
}: {
  project: Project;
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [armed, setArmed] = useState(false);
  const armTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const deleteMutation = useMutation({
    mutationFn: () => resources.projects.delete(project.id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["projects"] }),
  });

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (armed) {
      if (armTimer.current) clearTimeout(armTimer.current);
      setArmed(false);
      deleteMutation.mutate();
    } else {
      if (armTimer.current) clearTimeout(armTimer.current);
      setArmed(true);
      armTimer.current = setTimeout(() => setArmed(false), 3000);
    }
  };

  const date = new Date(project.created_at).toLocaleDateString();

  return (
    <div
      className="flex cursor-pointer items-center justify-between rounded-lg border border-border bg-card px-5 py-4 shadow-card transition-colors hover:bg-card-hover"
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onOpen()}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-fg">{project.name}</p>
        {project.description && (
          <p className="mt-0.5 truncate text-sm text-fg-muted">{project.description}</p>
        )}
        <p className="mt-1 text-xs text-fg-muted">
          {t("projects.createdAt")} {date}
          {project.vision_enabled && (
            <span className="ml-2 rounded bg-brand/20 px-1.5 py-0.5 text-xs text-brand-blue-light">
              Vision
            </span>
          )}
        </p>
      </div>
      <div onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className={[
            "ml-4 shrink-0 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            armed
              ? "bg-danger text-white hover:bg-danger/80"
              : "border border-border text-fg-muted hover:border-danger hover:text-danger",
          ].join(" ")}
        >
          {armed ? t("projects.deleteArm") : t("common.delete")}
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ProjectsList — liste des projets + formulaire création
// ─────────────────────────────────────────────────────────────────────────────

function ProjectsList({ onOpenDetail }: { onOpenDetail: (pid: string) => void }) {
  const { t } = useTranslation();
  const [showForm, setShowForm] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: resources.projects.list,
  });

  return (
    <>
      <div className="mb-6 flex items-start justify-between">
        {!showForm && (
          <Button variant="primary" onClick={() => setShowForm(true)}>
            {t("projects.new")}
          </Button>
        )}
      </div>

      {showForm && <CreateForm onCancel={() => setShowForm(false)} />}

      {isLoading && <p className="text-fg-muted">{t("common.loading")}</p>}

      {isError && (
        <div className="flex items-center gap-3 rounded-lg border border-danger/30 bg-card p-4 text-sm text-danger">
          <span>{t("errors.generic")}</span>
          <button
            type="button"
            onClick={() => void refetch()}
            className="underline hover:no-underline"
          >
            {t("common.retry")}
          </button>
        </div>
      )}

      {data && data.length === 0 && !showForm && (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-fg-muted shadow-card">
          {t("projects.empty")}
        </div>
      )}

      {data && data.length > 0 && (
        <div className="flex flex-col gap-3">
          {data.map((p) => (
            <ProjectRow key={p.id} project={p} onOpen={() => onOpenDetail(p.id)} />
          ))}
        </div>
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Projects — route export : gère le switch liste / detail + ?pid= deep link
// ─────────────────────────────────────────────────────────────────────────────

export function Projects() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const pidParam = searchParams.get("pid");
  const [selectedPid, setSelectedPid] = useState<string | null>(pidParam);

  useEffect(() => { if (pidParam) setSearchParams({}, { replace: true }); }, []);

  return (
    <div className="px-8 py-6">
      <PageHeader title={t("nav.projects")} subtitle={t("page.projects")} />

      {selectedPid ? (
        <ProjectDetail pid={selectedPid} onBack={() => setSelectedPid(null)} />
      ) : (
        <ProjectsList onOpenDetail={(pid) => setSelectedPid(pid)} />
      )}
    </div>
  );
}
