import { useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  importChecklist,
  rulesInspect,
  type CompiledRuleSummary,
  type SheetInfo,
} from "../hooks/useRules";
import { API_BASE_URL } from "../lib/api";
import { useFiltersStore } from "../stores/filtersStore";

type Mode = "replace" | "add";
type ImportPhase = "inspect" | "compile";

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
 * Import d'une checklist Excel : choix du fichier -> apercu (inspect) -> onglet +
 * ligne d'en-tete + mapping des colonnes (tableau cliquable) -> import. Inspire
 * de l'UI corpus-agent. Les regles deterministes sont actives des compilation.
 */
export function ChecklistImportCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const setChecklistActive = useFiltersStore((state) => state.setChecklistActive);

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
  const [mode, setMode] = useState<Mode>("replace");
  const [msg, setMsg] = useState("");
  const [phase, setPhase] = useState<ImportPhase | null>(null);
  const [diag, setDiag] = useState("");
  const [compiledRules, setCompiledRules] = useState<CompiledRuleSummary[]>([]);
  const busy = phase !== null;

  const sheet = sheets[sheetIdx];
  const ncols = sheet ? Math.max(0, ...sheet.rows.map((r) => r.length)) : 0;
  const colOptions = Array.from({ length: ncols }, (_, i) => i);
  const headerCells = sheet?.rows[headerRow] ?? [];
  const colOptionLabel = (c: number): string => {
    const name = String(headerCells[c] ?? "").trim();
    return name ? `${name} (${colLabel(c)})` : colLabel(c);
  };

  async function onPick(f: File | null): Promise<void> {
    setFile(f);
    setSheets([]);
    setMsg("");
    setDiag("");
    setCompiledRules([]);
    if (!f) return;
    setPhase("inspect");
    try {
      const out = await rulesInspect(f);
      const sh = out?.sheets ?? [];
      setDiag(
        t("rules.import.inspectOk", {
          count: sh.length,
          names: sh.map((s) => s.name).join(", ") || "—",
        }),
      );
      setSheets(sh);
      setSheetIdx(0);
      setHeaderRow(sh[0]?.header_row ?? 0);
      setTopicCol(0);
      setCheckCol(1);
      setSeverityCol(null);
      setHandlingCol(null);
      setZoneCol(null);
      setContextCol(null);
    } catch (e) {
      setDiag(t("rules.import.inspectFail", { error: e instanceof Error ? e.message : String(e) }));
    } finally {
      setPhase(null);
    }
  }

  function resultMsg(r: { imported: number; replaced_count: number; skipped_manual: number }): string {
    return t("rules.import.result", {
      imported: r.imported,
      replaced: r.replaced_count,
      skipped: r.skipped_manual,
    });
  }

  async function doDirectImport(): Promise<void> {
    if (!file) return;
    setPhase("compile");
    setMsg("");
    try {
      const r = await importChecklist(file, { mode });
      setMsg(resultMsg(r));
      setCompiledRules(r.rules);
      setChecklistActive(true);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["rules"] }),
        qc.invalidateQueries({ queryKey: ["compiled-rules"] }),
      ]);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setPhase(null);
    }
  }

  async function doImport(): Promise<void> {
    if (!file || checkCol == null) return;
    setPhase("compile");
    setMsg("");
    try {
      const r = await importChecklist(file, {
        mode,
        sheet: sheet?.name,
        header_row: headerRow,
        topic: topicCol,
        check: checkCol,
        severity: severityCol,
        handling: handlingCol,
        zone: zoneCol,
        context: contextCol != null ? [contextCol] : [],
      });
      setMsg(resultMsg(r));
      setCompiledRules(r.rules);
      setChecklistActive(true);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["rules"] }),
        qc.invalidateQueries({ queryKey: ["compiled-rules"] }),
      ]);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setPhase(null);
    }
  }

  // Surbrillance de la colonne mappee (tokens design, pas de hex en dur).
  const cellBg = (ci: number): string | undefined => {
    if (ci === checkCol) return "var(--brand-light)";
    if (topicCol != null && ci === topicCol) return "var(--card-hover)";
    if (contextCol != null && ci === contextCol) return "var(--bg-2)";
    return undefined;
  };

  return (
    <div className="card">
      <div className="card-title">{t("rules.import.title")}</div>
      <p className="card-sub">{t("rules.import.subtitle")}</p>

      <div className="row" style={{ gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <a className="btn ghost small" href={`${API_BASE_URL}/rules/template`}>
          {t("rules.import.template")}
        </a>
        <label className="label">
          {t("rules.import.mode")}
          <select
            className="input"
            style={{ width: "auto", marginLeft: 6 }}
            value={mode}
            onChange={(e) => setMode(e.target.value as Mode)}
          >
            <option value="replace">{t("rules.import.modeReplace")}</option>
            <option value="add">{t("rules.import.modeAdd")}</option>
          </select>
        </label>
        <input
          type="file"
          accept=".xlsx,.xlsm"
          disabled={busy}
          onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        />
      </div>

      {phase ? <ChecklistImportProgress phase={phase} /> : null}

      {mode === "replace" ? (
        <p className="banner warn" style={{ marginTop: 8 }}>
          {t("rules.import.replaceWarn")}
        </p>
      ) : null}

      {/* Fichier charge + import direct (auto-detection). */}
      {file ? (
        <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 8 }}>
          <span className="badge default">
            <Upload size={12} /> {file.name}
          </span>
          <button
            type="button"
            className="btn primary small"
            disabled={busy}
            onClick={doDirectImport}
          >
            {phase === "compile" ? t("rules.import.importing") : t("rules.import.direct")}
          </button>
          <span className="label">{t("rules.import.directHint")}</span>
        </div>
      ) : null}

      {diag ? (
        <p className="label" style={{ fontFamily: "var(--font-mono)", marginTop: 6 }}>
          {diag}
        </p>
      ) : null}

      {/* Apercu + mapping interactif. */}
      {sheet ? (
        <div style={{ marginTop: 10 }}>
          <div className="row" style={{ gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            {sheets.length > 1 ? (
              <label className="label">
                {t("rules.import.sheet")}
                <select
                  className="input"
                  style={{ marginLeft: 6 }}
                  value={sheetIdx}
                  onChange={(e) => {
                    const i = Number(e.target.value);
                    setSheetIdx(i);
                    setHeaderRow(sheets[i]?.header_row ?? 0);
                  }}
                >
                  {sheets.map((s, i) => (
                    <option key={s.name} value={i}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label className="label">
              {t("rules.import.headerRow")}
              <select
                className="input"
                style={{ marginLeft: 6 }}
                value={headerRow}
                onChange={(e) => setHeaderRow(Number(e.target.value))}
              >
                {sheet.rows.map((_, ri) => (
                  <option key={ri} value={ri}>
                    {ri + 1}
                  </option>
                ))}
              </select>
            </label>
            <span className="label" style={{ opacity: 0.75 }}>{t("rules.import.clickHeader")}</span>
          </div>

          <div className="table-scroll" style={{ marginTop: 8 }}>
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
                      const bg = cellBg(ci);
                      const isZone = zoneCol != null && ci === zoneCol;
                      return (
                        <td
                          key={ci}
                          style={{
                            ...(bg ? { background: bg } : {}),
                            ...(isZone ? { opacity: 0.4 } : {}),
                            padding: "2px 6px",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {r[ci] ?? ""}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="row" style={{ gap: 12, flexWrap: "wrap", marginTop: 10 }}>
            <ColSelect label={t("rules.import.topicCol")} value={topicCol} onChange={setTopicCol} options={colOptions} labelOf={colOptionLabel} allowNone />
            <ColSelect label={t("rules.import.checkCol")} value={checkCol} onChange={setCheckCol} options={colOptions} labelOf={colOptionLabel} allowNone />
            <ColSelect label={t("rules.import.severityCol")} value={severityCol} onChange={setSeverityCol} options={colOptions} labelOf={colOptionLabel} autoLabel={t("rules.import.colAuto")} />
            <ColSelect label={t("rules.import.handlingCol")} value={handlingCol} onChange={setHandlingCol} options={colOptions} labelOf={colOptionLabel} autoLabel={t("rules.import.colAuto")} />
            <ColSelect label={t("rules.import.contextCol")} value={contextCol} onChange={setContextCol} options={colOptions} labelOf={colOptionLabel} autoLabel={t("rules.import.colAuto")} />
          </div>

          <button
            type="button"
            className="btn primary"
            style={{ marginTop: 10 }}
            disabled={busy || checkCol == null}
            onClick={doImport}
          >
            <Upload size={13} />
            {busy ? t("rules.import.importing") : t("rules.import.cta")}
          </button>
        </div>
      ) : null}

      {msg ? (
        <p className="banner ok" style={{ marginTop: 8 }}>
          {msg}
        </p>
      ) : null}
      {compiledRules.length > 0 ? (
        <div className="table-scroll" style={{ marginTop: 8 }}>
          <table className="rules-table">
            <thead>
              <tr>
                <th>{t("rules.compiled.status")}</th>
                <th>{t("rules.form.name")}</th>
                <th>{t("rules.compiled.detail")}</th>
              </tr>
            </thead>
            <tbody>
              <CompiledRuleRows rules={compiledRules} />
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

export function ChecklistImportProgress({ phase }: { phase: ImportPhase }) {
  const { t } = useTranslation();
  const label = t(`rules.import.progress.${phase}`);
  return (
    <div className="checklist-import-progress">
      <span className="label">{label}</span>
      <div className="progress" role="progressbar" aria-label={label}>
        <div className="progress-bar indeterminate" />
      </div>
    </div>
  );
}

export function CompiledRuleRows({ rules }: { rules: CompiledRuleSummary[] }) {
  const { t } = useTranslation();
  return rules.map((rule) => (
    <tr key={rule.id} data-execution={rule.execution}>
      <td>
        <span
          className={`badge ${
            rule.execution === "deterministic" || rule.execution === "semantic"
              ? "success"
              : "default"
          }`}
        >
          {t(`rules.compiled.${rule.execution}`)}
        </span>
      </td>
      <td>{t(`rules.catalog.${rule.id}`, { defaultValue: rule.topic })}</td>
      <td>{rule.detail ?? t("rules.compiled.activeImmediately")}</td>
    </tr>
  ));
}

function ColSelect({
  label,
  value,
  onChange,
  options,
  labelOf,
  allowNone,
  autoLabel,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  options: number[];
  labelOf: (c: number) => string;
  allowNone?: boolean;
  autoLabel?: string;
}): JSX.Element {
  return (
    <label className="label">
      {label}
      <select
        className="input"
        style={{ marginLeft: 6 }}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      >
        <option value="">{allowNone ? "—" : (autoLabel ?? "—")}</option>
        {options.map((c) => (
          <option key={c} value={c}>
            {labelOf(c)}
          </option>
        ))}
      </select>
    </label>
  );
}
