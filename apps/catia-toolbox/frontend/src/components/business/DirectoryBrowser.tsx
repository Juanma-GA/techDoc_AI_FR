import { Badge, Button, Checkbox, Spinner } from "@internal/ui";
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
 * sur fichiers ET dossiers. Compose uniquement des primitives @internal/ui.
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

  if (listQuery.isLoading) return <Spinner />;
  if (listQuery.isError) {
    return (
      <p className="text-sm text-danger">
        {listQuery.error instanceof Error ? listQuery.error.message : String(listQuery.error)}
      </p>
    );
  }
  if (!data) return null;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          disabled={atRoot}
          onClick={() => setPath(parentPath(data.path, data.root))}
        >
          <ChevronUp className="mr-1 h-4 w-4" />
          {t("browse.up")}
        </Button>
        <code className="flex-1 truncate text-xs text-fg-dim">{data.path}</code>
      </div>

      <ul className="flex flex-col divide-y divide-border rounded-sm border border-md">
        {data.entries.length ? (
          data.entries.map((e) => (
            <li key={e.path} className="flex items-center gap-2 px-2 py-1.5">
              <Checkbox
                checked={selection.has(e.path)}
                onCheckedChange={() => toggle(e.path)}
                aria-label={e.name}
              />
              {e.kind === "folder" ? (
                <button
                  type="button"
                  className="flex flex-1 items-center gap-2 truncate text-left hover:text-brand-light"
                  onClick={() => setPath(e.path)}
                >
                  <Folder className="h-4 w-4 shrink-0 text-brand-light" />
                  <span className="truncate">{e.name}</span>
                </button>
              ) : (
                <span className="flex flex-1 items-center gap-2 truncate">
                  <File className="h-4 w-4 shrink-0 text-fg-muted" />
                  <span className="truncate">{e.name}</span>
                </span>
              )}
              {e.kind === "file" ? <Badge>{e.ext || "?"}</Badge> : null}
            </li>
          ))
        ) : (
          <li className="px-2 py-2 text-sm text-fg-dim">{t("browse.empty")}</li>
        )}
      </ul>
    </div>
  );
}
