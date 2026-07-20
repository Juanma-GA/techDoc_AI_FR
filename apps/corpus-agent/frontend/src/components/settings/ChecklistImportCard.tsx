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
  const [mode, setMode] = useState<ChecklistImportMode>("replace");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const sheet = sheets[sheetIdx];
  const ncols = sheet ? Math.max(0, ...sheet.rows.map((r) => r.length)) : 0;

  async function onPick(f: File | null) {
    setFile(f);
    setSheets([]);
    setMsg("");
    if (!f) return;
    setBusy(true);
    try {
      const out = await settingsApi.rulesInspect(f);
      setSheets(out.sheets);
      setSheetIdx(0);
      setHeaderRow(out.sheets[0]?.header_row ?? 0);
      setTopicCol(0);
      setCheckCol(1);
      setSeverityCol(null);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
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
        <input type="file" accept=".xlsx,.xlsm" onChange={(e) => onPick(e.target.files?.[0] ?? null)} />
      </div>
      {mode === "replace" && <div className="banner warn">{t("settings.importReplaceWarn")}</div>}

      {sheet && (
        <>
          {sheets.length > 1 && (
            <label className="label">
              {t("settings.importSheet")}
              <select
                className="input"
                value={sheetIdx}
                onChange={(e) => {
                  const i = Number(e.target.value);
                  setSheetIdx(i);
                  setHeaderRow(sheets[i]?.header_row ?? 0);
                }}
              >
                {sheets.map((s, i) => (
                  <option key={s.name} value={i}>{s.name}</option>
                ))}
              </select>
            </label>
          )}
          <div className="label">{t("settings.importClickHeader")}</div>
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
                    {Array.from({ length: ncols }, (_, ci) => (
                      <td key={ci}>{r[ci] ?? ""}</td>
                    ))}
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
                {colOptions.map((c) => <option key={c} value={c}>{colLabel(c)}</option>)}
              </select>
            </label>
            <label className="label">
              {t("settings.importCheckCol")}
              <select className="input" value={checkCol ?? ""} onChange={(e) => setCheckCol(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">—</option>
                {colOptions.map((c) => <option key={c} value={c}>{colLabel(c)}</option>)}
              </select>
            </label>
            <label className="label">
              {t("settings.importSeverityCol")}
              <select className="input" value={severityCol ?? ""} onChange={(e) => setSeverityCol(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">—</option>
                {colOptions.map((c) => <option key={c} value={c}>{colLabel(c)}</option>)}
              </select>
            </label>
          </div>

          <button type="button" className="btn primary" disabled={busy || checkCol == null} onClick={doImport}>
            {busy ? t("common.loading") : t("settings.importButton")}
          </button>
        </>
      )}
      {msg && <div className="label" style={{ marginTop: "0.5rem" }}>{msg}</div>}
    </div>
  );
}
