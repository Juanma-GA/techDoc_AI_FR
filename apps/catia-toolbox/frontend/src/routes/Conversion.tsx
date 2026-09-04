import { Checkbox } from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  conversionApi,
  exportUrl,
  importsApi,
  settingsApi,
  type ConversionExecDto,
  type ConversionItemDto,
  type ConversionRunDto,
  type SettingsDto,
} from "../lib/api";
import { FilePicker } from "../components/FilePicker";
import { useWorkspace } from "../stores/workspace";

const ZIP_EXTS = [".zip"];

/** Config licence flottante Composer (partagee avec l'onglet Parametres). */
function ComposerLicenseCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const settingsQuery = useQuery<SettingsDto>({ queryKey: ["settings"], queryFn: settingsApi.read });
  const [draft, setDraft] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const value = draft ?? settingsQuery.data?.composer_license_server ?? "";

  const saveMutation = useMutation({
    mutationFn: () => settingsApi.write({ composer_license_server: value.trim() }),
    onSuccess: () => {
      setNotice(t("settings.saved"));
      void qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  return (
    <article className="card">
      <h2 className="card-title">{t("settings.composerTitle")}</h2>
      <p className="banner info">{t("settings.composerNotice")}</p>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="grow field">
          <label htmlFor="conv-lic" className="field-label">
            {t("settings.composerLicense")}
          </label>
          <input
            id="conv-lic"
            className="input mono"
            value={value}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="4085@serveur-licence"
          />
          <p className="hint">{t("settings.composerHint")}</p>
        </div>
        <button
          type="button"
          className="btn primary small"
          onClick={() => {
            setNotice(null);
            saveMutation.mutate();
          }}
          disabled={saveMutation.isPending}
        >
          {saveMutation.isPending ? <span className="spinner" /> : null}
          <span>{t("settings.save")}</span>
        </button>
        {notice ? <span className="success">{notice}</span> : null}
      </div>
    </article>
  );
}

export function Conversion() {
  const { t } = useTranslation();
  const importId = useWorkspace((s) => s.importId);
  const setImport = useWorkspace((s) => s.setImport);

  const [folderPath, setFolderPath] = useState("");
  const [selection, setSelection] = useState<string[]>([]);
  const [zipPath, setZipPath] = useState("");
  const [sourceLabel, setSourceLabel] = useState("");
  const [outputName, setOutputName] = useState("");
  const [run, setRun] = useState<ConversionRunDto | null>(null);
  const [items, setItems] = useState<ConversionItemDto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [execOut, setExecOut] = useState<ConversionExecDto | null>(null);
  const [execArmed, setExecArmed] = useState(false);
  const armTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onImported = (id: string, label: string) => {
    setImport(id);
    setSourceLabel(label);
    const output = `${label}_Converti`;
    setOutputName(output); // dossier de sortie auto, modifiable
    setExecOut(null);
    setError(null);
    // Affiche tout de suite la liste des fichiers a convertir.
    planMutation.mutate({ id, output });
  };

  const importFolder = useMutation({
    mutationFn: () => importsApi.scan(folderPath.trim()),
    onSuccess: (imp) => onImported(imp.id, imp.root_label),
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  const importSelection = useMutation({
    mutationFn: () => importsApi.select(selection, "input"),
    onSuccess: (imp) => {
      onImported(imp.id, imp.root_label);
      setSelection([]);
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  const importZip = useMutation({
    mutationFn: () => importsApi.zip(zipPath.trim()),
    onSuccess: (imp) => onImported(imp.id, imp.root_label),
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  const planMutation = useMutation({
    mutationFn: async ({ id, output }: { id: string; output: string }) => {
      const r = await conversionApi.run(id, { target_dir: output.trim() });
      const it = await conversionApi.items(r.id);
      return { r, it };
    },
    onSuccess: ({ r, it }) => {
      setError(null);
      setRun(r);
      setItems(it);
      setExecOut(null);
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  const disarm = () => {
    if (armTimer.current) clearTimeout(armTimer.current);
    armTimer.current = null;
    setExecArmed(false);
  };

  const executeMutation = useMutation({
    mutationFn: ({ dryRun, confirm }: { dryRun: boolean; confirm: boolean }) =>
      conversionApi.execute(run!.id, dryRun, confirm),
    onSuccess: (out) => {
      disarm();
      setError(null);
      setExecOut(out);
    },
    onError: (e) => {
      disarm();
      setError(e instanceof ApiClientError ? e.message : String(e));
    },
  });

  const onExecuteReal = () => {
    if (!execArmed) {
      setExecArmed(true);
      armTimer.current = setTimeout(() => setExecArmed(false), 3000);
      return;
    }
    executeMutation.mutate({ dryRun: false, confirm: true });
  };

  // Selection optimiste : bascule tout de suite l'affichage, puis persiste ;
  // en cas d'echec, on revient en arriere et on affiche l'erreur.
  const setStatus = (id: string, checked: boolean) => {
    const status = checked ? "accepted" : "rejected";
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, status } : it)));
    conversionApi.setItem(run!.id, id, status).catch((e) => {
      setError(e instanceof ApiClientError ? e.message : String(e));
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, status: checked ? "rejected" : "accepted" } : it)));
    });
  };

  const setAll = (checked: boolean) => {
    const status = checked ? "accepted" : "rejected";
    const prev = items;
    setItems((cur) => cur.map((it) => ({ ...it, status })));
    conversionApi.bulkStatus(run!.id, items.map((it) => it.id), status).catch((e) => {
      setError(e instanceof ApiClientError ? e.message : String(e));
      setItems(prev);
    });
  };

  const outputDir =
    run && typeof run.summary.output_dir === "string" ? (run.summary.output_dir as string) : "";
  const selectedCount = items.filter((it) => it.status === "accepted").length;

  return (
    <div className="grow form" style={{ maxWidth: "56rem" }}>
      {/* ---- 0. Workflow ---- */}
      <article className="card">
        <h2 className="card-title">{t("conversion.workflowTitle")}</h2>
        <ol style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.7 }}>
          <li>{t("conversion.workflow1")}</li>
          <li>{t("conversion.workflow2")}</li>
          <li>{t("conversion.workflow3")}</li>
          <li>{t("conversion.workflow4")}</li>
          <li>{t("conversion.workflow5")}</li>
        </ol>
        <p className="banner warn" style={{ marginTop: "0.75rem" }}>
          {t("conversion.workflowScriptNote")}
        </p>
      </article>

      {/* ---- Licence Composer (injectee dans le script genere) ---- */}
      <ComposerLicenseCard />

      {/* ---- 1. Source a convertir : dossier ou zip ---- */}
      <article className="card">
        <h2 className="card-title">{t("conversion.sourceTitle")}</h2>
        <p className="banner info">{t("conversion.sourceBanner")}</p>

        <div className="field">
          <label className="field-label">{t("conversion.folderLabel")}</label>
          <FilePicker
            mode="multi"
            exts={[]}
            value={selection}
            onChange={setSelection}
            onFolderChange={setFolderPath}
          />
          <div className="row" style={{ marginTop: "0.5rem" }}>
            <button
              type="button"
              className="btn secondary small"
              onClick={() => importFolder.mutate()}
              disabled={!folderPath.trim() || importFolder.isPending}
            >
              {importFolder.isPending ? <span className="spinner" /> : null}
              <span>{t("conversion.importFolder")}</span>
            </button>
            <button
              type="button"
              className="btn secondary small"
              onClick={() => importSelection.mutate()}
              disabled={selection.length === 0 || importSelection.isPending}
            >
              {importSelection.isPending ? <span className="spinner" /> : null}
              <span>{t("conversion.importSelection", { count: selection.length })}</span>
            </button>
          </div>
        </div>

        <div className="field" style={{ marginTop: "0.75rem" }}>
          <label className="field-label">{t("conversion.zipLabel")}</label>
          <FilePicker exts={ZIP_EXTS} value={zipPath} onChange={setZipPath} sheetPreview={false} />
          <div className="row" style={{ marginTop: "0.5rem" }}>
            <button
              type="button"
              className="btn secondary small"
              onClick={() => importZip.mutate()}
              disabled={!zipPath.trim() || importZip.isPending}
            >
              {importZip.isPending ? <span className="spinner" /> : null}
              <span>{t("conversion.importZip")}</span>
            </button>
          </div>
        </div>

        {sourceLabel ? <p className="success">{t("conversion.currentSource", { name: sourceLabel })}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </article>

      {/* ---- 2. Dossier de sortie + generation du plan ---- */}
      <article className="card">
        <h2 className="card-title">{t("conversion.planTitle")}</h2>
        <p className="banner warn">
          <strong>{t("export.dryRunTitle")}</strong> {t("conversion.dryRun")}
        </p>

        <div className="field">
          <label className="field-label" htmlFor="conv-output">{t("conversion.outputNameLabel")}</label>
          <input
            id="conv-output"
            className="input"
            value={outputName}
            onChange={(e) => setOutputName(e.target.value)}
            placeholder="NomDossierInput_Converti"
            disabled={!importId}
          />
          <p className="hint">{t("conversion.outputInfo")}</p>
        </div>

        <button
          type="button"
          className="btn primary"
          onClick={() => planMutation.mutate({ id: importId as string, output: outputName })}
          disabled={!importId || !outputName.trim() || planMutation.isPending}
        >
          {planMutation.isPending ? <span className="spinner" /> : null}
          <span>{t("conversion.generate")}</span>
        </button>
        {!importId ? <p className="hint" style={{ marginTop: "0.5rem" }}>{t("conversion.sourceRequired")}</p> : null}
      </article>

      {/* ---- 3. Plan : fichiers a convertir (selection) ---- */}
      {run ? (
        <article className="card">
          <h2 className="card-title">{t("conversion.resultTitle", { count: items.length })}</h2>
          {outputDir ? <p className="banner info">{t("conversion.outputFolder", { name: outputDir })}</p> : null}

          <div className="row" style={{ margin: "0.5rem 0" }}>
            <button type="button" className="btn ghost small" onClick={() => setAll(true)}>
              {t("conversion.selectAll")}
            </button>
            <button type="button" className="btn ghost small" onClick={() => setAll(false)}>
              {t("conversion.deselectAll")}
            </button>
            <a href={exportUrl.conversionCsv(run.id)}>
              <button type="button" className="btn secondary small">{t("common.exportCsv")}</button>
            </a>
            <a href={exportUrl.conversionScript(run.id)}>
              <button type="button" className="btn secondary small">{t("conversion.composerScript")}</button>
            </a>
            <span className="hint" style={{ marginLeft: "auto" }}>
              {t("conversion.selected", { count: selectedCount, total: items.length })}
            </span>
          </div>

          {items.length === 0 ? (
            <p className="hint">{t("conversion.noItems")}</p>
          ) : (
            <div style={{ maxHeight: "30rem", overflow: "auto" }}>
              <table className="tbl" style={{ whiteSpace: "nowrap" }}>
                <thead>
                  <tr>
                    <th style={{ position: "sticky", top: 0, background: "var(--bg-2)", textAlign: "center" }}>
                      {t("conversion.colKeep")}
                    </th>
                    <th style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>{t("conversion.colSource")}</th>
                    <th style={{ position: "sticky", top: 0, background: "var(--bg-2)" }}>{t("conversion.colTarget")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it) => {
                    const kept = it.status === "accepted";
                    return (
                      <tr key={it.id} style={kept ? undefined : { opacity: 0.5 }}>
                        <td style={{ textAlign: "center" }}>
                          <Checkbox
                            checked={kept}
                            onCheckedChange={(v) => setStatus(it.id, v === true)}
                            aria-label={it.source_path}
                          />
                        </td>
                        <td style={{ fontFamily: '"JetBrains Mono", monospace' }}>{it.source_path}</td>
                        <td style={{ fontFamily: '"JetBrains Mono", monospace' }}>{it.target_path}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* ---- Execution locale (non destructive) ---- */}
          <div style={{ marginTop: "1rem", borderTop: "1px solid var(--border)", paddingTop: "0.75rem" }}>
            <h3 className="card-title" style={{ fontSize: "0.95rem" }}>{t("conversion.execTitle")}</h3>
            <p className="hint">{t("conversion.execHint")}</p>
            <div className="row" style={{ marginTop: "0.5rem" }}>
              <button
                type="button"
                className="btn secondary small"
                onClick={() => executeMutation.mutate({ dryRun: true, confirm: false })}
                disabled={executeMutation.isPending || selectedCount === 0}
              >
                {executeMutation.isPending ? <span className="spinner" /> : null}
                <span>{t("conversion.execDry")}</span>
              </button>
              <button
                type="button"
                className="btn danger small"
                onClick={onExecuteReal}
                disabled={executeMutation.isPending || selectedCount === 0}
              >
                <span>{execArmed ? t("conversion.execConfirm") : t("conversion.execReal")}</span>
              </button>
            </div>

            {execOut ? (
              <div style={{ marginTop: "0.75rem" }}>
                <p className={execOut.returncode === 0 ? "success" : "error"}>
                  {t("conversion.execResult", {
                    mode: execOut.dry_run ? "dry-run" : t("conversion.execModeReal"),
                    code: execOut.returncode,
                  })}
                </p>
                {execOut.base ? <p className="hint">{t("conversion.execBase", { base: execOut.base })}</p> : null}
                <pre
                  style={{
                    maxHeight: "20rem",
                    overflow: "auto",
                    background: "var(--bg-2)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: "0.5rem",
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: "0.78rem",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {execOut.stdout || "(vide)"}
                  {execOut.stderr ? `\n--- stderr ---\n${execOut.stderr}` : ""}
                </pre>
              </div>
            ) : null}
          </div>
        </article>
      ) : null}
    </div>
  );
}
