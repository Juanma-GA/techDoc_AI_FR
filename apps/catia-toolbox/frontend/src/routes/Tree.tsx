import { useMutation, useQuery } from "@tanstack/react-query";
import { FolderTree } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { FilePicker } from "../components/FilePicker";
import { MetricsPanel } from "../components/business/MetricsPanel";
import { TreeView } from "../components/business/TreeView";
import { ApiClientError, importsApi, smgxmlApi, type SmgxmlTreeDto, type TreeDto } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

const SMGXML_EXTS = [".smgxml", ".smg", ".xml"];

/** Arbre XML brut d'un fichier SMGXML (lecture seule), independant de l'import. */
function SmgxmlTreeCard() {
  const { t } = useTranslation();
  const path = useWorkspace((s) => s.sources.smgxml);
  const setPath = (p: string) => useWorkspace.getState().setSource("smgxml", p);
  const [result, setResult] = useState<SmgxmlTreeDto | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadMutation = useMutation({
    mutationFn: () => smgxmlApi.tree({ path: path.trim() }),
    onSuccess: (data) => {
      setError(null);
      setResult(data);
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  return (
    <article className="card">
      <h2 className="card-title">{t("tree.smgxmlTitle")}</h2>
      <p className="banner info">{t("tree.smgxmlBanner")}</p>
      <div className="field">
        <label className="label">{t("smgxml.fileLabel")}</label>
        <FilePicker exts={SMGXML_EXTS} value={path} onChange={setPath} />
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <button
          type="button"
          className="btn primary"
          onClick={() => loadMutation.mutate()}
          disabled={loadMutation.isPending || !path.trim()}
        >
          {loadMutation.isPending ? <span className="spinner" /> : null}
          <span>{t("tree.smgxmlLoad")}</span>
        </button>
        {error ? <span className="error">{error}</span> : null}
      </div>

      {result ? (
        <div style={{ marginTop: 12 }}>
          <p className="hint">
            {t("tree.structureTitle", { count: result.node_count })} - {result.root_label}
          </p>
          <TreeView nodes={result.nodes} />
        </div>
      ) : null}
    </article>
  );
}

export function Tree() {
  const { t } = useTranslation();
  const { importId } = useWorkspace();

  const treeQuery = useQuery<TreeDto>({
    queryKey: ["tree", importId],
    queryFn: () => importsApi.tree(importId as string),
    enabled: !!importId,
  });

  const data = treeQuery.data;
  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <SmgxmlTreeCard />

      {!importId ? (
        <div className="empty-state">
          <FolderTree size={28} aria-hidden="true" />
          <h3 className="card-title">{t("tree.noImport")}</h3>
          <p className="hint">{t("tree.noImportDesc")}</p>
        </div>
      ) : treeQuery.isLoading ? (
        <span className="spinner" />
      ) : !data ? (
        <div className="empty-state">
          <FolderTree size={28} aria-hidden="true" />
          <h3 className="card-title">{t("tree.notFound")}</h3>
          <p className="hint">{t("tree.notFoundDesc")}</p>
        </div>
      ) : (
        <>
          <article className="card">
            <h2 className="card-title">
              {t("tree.metricsTitle")} - {data.root_label}
            </h2>
            <MetricsPanel metrics={data.metrics} />
          </article>

          <article className="card">
            <h2 className="card-title">{t("tree.structureTitle", { count: data.node_count })}</h2>
            <TreeView nodes={data.nodes} />
          </article>
        </>
      )}
    </div>
  );
}
