import { EmptyState, Spinner } from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { errorText } from "../../lib/api";
import { convertApi } from "../../lib/flowApi";
import type { FlowGraph } from "../../types/flow";

export function PreviewPanel({ graph }: { graph: FlowGraph | null }) {
  const { t } = useTranslation();
  const [url, setUrl] = useState<string | null>(null);
  const preview = useQuery({
    queryKey: ["preview", graph],
    queryFn: () => convertApi.preview(graph as FlowGraph),
    enabled: graph !== null,
    retry: false,
  });

  useEffect(() => {
    if (!preview.data) {
      setUrl(null);
      return;
    }
    const next = URL.createObjectURL(preview.data);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [preview.data]);

  if (!graph) {
    return <EmptyState title={t("editor.preview.emptyTitle")} description={t("editor.preview.emptyHelp")} />;
  }
  if (preview.isError) {
    return (
      <div className="text-danger" role="alert">
        {errorText(preview.error)}
      </div>
    );
  }
  if (preview.isPending || !url) {
    return (
      <div className="flex justify-center p-8">
        <Spinner />
      </div>
    );
  }
  return (
    <div className="max-h-[70vh] overflow-auto rounded border bg-card p-2">
      <img src={url} alt={t("editor.preview.alt", { title: graph.title })} className="mx-auto max-w-none" />
    </div>
  );
}
