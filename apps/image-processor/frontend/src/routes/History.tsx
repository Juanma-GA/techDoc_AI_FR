import { Button, Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { FolderOpen, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { WorkspaceStatus } from "../components/WorkspaceStatus";
import { useWorkflow } from "../hooks/WorkflowProvider";
import { requestError, workspaceApi, type HistorySummary } from "../lib/workspace-api";

export function History() {
  const { t, i18n } = useTranslation();
  const workflow = useWorkflow();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const query = useInfiniteQuery({
    queryKey: ["image-history", workflow.storage.historySaved],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => workspaceApi.list(pageParam),
    getNextPageParam: (page) => page.next_cursor,
    enabled: workflow.storage.ready && !workflow.storage.saving,
  });
  const remove = useMutation({
    mutationFn: async (id: string) => {
      await workflow.storage.flush();
      if (workflow.document?.id === id && !await workflow.newImage()) {
        throw new Error(t("history.deleteError"));
      }
      await workspaceApi.remove(id);
    },
    onSuccess: async () => {
      setFeedback("");
      await queryClient.invalidateQueries({ queryKey: ["image-history"] });
    },
    onError: (error) => setFeedback(requestError(error, t("history.deleteError"))),
  });
  const busy = workflow.loading || workflow.retouching || workflow.restoring ||
    workflow.excelLoading || workflow.excelPairsLoading || remove.isPending;
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];

  async function open(id: string) {
    if (await workflow.openHistory(id)) navigate("/");
  }

  return (
    <div className="space-y-4">
      <header className="page-header">
        <div><h1>{t("history.title")}</h1><p>{t("history.subtitle")}</p></div>
      </header>
      <WorkspaceStatus />
      {workflow.error || feedback ? <p role="alert" className="text-danger">{feedback || workflow.error}</p> : null}
      {query.isPending ? <p role="status">{t("common.loading")}</p> : null}
      {query.isError ? (
        <div role="alert" className="space-y-2 text-danger">
          <p>{requestError(query.error, t("history.loadError"))}</p>
          <Button variant="secondary" onClick={() => void query.refetch()}>{t("history.retry")}</Button>
        </div>
      ) : null}
      {query.isSuccess && items.length === 0 ? (
        <p className="rounded-md border border-dashed border-md p-6 text-fg-dim">{t("history.empty")}</p>
      ) : null}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {items.map((item) => (
          <HistoryEntry
            key={item.id} item={item} disabled={busy} language={i18n.resolvedLanguage} t={t}
            onOpen={() => void open(item.id)} onRemove={() => remove.mutate(item.id)}
          />
        ))}
      </div>
      {query.hasNextPage ? (
        <Button
          variant="secondary" disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >{t("history.more")}</Button>
      ) : null}
    </div>
  );
}

function HistoryEntry({ item, disabled, language, t, onOpen, onRemove }: {
  item: HistorySummary; disabled: boolean; language?: string; t: TFunction;
  onOpen: () => void; onRemove: () => void;
}) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => clearTimeout(timer.current), []);
  function confirmRemove() {
    if (!armed) {
      setArmed(true);
      timer.current = setTimeout(() => setArmed(false), 3000);
      return;
    }
    clearTimeout(timer.current);
    setArmed(false);
    onRemove();
  }
  return (
    <Card>
      <CardHeader><CardTitle className="break-all">{item.filename}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {item.piece_name ? <p className="text-sm">{item.piece_name}</p> : null}
        <p className="text-xs text-fg-dim">
          {new Date(item.updated_at).toLocaleString(language)}{" · "}
          {t("history.operationCount", { count: item.operation_count })}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={disabled} onClick={onOpen}>
            <FolderOpen size={16} aria-hidden="true" />{t("history.open")}
          </Button>
          <Button variant="danger" disabled={disabled} onClick={confirmRemove}>
            <Trash2 size={16} aria-hidden="true" />
            {t(armed ? "history.confirmDelete" : "history.delete")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
