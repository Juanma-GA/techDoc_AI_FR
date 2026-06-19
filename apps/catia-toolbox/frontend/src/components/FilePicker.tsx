import { Checkbox } from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { ChevronUp, File as FileIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { browseApi, type BrowseEntryDto, type BrowseScope } from "../lib/api";

// --- Helpers partages -------------------------------------------------------

function parentPath(absPath: string, root: string): string {
  const norm = absPath.replace(/\\/g, "/").replace(/\/+$/, "");
  const rootNorm = root.replace(/\\/g, "/").replace(/\/+$/, "");
  if (!norm || norm === rootNorm) return "";
  const idx = norm.lastIndexOf("/");
  const parent = idx > 0 ? norm.slice(0, idx) : "";
  return parent.length < rootNorm.length ? rootNorm : parent;
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / 1048576).toFixed(2)} MB`;
}

const EXCEL_EXTS = [".xlsx", ".xlsm"];
function isExcel(path: string): boolean {
  const p = path.toLowerCase();
  return EXCEL_EXTS.some((x) => p.endsWith(x));
}

function matchesExts(name: string, exts: string[]): boolean {
  if (exts.length === 0) return true;
  const n = name.toLowerCase();
  return exts.some((x) => n.endsWith(x));
}

// --- Composant public -------------------------------------------------------

type CommonProps = {
  /** Extensions filtrantes (avec le point), ex: [".xlsm", ".xlsx"]. Vide = tout. */
  exts: string[];
  /** Racine navigee (defaut : "input"). */
  scope?: BrowseScope;
};

type SingleProps = CommonProps & {
  mode?: "single";
  value: string;
  onChange: (path: string) => void;
  /** Libelle du bouton toggle (defaut : "Parcourir"). */
  label?: string;
  /** Apercu onglet + premieres lignes pour les .xlsx/.xlsm. Defaut : true. */
  sheetPreview?: boolean;
};

type MultiProps = CommonProps & {
  mode: "multi";
  value: string[];
  onChange: (paths: string[]) => void;
  /** Notifie le dossier courant (pour une action "scanner ce dossier"). */
  onFolderChange?: (absPath: string) => void;
  /** Autorise la vue recursive a plat (filtrable). Defaut : true. */
  allowRecursive?: boolean;
};

export type FilePickerProps = SingleProps | MultiProps;

/**
 * Selecteur de fichier unique de l'app, decline en deux modes :
 *  - `single` : un champ + bouton qui ouvre un panneau pliable ; choisir un
 *    fichier renvoie son chemin. Apercu onglet/lignes pour les classeurs Excel.
 *  - `multi`  : panneau inline avec cases a cocher, vue niveau ou recursive,
 *    Tout cocher / Vider ; renvoie la liste des chemins coches.
 * Les deux partagent la meme navigation (fil d'Ariane, Remonter, filtre par
 * extension) et le meme rendu de lignes -> coherence entre tous les onglets.
 */
export function FilePicker(props: FilePickerProps) {
  if (props.mode === "multi") return <MultiFilePicker {...props} />;
  return <SingleFilePicker {...props} />;
}

// --- Mode single ------------------------------------------------------------

function SingleFilePicker({ exts, scope = "input", value, onChange, label, sheetPreview = true }: SingleProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState("");

  const listQuery = useQuery({
    queryKey: ["browse", scope, path],
    queryFn: () => browseApi.list(path, scope),
    enabled: open,
  });

  const data = listQuery.data;
  const atRoot = !!data && data.path === data.root;
  const entries = (data?.entries ?? []).filter((e) => e.kind === "folder" || matchesExts(e.name, exts));

  return (
    <div className="form">
      <div className="row">
        <input
          type="text"
          className="input grow"
          placeholder={t("picker.placeholder")}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="button"
          className="btn secondary"
          onClick={() => {
            if (!open) setPath("");
            setOpen((v) => !v);
          }}
        >
          {label ?? t("picker.browse")}
        </button>
      </div>

      {open ? (
        <div className="card" style={{ padding: "0.5rem" }}>
          {listQuery.isLoading ? (
            <span className="spinner" />
          ) : listQuery.isError ? (
            <p className="hint" style={{ textAlign: "center" }}>
              {(listQuery.error instanceof Error ? listQuery.error.message : String(listQuery.error)) +
                " " +
                t("picker.configureRoot")}
            </p>
          ) : data ? (
            <>
              <div className="row" style={{ marginBottom: "0.5rem" }}>
                <button
                  type="button"
                  className="btn ghost small"
                  disabled={atRoot}
                  onClick={() => setPath(parentPath(data.path, data.root))}
                >
                  {t("picker.up")}
                </button>
                <code className="hint grow" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {data.path}
                </code>
              </div>
              <div className="item-list" style={{ maxHeight: "15rem", overflow: "auto" }}>
                {entries.length ? (
                  entries.map((e) =>
                    e.kind === "folder" ? (
                      <div key={e.path} className="item-row">
                        <div className="item-actions">
                          <button type="button" className="btn ghost small" onClick={() => setPath(e.path)}>
                            {t("picker.open")}
                          </button>
                        </div>
                        <div className="item-main">
                          <span className="item-name">{e.name}/</span>
                        </div>
                      </div>
                    ) : (
                      <div key={e.path} className="item-row">
                        <div className="item-actions">
                          <button
                            type="button"
                            className="btn secondary small"
                            onClick={() => {
                              onChange(e.path);
                              setOpen(false);
                            }}
                          >
                            {t("picker.choose")}
                          </button>
                        </div>
                        <div className="item-main">
                          <span className="item-name">{e.name}</span>
                          <span className="item-meta">{fmtBytes(e.size)}</span>
                        </div>
                      </div>
                    ),
                  )
                ) : (
                  <p className="hint" style={{ textAlign: "center" }}>
                    {t("picker.empty", { exts: exts.join(", ") })}
                  </p>
                )}
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      {sheetPreview && value && isExcel(value) ? <SheetPreview path={value} scope={scope} /> : null}
    </div>
  );
}

// --- Mode multi -------------------------------------------------------------

function MultiFilePicker({ exts, scope = "input", value, onChange, onFolderChange, allowRecursive = true }: MultiProps) {
  const { t } = useTranslation();
  const [path, setPath] = useState("");
  const [recursive, setRecursive] = useState(false);
  const [filter, setFilter] = useState("");
  const selection = useMemo(() => new Set(value), [value]);

  const listQuery = useQuery({
    queryKey: ["browse", scope, path],
    queryFn: () => browseApi.list(path, scope),
  });
  const filesQuery = useQuery({
    queryKey: ["browse-files", scope, path],
    queryFn: () => browseApi.files(path, scope),
    enabled: recursive,
  });

  const data = listQuery.data;
  const absPath = data?.path ?? "";
  const root = data?.root ?? "";
  const atRoot = !!data && data.path === data.root;

  // Remonte le dossier courant au parent (action "scanner ce dossier").
  useEffect(() => {
    if (absPath) onFolderChange?.(absPath);
  }, [absPath, onFolderChange]);

  const visibleItems = useMemo<BrowseEntryDto[]>(() => {
    if (recursive) {
      const f = filter.trim().toLowerCase();
      const all = (filesQuery.data?.entries ?? []).filter((e) => matchesExts(e.name, exts));
      return f ? all.filter((e) => (e.rel ?? e.name).toLowerCase().includes(f)) : all;
    }
    return (data?.entries ?? []).filter((e) => e.kind === "folder" || matchesExts(e.name, exts));
  }, [recursive, filter, filesQuery.data, data, exts]);

  const toggle = (p: string) => {
    const next = new Set(selection);
    if (next.has(p)) next.delete(p);
    else next.add(p);
    onChange(Array.from(next));
  };

  const selectAll = () => {
    const next = new Set(selection);
    visibleItems.forEach((e) => next.add(e.path));
    onChange(Array.from(next));
  };

  const openFolder = (p: string) => {
    setRecursive(false);
    setPath(p);
  };

  if (listQuery.isLoading) return <span className="spinner" />;
  if (listQuery.isError) {
    return (
      <p className="error">
        {listQuery.error instanceof Error ? listQuery.error.message : String(listQuery.error)}
      </p>
    );
  }
  if (!data) return null;

  return (
    <div className="form">
      <div className="row">
        <button type="button" className="btn ghost small" disabled={atRoot} onClick={() => openFolder(parentPath(absPath, root))}>
          <ChevronUp className="mr-1 h-4 w-4" />
          {t("picker.up")}
        </button>
        <code className="grow label" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {absPath}
        </code>
        {allowRecursive ? (
          <button
            type="button"
            className={recursive ? "btn secondary small" : "btn ghost small"}
            onClick={() => setRecursive((v) => !v)}
          >
            {recursive ? t("picker.levelView") : t("picker.recursiveView")}
          </button>
        ) : null}
      </div>

      {recursive ? (
        <input
          className="input"
          type="text"
          placeholder={t("picker.filterPlaceholder")}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      ) : null}

      <p className="hint">{recursive ? t("picker.recursiveHint") : t("picker.levelHint")}</p>

      <ul className="item-list" style={{ maxHeight: "18rem", overflow: "auto" }}>
        {recursive && filesQuery.isLoading ? (
          <li className="item-row">
            <span className="spinner" />
          </li>
        ) : visibleItems.length ? (
          visibleItems.map((e) => {
            const checked = selection.has(e.path);
            return (
              <li key={e.path} className={checked ? "item-row clickable" : "item-row"}>
                <Checkbox checked={checked} onCheckedChange={() => toggle(e.path)} aria-label={e.name} />
                {!recursive && e.kind === "folder" ? (
                  <button
                    type="button"
                    className="item-main"
                    style={{ textAlign: "left", background: "none", border: "none", cursor: "pointer" }}
                    onClick={() => openFolder(e.path)}
                  >
                    <span className="item-name">{e.name}/</span>
                  </button>
                ) : (
                  <span className="item-main">
                    <FileIcon className="h-4 w-4 shrink-0" />
                    <span className="item-name">{recursive ? e.rel ?? e.name : e.name}</span>
                  </span>
                )}
                {!recursive && e.kind === "folder" ? (
                  <span className="badge default">{t("picker.folder")}</span>
                ) : (
                  <span className="item-meta">{fmtBytes(e.size)}</span>
                )}
              </li>
            );
          })
        ) : (
          <li className="item-row">
            <span className="hint">{recursive ? t("picker.recursiveEmpty") : t("picker.empty", { exts: exts.join(", ") })}</span>
          </li>
        )}
      </ul>

      <div className="row">
        <button type="button" className="btn ghost small" onClick={selectAll}>
          {t("picker.selectAll")}
        </button>
        <button type="button" className="btn ghost small" onClick={() => onChange([])}>
          {t("picker.clear")}
        </button>
        <span className="hint">{t("picker.countSelected", { count: visibleItems.length, sel: selection.size })}</span>
      </div>
    </div>
  );
}

// --- Apercu Excel (mode single) ---------------------------------------------

/**
 * Apercu onglet + premieres lignes d'un classeur Excel choisi. Charge la liste
 * des onglets et la grille via `browseApi.preview`. Le changement d'onglet
 * recharge l'apercu. Repliable.
 */
function SheetPreview({ path, scope }: { path: string; scope: BrowseScope }) {
  const { t } = useTranslation();
  const [sheet, setSheet] = useState("");
  const [collapsed, setCollapsed] = useState(false);

  // Nouveau fichier -> on repart sur l'onglet detecte par defaut.
  useEffect(() => {
    setSheet("");
  }, [path]);

  const previewQuery = useQuery({
    queryKey: ["browse-preview", scope, path, sheet],
    queryFn: () => browseApi.preview({ scope, path, sheet: sheet || undefined }),
  });

  const data = previewQuery.data;
  // L'onglet effectif renvoye par le backend pilote le select tant que l'user
  // n'a pas choisi explicitement (sheet vide).
  const activeSheet = sheet || data?.sheet || "";

  return (
    <div className="card" style={{ padding: "0.5rem" }}>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="field">
          <label htmlFor="picker-sheet" className="field-label">
            {t("picker.sheet")}
          </label>
          <select
            id="picker-sheet"
            className="input"
            value={activeSheet}
            disabled={!data || data.sheets.length === 0}
            onChange={(e) => setSheet(e.target.value)}
          >
            {(data?.sheets ?? []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <button type="button" className="btn ghost small" onClick={() => setCollapsed((v) => !v)}>
          {collapsed ? t("picker.previewShow") : t("picker.previewHide")}
        </button>
      </div>

      {collapsed ? null : previewQuery.isLoading ? (
        <span className="spinner" style={{ marginTop: "0.5rem" }} />
      ) : previewQuery.isError ? (
        <p className="error" style={{ marginTop: "0.5rem" }}>
          {previewQuery.error instanceof Error ? previewQuery.error.message : String(previewQuery.error)}
        </p>
      ) : data ? (
        <div style={{ maxHeight: 288, overflow: "auto", marginTop: "0.5rem" }}>
          <table className="preview-table">
            <tbody>
              {data.rows.map((r, ri) => (
                <tr key={ri}>
                  <td className="rownum">{ri + 1}</td>
                  {r.map((c, ci) => (
                    <td key={ci}>{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
