import { Button, Card, CardContent, CardHeader, CardTitle, EmptyState, Select } from "@internal/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Palette } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  colorizationApi,
  exportUrl,
  type ColorizationItemDto,
  type ColorizationRunDto,
  type DiffRunDto,
} from "../lib/api";
import { useWorkspace } from "../stores/workspace";

export function Colorization() {
  const { t } = useTranslation();
  const { importId } = useWorkspace();
  const [strategy, setStrategy] = useState("by_type");
  const [diffRunId, setDiffRunId] = useState("");
  const [run, setRun] = useState<ColorizationRunDto | null>(null);
  const [items, setItems] = useState<ColorizationItemDto[]>([]);
  const [error, setError] = useState<string | null>(null);

  const diffsQuery = useQuery<DiffRunDto[]>({
    queryKey: ["diffs", importId],
    queryFn: () => colorizationApi.diffs(importId as string),
    enabled: !!importId,
  });

  const mutation = useMutation({
    mutationFn: async () => {
      const body = strategy === "by_change" ? { strategy, diff_run_id: diffRunId } : { strategy };
      const r = await colorizationApi.run(importId as string, body);
      const it = await colorizationApi.items(r.id);
      return { r, it };
    },
    onSuccess: ({ r, it }) => {
      setError(null);
      setRun(r);
      setItems(it);
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  if (!importId) {
    return <EmptyState icon={Palette} title={t("colorization.noImport")} description={t("tree.noImportDesc")} />;
  }

  const textOn = (r: number, g: number, b: number) =>
    (r * 299 + g * 587 + b * 114) / 1000 > 140 ? "black" : "white";

  const diffs = diffsQuery.data ?? [];
  const stratOptions = [
    { value: "by_type", label: t("colorization.byType") },
    { value: "by_depth", label: t("colorization.byDepth") },
    { value: "by_change", label: t("colorization.byChange") },
  ];

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("colorization.title")}</h1>
        <p className="text-fg-dim">{t("colorization.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("colorization.runTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 rounded-sm border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
            <strong>{t("export.dryRunTitle")}</strong> {t("colorization.dryRun")}
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-1 flex-col gap-1">
              <span className="label">{t("colorization.strategy")}</span>
              <Select options={stratOptions} value={strategy} onChange={(e) => setStrategy(e.target.value)} />
            </label>
            {strategy === "by_change" ? (
              <label className="flex flex-1 flex-col gap-1">
                <span className="label">{t("colorization.comparison")}</span>
                <Select
                  options={
                    diffs.length
                      ? diffs.map((d) => ({ value: d.id, label: `${t("nav.diff")} ${d.id.slice(0, 8)}` }))
                      : [{ value: "", label: t("colorization.noDiff") }]
                  }
                  value={diffRunId || diffs[0]?.id || ""}
                  onChange={(e) => setDiffRunId(e.target.value)}
                />
              </label>
            ) : null}
            <Button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || (strategy === "by_change" && !diffs.length)}
            >
              {t("colorization.run")}
            </Button>
          </div>
          {error ? <p className="mt-2 text-sm text-danger">{error}</p> : null}
        </CardContent>
      </Card>

      {run ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("colorization.resultTitle", { count: items.length })}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-3 flex flex-wrap gap-2">
              <a href={exportUrl.colorizationCsv(run.id)}>
                <Button variant="secondary" size="sm">{t("common.exportCsv")}</Button>
              </a>
              <a href={exportUrl.colorizationComposer(run.id)}>
                <Button variant="secondary" size="sm">{t("colorization.composerScript")}</Button>
              </a>
              <a href={exportUrl.colorizationMacro(run.id)}>
                <Button variant="secondary" size="sm">{t("colorization.macro")}</Button>
              </a>
              <a href={exportUrl.colorizationSvg(run.id)} target="_blank" rel="noreferrer">
                <Button variant="secondary" size="sm">{t("colorization.svg")}</Button>
              </a>
            </div>

            {/* Simulation : chaque piece dans sa couleur attribuee. */}
            <p className="mb-2 text-sm text-fg-dim">{t("colorization.simulation")}</p>
            <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {items.map((it) => (
                <div
                  key={it.id}
                  className="overflow-hidden rounded-sm px-2 py-2 text-xs"
                  style={{
                    backgroundColor: `rgb(${it.color_r}, ${it.color_g}, ${it.color_b})`,
                    color: textOn(it.color_r, it.color_g, it.color_b),
                  }}
                  title={`${it.rel_path} — ${it.reason}`}
                >
                  <div className="truncate font-mono font-medium">{it.rel_path.split("/").pop()}</div>
                  <div className="truncate opacity-80">{it.reason}</div>
                </div>
              ))}
            </div>

            <ul className="flex flex-col gap-1">
              {items.map((it) => (
                <li key={it.id} className="flex items-center gap-2 rounded-sm bg-bg-2 px-3 py-1.5 text-sm">
                  <span
                    className="inline-block h-4 w-4 shrink-0 rounded-sm border border-md"
                    style={{ backgroundColor: `rgb(${it.color_r}, ${it.color_g}, ${it.color_b})` }}
                    aria-hidden="true"
                  />
                  <span className="grow break-all font-mono">{it.rel_path}</span>
                  <span className="text-fg-dim">{it.reason}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
