import { useQuery } from "@tanstack/react-query";
import { FolderTree } from "lucide-react";
import { useTranslation } from "react-i18next";

import { MetricsPanel } from "../components/business/MetricsPanel";
import { TreeView } from "../components/business/TreeView";
import { importsApi, type TreeDto } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

export function Tree() {
  const { t } = useTranslation();
  const { importId } = useWorkspace();

  const treeQuery = useQuery<TreeDto>({
    queryKey: ["tree", importId],
    queryFn: () => importsApi.tree(importId as string),
    enabled: !!importId,
  });

  if (!importId) {
    return (
      <div className="empty-state">
        <FolderTree size={28} aria-hidden="true" />
        <h3 className="card-title">{t("tree.noImport")}</h3>
        <p className="hint">{t("tree.noImportDesc")}</p>
      </div>
    );
  }
  if (treeQuery.isLoading) return <span className="spinner" />;
  if (!treeQuery.data) {
    return (
      <div className="empty-state">
        <FolderTree size={28} aria-hidden="true" />
        <h3 className="card-title">{t("tree.notFound")}</h3>
        <p className="hint">{t("tree.notFoundDesc")}</p>
      </div>
    );
  }

  const data = treeQuery.data;
  return (
    <div className="flex max-w-4xl flex-col gap-4">
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
    </div>
  );
}
