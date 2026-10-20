import { Button, Card, CardContent, CardHeader, CardTitle, EmptyState, KpiCard, Select } from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { useArmedConfirm } from "../hooks/useArmedConfirm";
import { errorText } from "../lib/api";
import { adminApi, convertApi, flowsApi, saveResponse } from "../lib/flowApi";
import { useEditorStore } from "../stores/editorStore";

export function Data() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const loadFlow = useEditorStore((s) => s.loadFlow);
  const { armed, trigger } = useArmedConfirm();
  const [fmt, setFmt] = useState("xlsx");
  const [error, setError] = useState<string | null>(null);

  const stats = useQuery({ queryKey: ["admin-stats"], queryFn: adminApi.stats });
  const flows = useQuery({ queryKey: ["flows"], queryFn: flowsApi.list });
  const formats = useQuery({ queryKey: ["formats"], queryFn: convertApi.formats, staleTime: Infinity });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["flows"] });
    void qc.invalidateQueries({ queryKey: ["admin-stats"] });
  };
  const onError = (e: unknown) => setError(errorText(e));
  const remove = useMutation({ mutationFn: flowsApi.remove, onSuccess: refresh, onError });
  const reset = useMutation({ mutationFn: () => adminApi.reset("all"), onSuccess: refresh, onError });

  const open = async (id: string) => {
    try {
      loadFlow(await flowsApi.read(id));
      navigate("/editor");
    } catch (e) {
      onError(e);
    }
  };
  const exportFlow = async (id: string) => {
    try {
      await saveResponse(await flowsApi.exportFile(id, fmt), `logigramme.${fmt}`);
    } catch (e) {
      onError(e);
    }
  };

  const confirmLabel = (key: string, label: string) => (armed === key ? t("common.confirm") : label);
  const date = (iso: string) => new Date(iso).toLocaleString(i18n.language);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-display text-xl">{t("data.title")}</h1>
      <div className="grid gap-3 sm:grid-cols-3">
        <KpiCard label={t("data.kpi.flows")} value={stats.data?.flows ?? "-"} />
        <KpiCard label={t("data.kpi.nodes")} value={stats.data?.nodes ?? "-"} />
        <KpiCard label={t("data.kpi.edges")} value={stats.data?.edges ?? "-"} />
      </div>
      {error && (
        <div className="text-sm text-danger" role="alert">
          {error}
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-2">
          <CardTitle>{t("data.flowsTitle")}</CardTitle>
          <div className="flex items-center gap-2">
            <span className="label">{t("data.exportFormat")}</span>
            <Select
              size="sm"
              value={fmt}
              onChange={(e) => setFmt(e.target.value)}
              options={(formats.data ?? []).map((f) => ({ value: f.format, label: f.format.toUpperCase() }))}
            />
          </div>
        </CardHeader>
        <CardContent>
          {flows.data && flows.data.length === 0 ? (
            <EmptyState title={t("data.emptyTitle")} description={t("data.emptyHelp")} />
          ) : (
            <table className="w-full text-left text-sm" data-testid="flows-table">
              <thead className="text-fg-dim">
                <tr>
                  <th className="py-1">{t("data.col.name")}</th>
                  <th className="py-1">{t("data.col.source")}</th>
                  <th className="py-1">{t("data.col.size")}</th>
                  <th className="py-1">{t("data.col.updated")}</th>
                  <th className="py-1" />
                </tr>
              </thead>
              <tbody>
                {(flows.data ?? []).map((f) => (
                  <tr key={f.id} className="border-t">
                    <td className="py-2">{f.name}</td>
                    <td className="py-2">{t(`data.source.${f.source_type}`)}</td>
                    <td className="py-2">{t("editor.counts", { nodes: f.node_count, edges: f.edge_count })}</td>
                    <td className="py-2">{date(f.updated_at)}</td>
                    <td className="flex justify-end gap-1 py-2">
                      <Button size="sm" variant="secondary" onClick={() => void open(f.id)}>
                        {t("data.open")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => void exportFlow(f.id)}>
                        {t("data.export")}
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => trigger(f.id, () => remove.mutate(f.id))}>
                        {confirmLabel(f.id, t("data.delete"))}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("data.resetTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-2">
          <p className="text-sm text-fg-dim">{t("data.resetHelp")}</p>
          <Button variant="danger" disabled={reset.isPending} onClick={() => trigger("reset-all", () => reset.mutate())}>
            {confirmLabel("reset-all", t("data.resetAll"))}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
