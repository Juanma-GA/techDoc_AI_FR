import { useQuery } from "@tanstack/react-query";
import { FolderTree } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { FilePicker } from "../components/FilePicker";
import { TreeView } from "../components/business/TreeView";
import { browseApi, smgxmlApi, type SmgxmlTreeDto } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

const SMGXML_EXTS = [".smgxml", ".smg", ".xml"];

function isSmgxml(name: string): boolean {
  const n = name.toLowerCase();
  return SMGXML_EXTS.some((x) => n.endsWith(x));
}

/**
 * Onglet Arborescence : tout part du DOSSIER choisi. On liste ses fichiers
 * SMGXML ; un clic affiche la branche la plus profonde du dernier ClitServer
 * du fichier (lecture seule). Aucune autre source n'intervient.
 */
export function Tree() {
  const { t } = useTranslation();
  const folder = useWorkspace((s) => s.sources.smgxmlFolder);
  const setFolder = (p: string) => useWorkspace.getState().setSource("smgxmlFolder", p);
  const [selected, setSelected] = useState<string | null>(null);

  // Contenu du dossier choisi (confine sous la racine Source).
  const listQuery = useQuery({
    queryKey: ["browse", "input", folder],
    queryFn: () => browseApi.list(folder, "input"),
    enabled: !!folder.trim(),
  });
  const files = (listQuery.data?.entries ?? []).filter((e) => e.kind === "file" && isSmgxml(e.name));

  // Arbre XML du fichier selectionne.
  const treeQuery = useQuery<SmgxmlTreeDto>({
    queryKey: ["smgxml-tree", selected],
    queryFn: () => smgxmlApi.tree({ path: selected! }),
    enabled: !!selected,
  });

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <article className="card">
        <h2 className="card-title">{t("tree.folderTitle")}</h2>

        <div className="field">
          <label className="label">{t("tree.folderLabel")}</label>
          <FilePicker
            mode="folder"
            exts={[]}
            value={folder}
            onChange={(p) => {
              setFolder(p);
              setSelected(null);
            }}
          />
        </div>

        {!folder.trim() ? (
          <p className="hint" style={{ marginTop: 8 }}>{t("tree.folderHint")}</p>
        ) : listQuery.isLoading ? (
          <span className="spinner" style={{ marginTop: 8 }} />
        ) : listQuery.isError ? (
          <p className="error" style={{ marginTop: 8 }}>
            {listQuery.error instanceof Error ? listQuery.error.message : String(listQuery.error)}
          </p>
        ) : files.length ? (
          <>
            <p className="hint" style={{ marginTop: 8 }}>{t("tree.folderCount", { count: files.length })}</p>
            <ul className="item-list" style={{ maxHeight: "18rem", overflow: "auto" }}>
              {files.map((f) => (
                <li key={f.path}>
                  <button
                    type="button"
                    className={selected === f.path ? "item-row clickable" : "item-row"}
                    style={{ width: "100%", textAlign: "left" }}
                    onClick={() => setSelected(f.path)}
                  >
                    <span className="item-actions">
                      <span className={selected === f.path ? "btn primary small" : "btn secondary small"}>
                        {t("tree.view")}
                      </span>
                    </span>
                    <span className="item-main">
                      <span className="item-name">{f.name}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <div className="empty-state">
            <FolderTree size={28} aria-hidden="true" />
            <h3 className="card-title">{t("tree.folderEmpty")}</h3>
          </div>
        )}
      </article>

      {selected ? (
        <article className="card">
          {treeQuery.isLoading ? (
            <span className="spinner" />
          ) : treeQuery.isError ? (
            <p className="error">
              {treeQuery.error instanceof Error ? treeQuery.error.message : String(treeQuery.error)}
            </p>
          ) : treeQuery.data ? (
            <>
              <h2 className="card-title">
                {t("tree.structureTitle", { count: treeQuery.data.node_count })} - {treeQuery.data.root_label}
              </h2>
              <TreeView nodes={treeQuery.data.nodes} />
            </>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}
