import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { FilePicker } from "../components/FilePicker";
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
  // Chemin du mapping memorise dans le workspace (pre-rempli au retour sur l'onglet).
  const srcPath = useWorkspace((s) => s.sources.mapping);
  const setSrcPath = (p: string) => useWorkspace.getState().setSource("mapping", p);
  const [run, setRun] = useState<ReplacementRunDto | null>(null);
  const [items, setItems] = useState<ReplacementItemDto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const onResult = (r: ReplacementRunDto, it: ReplacementItemDto[]) => {
    setError(null);
    setRun(r);
    setItems(it);
  };
  const onError = (e: unknown) => {
    setFeedback(null);
    setError(e instanceof ApiClientError ? e.message : String(e));
  };

  const fileMutation = useMutation({
    mutationFn: async (file: File) => {
      const r = await replacementApi.run(importId as string, file);
      const it = await replacementApi.items(r.id);
      return { r, it };
    },
    onSuccess: ({ r, it }) => {
      setFeedback(null);
      onResult(r, it);
    },
    onError,
  });

  const sourceMutation = useMutation({
    mutationFn: async (path: string) => {
      const r = await replacementApi.source(importId as string, path);
      const it = await replacementApi.items(r.id);
      return { r, it };
    },
    onSuccess: ({ r, it }) => {
      onResult(r, it);
      setFeedback(t("replacement.sourceApplied"));
    },
    onError,
  });

  if (!importId) {
    return (
      <div className="empty-state">
        <h3 className="card-title">{t("replacement.noImport")}</h3>
        <p className="hint">{t("tree.noImportDesc")}</p>
      </div>
    );
  }

  const submitSource = () => {
    const path = srcPath.trim();
    if (!path) {
      setError(t("replacement.sourceRequired"));
      return;
    }
    sourceMutation.mutate(path);
  };

  return (
    <div className="form" style={{ maxWidth: "56rem" }}>
      <article className="card">
        <h2 className="card-title">{t("replacement.mappingTitle")}</h2>
        <p className="banner warn">
          <strong>{t("export.dryRunTitle")}</strong> {t("replacement.dryRun")}
        </p>

        <p className="label">{t("replacement.sourceLabel")}</p>
        <div className="form">
          <FilePicker exts={[".csv", ".json"]} value={srcPath} onChange={setSrcPath} />
          <div>
            <button type="button" className="btn primary" onClick={submitSource} disabled={sourceMutation.isPending}>
              {t("replacement.useSource")}
            </button>
          </div>
        </div>

        <p className="label" style={{ marginTop: "1rem" }}>{t("replacement.orUpload")}</p>
        <div className="field">
          <span className="field-label">{t("replacement.dropLabel")}</span>
          <input
            type="file"
            className="input"
            accept=".csv,.json"
            disabled={fileMutation.isPending}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) fileMutation.mutate(f);
            }}
          />
          <p className="hint">{t("replacement.dropDescription")}</p>
        </div>

        {feedback ? <p className="success">{feedback}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </article>

      <article className="card">
        <h2 className="card-title">
          {run ? t("replacement.resultTitle", { count: items.length }) : t("replacement.resultTitle", { count: 0 })}
        </h2>
        {run ? (
          <>
            <div className="row">
              <a href={exportUrl.replacementCsv(run.id)}>
                <button type="button" className="btn secondary small">
                  {t("common.exportCsv")}
                </button>
              </a>
              <a href={exportUrl.replacementMacro(run.id)}>
                <button type="button" className="btn secondary small">
                  {t("replacement.macro")}
                </button>
              </a>
            </div>
            {items.length ? (
              <ul className="item-list">
                {items.map((it) => (
                  <li key={it.id} className="item-row">
                    <div className="item-main">
                      <span className="item-name">{it.occurrence_path}</span>
                      <span className="item-meta">
                        {it.old_ref} &rarr; {it.new_ref}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hint">{t("replacement.resultEmpty")}</p>
            )}
          </>
        ) : (
          <p className="hint">{t("replacement.pickMapping")}</p>
        )}
      </article>
    </div>
  );
}
