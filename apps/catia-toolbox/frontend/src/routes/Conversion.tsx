import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState } from "@internal/ui";
import { useMutation } from "@tanstack/react-query";
import { Boxes } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { conversionApi, exportUrl, type ConversionItemDto, type ConversionRunDto } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

export function Conversion() {
  const { t } = useTranslation();
  const { importId } = useWorkspace();
  const [run, setRun] = useState<ConversionRunDto | null>(null);
  const [items, setItems] = useState<ConversionItemDto[]>([]);

  const mutation = useMutation({
    mutationFn: async () => {
      const r = await conversionApi.run(importId as string);
      const it = await conversionApi.items(r.id);
      return { r, it };
    },
    onSuccess: ({ r, it }) => {
      setRun(r);
      setItems(it);
    },
  });

  if (!importId) {
    return <EmptyState icon={Boxes} title={t("conversion.noImport")} description={t("tree.noImportDesc")} />;
  }

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("conversion.title")}</h1>
        <p className="text-fg-dim">{t("conversion.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("conversion.planTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 rounded-sm border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
            <strong>{t("export.dryRunTitle")}</strong> {t("conversion.dryRun")}
          </p>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {t("conversion.generate")}
          </Button>
        </CardContent>
      </Card>

      {run ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("conversion.resultTitle", { count: items.length })}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-3 flex gap-2">
              <a href={exportUrl.conversionCsv(run.id)}>
                <Button variant="secondary" size="sm">{t("common.exportCsv")}</Button>
              </a>
              <a href={exportUrl.conversionScript(run.id)}>
                <Button variant="secondary" size="sm">{t("conversion.composerScript")}</Button>
              </a>
            </div>
            <ul className="flex flex-col gap-1">
              {items.map((it) => (
                <li key={it.id} className="flex items-center gap-2 rounded-sm bg-bg-2 px-3 py-1.5 font-mono text-sm">
                  <Badge variant="info">{it.source_ext}</Badge>
                  <span className="break-all">
                    {it.source_path} <span className="text-brand-blue-light">&rarr;</span> {it.target_path}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
