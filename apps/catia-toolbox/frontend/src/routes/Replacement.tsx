import { Button, Card, CardContent, CardHeader, CardTitle, EmptyState, FileDropzone } from "@internal/ui";
import { useMutation } from "@tanstack/react-query";
import { Replace } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  exportUrl,
  replacementApi,
  type ReplacementItemDto,
  type ReplacementRunDto,
} from "../lib/api";
import { useWorkspace } from "../stores/workspace";

export function Replacement() {
  const { t } = useTranslation();
  const { importId } = useWorkspace();
  const [run, setRun] = useState<ReplacementRunDto | null>(null);
  const [items, setItems] = useState<ReplacementItemDto[]>([]);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (file: File) => {
      const r = await replacementApi.run(importId as string, file);
      const it = await replacementApi.items(r.id);
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
    return <EmptyState icon={Replace} title={t("replacement.noImport")} description={t("tree.noImportDesc")} />;
  }

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("replacement.title")}</h1>
        <p className="text-fg-dim">{t("replacement.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("replacement.mappingTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 rounded-sm border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
            <strong>{t("export.dryRunTitle")}</strong> {t("replacement.dryRun")}
          </p>
          <FileDropzone
            accept=".csv,.json"
            multiple={false}
            label={t("replacement.dropLabel")}
            description={t("replacement.dropDescription")}
            disabled={mutation.isPending}
            onFiles={(files) => files[0] && mutation.mutate(files[0])}
          />
          {error ? <p className="mt-2 text-sm text-danger">{error}</p> : null}
        </CardContent>
      </Card>

      {run ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("replacement.resultTitle", { count: items.length })}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-3 flex gap-2">
              <a href={exportUrl.replacementCsv(run.id)}>
                <Button variant="secondary" size="sm">{t("common.exportCsv")}</Button>
              </a>
              <a href={exportUrl.replacementMacro(run.id)}>
                <Button variant="secondary" size="sm">{t("replacement.macro")}</Button>
              </a>
            </div>
            <ul className="flex flex-col gap-1">
              {items.map((it) => (
                <li key={it.id} className="rounded-sm bg-bg-2 px-3 py-1.5 font-mono text-sm">
                  <span className="break-all">{it.occurrence_path}</span>
                  <div className="text-fg-dim">
                    {it.old_ref} <span className="text-brand-blue-light">&rarr;</span> {it.new_ref}
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
