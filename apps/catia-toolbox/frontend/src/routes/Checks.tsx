import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState, Input } from "@internal/ui";
import { useMutation } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { checksApi, exportUrl, type CheckResultDto, type CheckRunDto } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

const SEV_VARIANT: Record<string, "danger" | "warning" | "info"> = {
  danger: "danger",
  warning: "warning",
  info: "info",
};

export function Checks() {
  const { t } = useTranslation();
  const { importId } = useWorkspace();
  const [maxDepth, setMaxDepth] = useState(6);
  const [run, setRun] = useState<CheckRunDto | null>(null);
  const [results, setResults] = useState<CheckResultDto[]>([]);

  const mutation = useMutation({
    mutationFn: async () => {
      const r = await checksApi.run(importId as string, { max_depth: maxDepth });
      const res = await checksApi.results(r.id);
      return { r, res };
    },
    onSuccess: ({ r, res }) => {
      setRun(r);
      setResults(res);
    },
  });

  if (!importId) {
    return <EmptyState icon={ShieldCheck} title={t("checks.noImport")} description={t("tree.noImportDesc")} />;
  }

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("checks.title")}</h1>
        <p className="text-fg-dim">{t("checks.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("checks.runTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="label">{t("checks.maxDepth")}</span>
              <Input
                type="number"
                min={1}
                max={20}
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value) || 6)}
                className="w-24"
              />
            </label>
            <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              {t("checks.run")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {run ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("checks.resultTitle", { count: results.length })}</CardTitle>
          </CardHeader>
          <CardContent>
            <a href={exportUrl.checksCsv(run.id)} className="mb-3 inline-block">
              <Button variant="secondary" size="sm">{t("common.exportCsv")}</Button>
            </a>
            {results.length ? (
              <ul className="flex flex-col gap-1">
                {results.map((r) => (
                  <li key={r.id} className="flex items-start gap-2 rounded-sm bg-bg-2 px-3 py-1.5 text-sm">
                    <Badge variant={SEV_VARIANT[r.severity] ?? "warning"}>{r.rule}</Badge>
                    <span className="break-all font-mono">{r.rel_path || "(global)"}</span>
                    <span className="text-fg-dim">— {r.message}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-fg-dim">{t("checks.none")}</p>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
