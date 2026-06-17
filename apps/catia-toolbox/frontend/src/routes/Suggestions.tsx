import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  Input,
} from "@internal/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Wand2 } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { streamOptimize, suggestionsApi, type SuggestionDto } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

const CONF_VARIANT: Record<string, "success" | "warning" | "danger"> = {
  elevee: "success",
  moyenne: "warning",
  faible: "danger",
};
const STATUS_VARIANT: Record<string, "success" | "warning" | "danger"> = {
  accepted: "success",
  pending: "warning",
  rejected: "danger",
};

export function Suggestions() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { importId, runId, setRun } = useWorkspace();
  const [maxDepth, setMaxDepth] = useState(5);
  const [useLlm, setUseLlm] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);

  const suggestionsQuery = useQuery<SuggestionDto[]>({
    queryKey: ["suggestions", runId],
    queryFn: () => suggestionsApi.list(runId as string),
    enabled: !!runId,
  });

  if (!importId) {
    return <EmptyState icon={Wand2} title={t("suggestions.noImport")} description={t("tree.noImportDesc")} />;
  }

  const launch = () => {
    setError(null);
    setOutput("");
    setStreaming(true);
    cancelRef.current = streamOptimize(
      importId,
      { target_max_depth: maxDepth, use_llm: useLlm },
      {
        onSession: (d) => setRun(d.run_id),
        onToken: (d) => setOutput((o) => o + d),
        onDone: () => {
          setStreaming(false);
          void qc.invalidateQueries({ queryKey: ["suggestions"] });
        },
        onError: (m) => {
          setStreaming(false);
          setError(m);
        },
      },
    );
  };

  const setStatus = async (id: string, status: string) => {
    await suggestionsApi.setStatus(id, status);
    void qc.invalidateQueries({ queryKey: ["suggestions", runId] });
  };

  const bulk = async (status: string) => {
    const items = suggestionsQuery.data ?? [];
    if (!items.length) return;
    await suggestionsApi.bulkStatus(items.map((s) => s.id), status);
    void qc.invalidateQueries({ queryKey: ["suggestions", runId] });
  };

  const suggestions = suggestionsQuery.data ?? [];

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("suggestions.title")}</h1>
        <p className="text-fg-dim">{t("suggestions.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("suggestions.generateTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex flex-col gap-1">
              <span className="label">{t("suggestions.maxDepth")}</span>
              <Input
                type="number"
                min={1}
                max={20}
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value) || 5)}
                className="w-24"
              />
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm">
              <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
              {t("suggestions.useLlm")}
            </label>
            <Button onClick={launch} disabled={streaming}>
              {streaming ? t("suggestions.running") : t("suggestions.launch")}
            </Button>
          </div>
          {output ? (
            <pre className="mt-3 max-h-56 overflow-y-auto whitespace-pre-wrap rounded-sm border bg-bg-2 p-3 font-mono text-sm">
              {output}
            </pre>
          ) : null}
          {error ? <p className="mt-2 text-sm text-danger">{error}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center justify-between gap-2">
              <span>{t("suggestions.listTitle")}</span>
              <span className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => bulk("accepted")}>
                  {t("suggestions.acceptAll")}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => bulk("rejected")}>
                  {t("suggestions.rejectAll")}
                </Button>
              </span>
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {suggestions.length ? (
            <ul className="flex flex-col gap-2">
              {suggestions.map((s) => (
                <li
                  key={s.id}
                  className={[
                    "rounded-sm border bg-bg-2 px-3 py-2",
                    s.status === "accepted"
                      ? "border-success"
                      : s.status === "rejected"
                        ? "border-md opacity-60"
                        : "border-md",
                  ].join(" ")}
                >
                  <div className="break-all font-mono text-sm">
                    {s.old_path} <span className="text-brand-blue-light">&rarr;</span> {s.new_path}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <Badge variant="info">{t(`suggestions.action.${s.action}`)}</Badge>
                    <Badge>{s.source}</Badge>
                    <Badge variant={CONF_VARIANT[s.confidence]}>{s.confidence}</Badge>
                    <Badge variant={STATUS_VARIANT[s.status]}>{s.status}</Badge>
                  </div>
                  {s.rationale ? <p className="mt-1 text-sm text-fg-dim">{s.rationale}</p> : null}
                  <div className="mt-2 flex gap-2">
                    <Button variant="secondary" size="sm" onClick={() => void setStatus(s.id, "accepted")}>
                      {t("suggestions.accept")}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void setStatus(s.id, "rejected")}>
                      {t("suggestions.reject")}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={Wand2} title={t("suggestions.emptyTitle")} description={t("suggestions.emptyDesc")} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
