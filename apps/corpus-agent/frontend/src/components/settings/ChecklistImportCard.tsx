import { FileDropzone } from "@internal/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { settingsApi } from "../../lib/api";
import type { ChecklistImportMode, SheetInfo } from "../../lib/types";

const MODES: ChecklistImportMode[] = ["replace", "add", "update", "overwrite"];

/** Index colonne 0-based -> lettre tableur (A, B, ... AA). */
function colLabel(idx: number): string {
  let n = idx;
  let s = "";
  do {
    s = String.fromCharCode(65 + (n % 26)) + s;
    n = Math.floor(n / 26) - 1;
  } while (n >= 0);
  return s;
}

/**
 * Import d'une checklist Excel en regles personnalisees : apercu (inspect) ->
 * choix de l'onglet + ligne d'en-tete + colonnes -> import selon un mode. Les
 * regles importees arrivent dans la file de validation (cf. CustomRulesCard).
 */
export function ChecklistImportCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [sheets, setSheets] = useState<SheetInfo[]>([]);
  const [sheetIdx, setSheetIdx] = useState(0);
  const [headerRow, setHeaderRow] = useState(0);
  const [topicCol, setTopicCol] = useState<number | null>(0);
  const [checkCol, setCheckCol] = useState<number | null>(1);
  const [severityCol, setSeverityCol] = useState<number | null>(null);
  const [handlingCol, setHandlingCol] = useState<number | null>(null);
  const [zoneCol, setZoneCol] = useState<number | null>(null);
  const [contextCol, setContextCol] = useState<number | null>(null);
  // "overwrite" (Fusionner) par defaut : upsert non destructif (met a jour
  // l'existant + cree le nouveau). "replace" purge toute la checklist -> ne
  // doit jamais etre la valeur preselectionnee au chargement de la page.
  const [mode, setMode] = useState<ChecklistImportMode>("overwrite");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [directBusy, setDirectBusy] = useState(false);
  // Diagnostic visible du dernier appel `inspect` (nb d'onglets ou erreur) —
  // permet de voir ce que renvoie le backend sans ouvrir les DevTools.
  const [diag, setDiag] = useState<string>("");

  const sheet = sheets[sheetIdx];
  const ncols = sheet ? Math.max(0, ...sheet.rows.map((r) => r.length)) : 0;

  /**
   * Selectionne un onglet et precharge ligne d'en-tete + colonnes a partir des
   * `roles` reconnus par le backend. Sans roles (onglet non reconnu), on garde
   * les defauts historiques colonne A = sujet, colonne B = verification.
   */
  function applySheet(sh: SheetInfo[], i: number) {
    const s = sh[i];
    const roles = s?.roles ?? null;
    setSheetIdx(i);
    setHeaderRow(s?.header_row ?? 0);
    setTopicCol(roles ? roles.topic ?? null : 0);
    setCheckCol(roles ? roles.check ?? null : 1);
    setSeverityCol(roles?.severity ?? null);
    setHandlingCol(roles?.handling ?? null);
    setZoneCol(roles?.zone ?? null);
    setContextCol(roles?.context ?? null);
  }

  async function onPick(f: File | null) {
    setFile(f);
    setSheets([]);
    setMsg("");
    setDiag("");
    if (!f) return;
    setBusy(true);
    try {
      const out = await settingsApi.rulesInspect(f);
      const sh = out?.sheets ?? [];
      const names = sh.map((s) => s.name).join(", ") || t("settings.importNoSheets");
      setDiag(t("settings.importInspectOk", { count: sh.length, names }));
      setSheets(sh);
      // Ouvre le 1er onglet ou le backend a reconnu une colonne « check » : la
      // checklist n'est pas toujours le 1er onglet (page de garde, annexes).
      const best = sh.findIndex((s) => s.roles?.check != null);
      applySheet(sh, best >= 0 ? best : 0);
    } catch (e) {
      // Le message d'exception brut (souvent une lib Python) reste en
      // anglais quel que soit la langue de l'UI : limitation acceptee, seul
      // le texte autour (« inspect ECHEC ») est traduit.
      const m = e instanceof Error ? e.message : String(e);
      setDiag(t("settings.importInspectFailed", { message: m }));
      setMsg(m);
    } finally {
      setBusy(false);
    }
  }

  // Import direct : saute l'aperçu interactif (appel `inspect`) et laisse le
  // backend auto-détecter les colonnes sujet/vérification. Disponible dès qu'un
  // fichier est choisi — chemin de secours quand l'aperçu ne se charge pas.
  async function doDirectImport() {
    if (!file) return;
    setDirectBusy(true);
    setMsg("");
    try {
      const r = await settingsApi.importChecklist(file, { mode });
      setMsg(t("settings.importDone", { created: r.created, updated: r.updated, pending: r.pending }));
      await qc.invalidateQueries({ queryKey: ["rules-legacy"] });
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setDirectBusy(false);
    }
  }

  async function doImport() {
    if (!file || checkCol == null) return;
    setBusy(true);
    setMsg("");
    try {
      const r = await settingsApi.importChecklist(file, {
        sheet: sheet?.name,
        header_row: headerRow,
        topic_col: topicCol,
        check_col: checkCol,
        severity_col: severityCol,
        handling_col: handlingCol,
        zone_col: zoneCol,
        context_cols: contextCol != null ? [contextCol] : [],
        mode,
      });
      setMsg(t("settings.importDone", { created: r.created, updated: r.updated, pending: r.pending }));
      await qc.invalidateQueries({ queryKey: ["rules-legacy"] });
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const colOptions = Array.from({ length: ncols }, (_, i) => i);
  // Libellé d'une colonne dans les menus : le NOM détecté (en-tête de la ligne
  // sélectionnée) plutôt que la seule lettre ; lettre en repli si l'en-tête est
  // vide, et rappelée entre parenthèses pour se repérer dans la grille.
  const headerCells = sheet?.rows[headerRow] ?? [];
  const colOptionLabel = (c: number): string => {
    const name = String(headerCells[c] ?? "").trim();
    return name ? `${name} (${colLabel(c)})` : colLabel(c);
  };

  return (
    <div className="card">
      <h2 className="card-title">{t("settings.importTitle")}</h2>
      <div className="label">{t("settings.importHint")}</div>
      <a className="btn ghost small" href={settingsApi.checklistTemplateUrl()} style={{ alignSelf: "flex-start" }}>
        {t("settings.downloadTemplate")}
      </a>

      <div className="row" style={{ alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
        <label className="label">
          {t("settings.importMode")}
          <select className="input" value={mode} onChange={(e) => setMode(e.target.value as ChecklistImportMode)}>
            {MODES.map((m) => (
              <option key={m} value={m}>{t(`settings.importMode.${m}`)}</option>
            ))}
          </select>
        </label>
        <FileDropzone
          accept=".xlsx,.xlsm"
          multiple={false}
          disabled={busy || directBusy}
          label={t("settings.chooseChecklist")}
          description={file?.name ?? t("settings.checklistFormats")}
          onFiles={(files) => void onPick(files[0] ?? null)}
        />
      </div>
      {mode === "replace" && <div className="banner warn">{t("settings.importReplaceWarn")}</div>}

      {file && (
        <div className="row" style={{ gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" className="btn primary" disabled={directBusy} onClick={doDirectImport}>
            {directBusy ? t("common.loading") : t("settings.importDirect")}
          </button>
          <span className="label">{t("settings.importDirectHint")}</span>
        </div>
      )}

      {file && busy && sheets.length === 0 && (
        <div className="label"><span className="spinner" /> {t("settings.importLoadingPreview")}</div>
      )}
      {file && !busy && sheets.length === 0 && (
        <div className="label">{t("settings.importNoPreview")}</div>
      )}
      {diag && (
        <div className="label" style={{ fontFamily: "monospace", fontSize: "0.85em", opacity: 0.85 }}>
          {diag}
        </div>
      )}

      {sheet && (
        <>
          {sheets.length > 1 && (
            <label className="label">
              {t("settings.importSheet")}
              <select
                className="input"
                value={sheetIdx}
                onChange={(e) => applySheet(sheets, Number(e.target.value))}
              >
                {sheets.map((s, i) => (
                  <option key={s.name} value={i}>{s.name}</option>
                ))}
              </select>
            </label>
          )}
          <div className="row" style={{ gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
            <label className="label">
              {t("settings.importHeaderRow")}
              <select
                className="input"
                value={headerRow}
                onChange={(e) => setHeaderRow(Number(e.target.value))}
              >
                {sheet.rows.map((_, ri) => (
                  <option key={ri} value={ri}>{ri + 1}</option>
                ))}
              </select>
            </label>
            <span className="label" style={{ opacity: 0.75 }}>{t("settings.importClickHeader")}</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="rules-table">
              <tbody>
                {sheet.rows.slice(0, 12).map((r, ri) => (
                  <tr
                    key={ri}
                    onClick={() => setHeaderRow(ri)}
                    className={ri === headerRow ? "row-selected" : ""}
                    style={{ cursor: "pointer" }}
                  >
                    <td className="label">{ri === headerRow ? "▸" : ""}</td>
                    {Array.from({ length: ncols }, (_, ci) => {
                      const isCheck = ci === checkCol;
                      const isTopic = topicCol != null && ci === topicCol;
                      const isContext = contextCol != null && ci === contextCol;
                      const isZone = zoneCol != null && ci === zoneCol;
                      const bg = isCheck
                        ? "color-mix(in srgb, var(--color-brand-blue) 22%, transparent)"
                        : isTopic
                          ? "color-mix(in srgb, var(--color-brand-blue) 10%, transparent)"
                          : isContext
                            ? "color-mix(in srgb, var(--color-semantic-success) 14%, transparent)"
                            : undefined;
                      return (
                        <td key={ci} style={{ ...(bg ? { background: bg } : {}), ...(isZone ? { opacity: 0.4 } : {}) }}>
                          {r[ci] ?? ""}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap" }}>
            <label className="label">
              {t("settings.importTopicCol")}
              <select className="input" value={topicCol ?? ""} onChange={(e) => setTopicCol(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">—</option>
                {colOptions.map((c) => <option key={c} value={c}>{colOptionLabel(c)}</option>)}
              </select>
            </label>
            <label className="label">
              {t("settings.importCheckCol")}
              <select className="input" value={checkCol ?? ""} onChange={(e) => setCheckCol(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">—</option>
                {colOptions.map((c) => <option key={c} value={c}>{colOptionLabel(c)}</option>)}
              </select>
            </label>
            <label className="label">
              {t("settings.importHandlingCol")}
              <select className="input" value={handlingCol ?? ""} onChange={(e) => setHandlingCol(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">{t("settings.importColAuto")}</option>
                {colOptions.map((c) => <option key={c} value={c}>{colOptionLabel(c)}</option>)}
              </select>
            </label>
            <label className="label">
              {t("settings.importSeverityCol")}
              <select className="input" value={severityCol ?? ""} onChange={(e) => setSeverityCol(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">{t("settings.importColAuto")}</option>
                {colOptions.map((c) => <option key={c} value={c}>{colOptionLabel(c)}</option>)}
              </select>
            </label>
            <label className="label">
              {t("settings.importZoneCol")}
              <select className="input" value={zoneCol ?? ""} onChange={(e) => setZoneCol(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">—</option>
                {colOptions.map((c) => <option key={c} value={c}>{colOptionLabel(c)}</option>)}
              </select>
            </label>
            <label className="label">
              {t("settings.importContextCol")}
              <select className="input" value={contextCol ?? ""} onChange={(e) => setContextCol(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">{t("settings.importColAuto")}</option>
                {colOptions.map((c) => <option key={c} value={c}>{colOptionLabel(c)}</option>)}
              </select>
            </label>
          </div>

          <div className="label" style={{ opacity: 0.75 }}>{t("settings.importContextNote")}</div>

          <button type="button" className="btn primary" disabled={busy || checkCol == null} onClick={doImport}>
            {busy ? t("common.loading") : t("settings.importButton")}
          </button>
        </>
      )}
      {msg && <div className="label" style={{ marginTop: "0.5rem" }}>{msg}</div>}
    </div>
  );
}
