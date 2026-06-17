import { Card, CardContent, CardHeader, CardTitle, EmptyState, Spinner } from "@internal/ui";
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
    return <EmptyState icon={FolderTree} title={t("tree.noImport")} description={t("tree.noImportDesc")} />;
  }
  if (treeQuery.isLoading) return <Spinner />;
  if (!treeQuery.data) {
    return <EmptyState icon={FolderTree} title={t("tree.notFound")} description={t("tree.notFoundDesc")} />;
  }

  const data = treeQuery.data;
  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("tree.title")}</h1>
        <p className="text-fg-dim">{data.root_label}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("tree.metricsTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <MetricsPanel metrics={data.metrics} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("tree.structureTitle", { count: data.node_count })}</CardTitle>
        </CardHeader>
        <CardContent>
          <TreeView nodes={data.nodes} />
        </CardContent>
      </Card>
    </div>
  );
}
