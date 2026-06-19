import { useMutation } from "@tanstack/react-query";
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
    return (
      <div className="empty-state">
        <h3 className="card-title">{t("conversion.noImport")}</h3>
        <p className="hint">{t("tree.noImportDesc")}</p>
      </div>
    );
  }

  return (
    <div className="grow form" style={{ maxWidth: "56rem" }}>
      <article className="card">
        <h2 className="card-title">{t("conversion.planTitle")}</h2>
        <p className="banner warn">
          <strong>{t("export.dryRunTitle")}</strong> {t("conversion.dryRun")}
        </p>
        <button type="button" className="btn primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {t("conversion.generate")}
        </button>
        {mutation.isError ? (
          <p className="error" style={{ marginTop: "0.5rem" }}>
            {(mutation.error as Error).message}
          </p>
        ) : null}
      </article>

      {run ? (
        <article className="card">
          <h2 className="card-title">{t("conversion.resultTitle", { count: items.length })}</h2>
          <div className="row" style={{ marginBottom: "0.75rem" }}>
            <a href={exportUrl.conversionCsv(run.id)}>
              <button type="button" className="btn secondary small">
                {t("common.exportCsv")}
              </button>
            </a>
            <a href={exportUrl.conversionScript(run.id)}>
              <button type="button" className="btn secondary small">
                {t("conversion.composerScript")}
              </button>
            </a>
          </div>
          {items.length === 0 ? (
            <p className="hint">{t("conversion.noItems")}</p>
          ) : (
            <ul className="item-list">
              {items.map((it) => (
                <li key={it.id} className="item-row">
                  <span className="badge info">{it.source_ext}</span>
                  <span className="item-main" style={{ fontFamily: '"JetBrains Mono", monospace', wordBreak: "break-all" }}>
                    {it.source_path} <span className="label">&rarr;</span> {it.target_path}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </article>
      ) : null}
    </div>
  );
}
