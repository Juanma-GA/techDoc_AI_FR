import { Checkbox } from "@internal/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronUp, File as FileIcon } from "lucide-react";
import type { InputHTMLAttributes } from "react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { browseApi, type BrowseEntryDto, type BrowseScope } from "../lib/api";

const DIRECTORY_INPUT_ATTRS = {
  webkitdirectory: "",
  directory: "",
} as unknown as InputHTMLAttributes<HTMLInputElement>;

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

type FolderProps = CommonProps & {
  mode: "folder";
  value: string;
  onChange: (path: string) => void;
  /** Libelle du bouton toggle (defaut : "Parcourir"). */
  label?: string;
};

export type FilePickerProps = SingleProps | MultiProps | FolderProps;

function rootIsConfigured(
  roots: { input: string; output: string } | undefined,
  scope: BrowseScope,
): boolean {
  return Boolean(scope === "input" ? roots?.input : roots?.output);
}

/**
 * Selecteur de fichier unique de l'app, decline en trois modes :
 *  - `single` : un champ + bouton qui ouvre un panneau pliable ; choisir un
 *    fichier renvoie son chemin. Apercu onglet/lignes pour les classeurs Excel.
 *  - `multi`  : panneau inline avec cases a cocher, vue niveau ou recursive,
 *    Tout cocher / Vider ; renvoie la liste des chemins coches.
 *  - `folder` : navigation dans les dossiers + bouton "Choisir ce dossier" qui
 *    renvoie le chemin du dossier courant (traitement de masse).
 * Tous partagent la meme navigation (fil d'Ariane, Remonter) -> coherence.
 */
export function FilePicker(props: FilePickerProps) {
  const scope = props.scope ?? "input";
  const rootsQuery = useQuery({
    queryKey: ["browse", "roots"],
    queryFn: browseApi.roots,
    staleTime: 30_000,
  });
  const localFallback = rootsQuery.isSuccess && !rootIsConfigured(rootsQuery.data, scope);

  if (props.mode === "multi") return <MultiFilePicker {...props} localFallback={localFallback} />;
  if (props.mode === "folder") return <FolderPicker {...props} localFallback={localFallback} />;
  return <SingleFilePicker {...props} localFallback={localFallback} />;
}

// --- Mode folder ------------------------------------------------------------

function FolderPicker({ scope = "input", value, onChange, label, localFallback }: FolderProps & { localFallback: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState("");

  const listQuery = useQuery({
    queryKey: ["browse", scope, path],
    queryFn: () => browseApi.list(path, scope),
    enabled: open && !localFallback,
  });

  const data = listQuery.data;
  const atRoot = !!data && data.path === data.root;
  const folders = (data?.entries ?? []).filter((e) => e.kind === "folder");

  if (localFallback) {
    return <LocalFolderPicker value={value} onChange={onChange} label={label} />;
  }

  return (
    <div className="form">
      <div className="row">
        <input
          type="text"
          className="input grow"
          placeholder={t("picker.folderPlaceholder")}
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
                <button
                  type="button"
                  className="btn primary small"
                  onClick={() => {
                    onChange(data.path);
                    setOpen(false);
                  }}
                >
                  {t("picker.chooseFolder")}
                </button>
              </div>
              <div className="item-list" style={{ maxHeight: "15rem", overflow: "auto" }}>
                {folders.length ? (
                  folders.map((e) => (
                    <button
                      key={e.path}
                      type="button"
                      className="item-row"
                      style={{ width: "100%", textAlign: "left" }}
                      onClick={() => setPath(e.path)}
                    >
                      <span className="item-actions">
                        <span className="btn ghost small">{t("picker.open")}</span>
                      </span>
                      <span className="item-main">
                        <span className="item-name">{e.name}/</span>
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="hint" style={{ textAlign: "center" }}>
                    {t("picker.noSubfolder")}
                  </p>
                )}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// --- Mode single ------------------------------------------------------------

function SingleFilePicker({
  exts,
  scope = "input",
  value,
  onChange,
  label,
  sheetPreview = true,
  localFallback,
}: SingleProps & { localFallback: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState("");

  const listQuery = useQuery({
    queryKey: ["browse", scope, path],
    queryFn: () => browseApi.list(path, scope),
    enabled: open && !localFallback,
  });

  const data = listQuery.data;
  const atRoot = !!data && data.path === data.root;
  // On affiche TOUS les dossiers et fichiers du dossier courant ; seuls les
  // fichiers dont l'extension correspond a `exts` sont selectionnables (les
  // autres sont grises), pour toujours voir le contenu reel du dossier.
  const entries = data?.entries ?? [];

  if (localFallback) {
    return <LocalSingleFilePicker exts={exts} value={value} onChange={onChange} label={label} />;
  }

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
                  entries.map((e) => {
                    if (e.kind === "folder") {
                      return (
                        <button
                          key={e.path}
                          type="button"
                          className="item-row"
                          style={{ width: "100%", textAlign: "left" }}
                          onClick={() => setPath(e.path)}
                        >
                          <span className="item-actions">
                            <span className="btn ghost small">{t("picker.open")}</span>
                          </span>
                          <span className="item-main">
                            <span className="item-name">{e.name}/</span>
                          </span>
                        </button>
                      );
                    }
                    // Fichier : selectionnable seulement si l'extension correspond.
                    const selectable = matchesExts(e.name, exts);
                    return (
                      <button
                        key={e.path}
                        type="button"
                        className="item-row"
                        disabled={!selectable}
                        style={{ width: "100%", textAlign: "left", ...(selectable ? {} : { opacity: 0.5 }) }}
                        onClick={() => {
                          onChange(e.path);
                          setOpen(false);
                        }}
                      >
                        <span className="item-actions">
                          <span className="btn secondary small">{t("picker.choose")}</span>
                        </span>
                        <span className="item-main">
                          <span className="item-name">{e.name}</span>
                          <span className="item-meta">{fmtBytes(e.size)}</span>
                        </span>
                      </button>
                    );
                  })
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

function MultiFilePicker({
  exts,
  scope = "input",
  value,
  onChange,
  onFolderChange,
  allowRecursive = true,
  localFallback,
}: MultiProps & { localFallback: boolean }) {
  const { t } = useTranslation();
  const [path, setPath] = useState("");
  const [recursive, setRecursive] = useState(false);
  const [filter, setFilter] = useState("");
  const selection = useMemo(() => new Set(value), [value]);

  const listQuery = useQuery({
    queryKey: ["browse", scope, path],
    queryFn: () => browseApi.list(path, scope),
    enabled: !localFallback,
  });
  const filesQuery = useQuery({
    queryKey: ["browse-files", scope, path],
    queryFn: () => browseApi.files(path, scope),
    enabled: recursive && !localFallback,
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

  if (localFallback) {
    return <LocalMultiFilePicker exts={exts} value={value} onChange={onChange} onFolderChange={onFolderChange} />;
  }
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
              <li
                key={e.path}
                className={checked ? "item-row clickable" : "item-row"}
              >
                <Checkbox checked={checked} onCheckedChange={() => toggle(e.path)} aria-label={e.name} />
                <button
                  type="button"
                  className="item-main grow"
                  style={{ textAlign: "left", background: "none", border: "none", cursor: "pointer" }}
                  onClick={() => (e.kind === "folder" && !recursive ? openFolder(e.path) : toggle(e.path))}
                >
                  {!recursive && e.kind === "folder" ? (
                    <span className="item-name">{e.name}/</span>
                  ) : (
                    <>
                      <FileIcon className="h-4 w-4 shrink-0" />
                      <span className="item-name">{recursive ? e.rel ?? e.name : e.name}</span>
                      <span className="item-meta">{fmtBytes(e.size)}</span>
                    </>
                  )}
                </button>
                {!recursive && e.kind === "folder" ? (
                  <span className="badge default">{t("picker.folder")}</span>
                ) : null}
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

function LocalSingleFilePicker({
  exts,
  value,
  onChange,
  label,
}: Pick<SingleProps, "exts" | "value" | "onChange" | "label">) {
  const { t } = useTranslation();
  const uploadMutation = useMutation({
    mutationFn: (file: File) => browseApi.uploadLocal([file]),
    onSuccess: (data) => {
      const uploaded = data.files[0];
      if (uploaded) onChange(uploaded.path);
    },
  });

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
        <label className="btn secondary">
          {uploadMutation.isPending ? <span className="spinner" /> : null}
          <span>{label ?? t("picker.browseLocal")}</span>
          <input
            type="file"
            hidden
            accept={exts.length ? exts.join(",") : undefined}
            disabled={uploadMutation.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadMutation.mutate(file);
              e.currentTarget.value = "";
            }}
          />
        </label>
      </div>
      <p className="hint">{t("picker.localHint")}</p>
      {uploadMutation.isError ? (
        <p className="error">
          {uploadMutation.error instanceof Error ? uploadMutation.error.message : String(uploadMutation.error)}
        </p>
      ) : null}
    </div>
  );
}

function LocalFolderPicker({ value, onChange, label }: Pick<FolderProps, "value" | "onChange" | "label">) {
  const { t } = useTranslation();
  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => browseApi.uploadLocal(files),
    onSuccess: (data) => onChange(data.root),
  });

  return (
    <div className="form">
      <div className="row">
        <input
          type="text"
          className="input grow"
          placeholder={t("picker.folderPlaceholder")}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <label className="btn secondary">
          {uploadMutation.isPending ? <span className="spinner" /> : null}
          <span>{label ?? t("picker.chooseLocalFolder")}</span>
          <input
            type="file"
            hidden
            multiple
            disabled={uploadMutation.isPending}
            {...DIRECTORY_INPUT_ATTRS}
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              if (files.length) uploadMutation.mutate(files);
              e.currentTarget.value = "";
            }}
          />
        </label>
      </div>
      <p className="hint">{t("picker.localFolderHint")}</p>
      {uploadMutation.isError ? (
        <p className="error">
          {uploadMutation.error instanceof Error ? uploadMutation.error.message : String(uploadMutation.error)}
        </p>
      ) : null}
    </div>
  );
}

function LocalMultiFilePicker({
  exts,
  value,
  onChange,
  onFolderChange,
}: Pick<MultiProps, "exts" | "value" | "onChange" | "onFolderChange">) {
  const { t } = useTranslation();
  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => browseApi.uploadLocal(files),
    onSuccess: (data) => {
      onFolderChange?.(data.root);
      onChange(data.files.map((file) => file.path));
    },
  });

  return (
    <div className="form">
      <label className="btn secondary" style={{ width: "fit-content" }}>
        {uploadMutation.isPending ? <span className="spinner" /> : null}
        <span>{t("picker.chooseLocalFolder")}</span>
        <input
          type="file"
          hidden
          multiple
          disabled={uploadMutation.isPending}
          accept={exts.length ? exts.join(",") : undefined}
          {...DIRECTORY_INPUT_ATTRS}
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) uploadMutation.mutate(files);
            e.currentTarget.value = "";
          }}
        />
      </label>
      <p className="hint">{t("picker.localFolderHint")}</p>
      {value.length ? <p className="success">{t("picker.localUploaded", { count: value.length })}</p> : null}
      {uploadMutation.isError ? (
        <p className="error">
          {uploadMutation.error instanceof Error ? uploadMutation.error.message : String(uploadMutation.error)}
        </p>
      ) : null}
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
