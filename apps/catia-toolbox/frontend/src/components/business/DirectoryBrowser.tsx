import { useQuery } from "@tanstack/react-query";
import { ChevronUp, File, Folder } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { browseApi, type BrowseScope } from "../../lib/api";

function parentPath(absPath: string, root: string): string {
  const norm = absPath.replace(/\\/g, "/").replace(/\/+$/, "");
  const rootNorm = root.replace(/\\/g, "/").replace(/\/+$/, "");
  if (!norm || norm === rootNorm) return "";
  const idx = norm.lastIndexOf("/");
  const parent = idx > 0 ? norm.slice(0, idx) : "";
  return parent.length < rootNorm.length ? rootNorm : parent;
}

export type DirectoryBrowserProps = {
  scope?: BrowseScope;
  /** Chemins absolus coches (controle par le parent). */
  selection: Set<string>;
  onSelectionChange: (next: Set<string>) => void;
};

/**
 * Navigateur d'arborescence OneDrive (lazy, un niveau par appel). Cases a cocher
 * sur fichiers ET dossiers. Skin "preview-skin" (classes .item-list / .checkbox).
 */
export function DirectoryBrowser({ scope = "input", selection, onSelectionChange }: DirectoryBrowserProps) {
  const { t } = useTranslation();
  const [path, setPath] = useState("");

  const listQuery = useQuery({
    queryKey: ["browse", scope, path],
    queryFn: () => browseApi.list(path, scope),
  });

  const data = listQuery.data;
  const atRoot = useMemo(() => !!data && data.path === data.root, [data]);

  const toggle = (p: string) => {
    const next = new Set(selection);
    if (next.has(p)) next.delete(p);
    else next.add(p);
    onSelectionChange(next);
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
        <button
          type="button"
          className="btn ghost small"
          disabled={atRoot}
          onClick={() => setPath(parentPath(data.path, data.root))}
        >
          <ChevronUp className="mr-1 h-4 w-4" />
          {t("browse.up")}
        </button>
        <code className="hint grow" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {data.path}
        </code>
      </div>

      <div className="item-list">
        {data.entries.length ? (
          data.entries.map((e) => (
            <div key={e.path} className="item-row">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={selection.has(e.path)}
                  onChange={() => toggle(e.path)}
                  aria-label={e.name}
                />
              </label>
              {e.kind === "folder" ? (
                <button
                  type="button"
                  className="item-main clickable"
                  style={{ textAlign: "left", background: "none", border: "none", cursor: "pointer" }}
                  onClick={() => setPath(e.path)}
                >
                  <Folder className="h-4 w-4 shrink-0 text-brand-light" />
                  <span className="item-name">{e.name}</span>
                </button>
              ) : (
                <span className="item-main">
                  <File className="h-4 w-4 shrink-0 text-fg-muted" />
                  <span className="item-name">{e.name}</span>
                </span>
              )}
              {e.kind === "file" ? <span className="badge default">{e.ext || "?"}</span> : null}
            </div>
          ))
        ) : (
          <div className="item-row">
            <span className="hint">{t("browse.empty")}</span>
          </div>
        )}
      </div>
    </div>
  );
}
