import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiClientError, promptsApi, type PromptsDto } from "../lib/api";

type PromptKey = "pptx_analysis" | "pptx_fill";

// Edition runtime des prompts Mistral, skin preview (.card / .label / .badge).
export function PromptsCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [drafts, setDrafts] = useState<Record<PromptKey, string>>({
    pptx_analysis: "",
    pptx_fill: "",
  });
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  const promptsQuery = useQuery<PromptsDto, ApiClientError>({
    queryKey: ["settings", "prompts"],
    queryFn: promptsApi.read,
  });

  useEffect(() => {
    if (promptsQuery.data) {
      setDrafts({
        pptx_analysis: promptsQuery.data.pptx_analysis.value,
        pptx_fill: promptsQuery.data.pptx_fill.value,
      });
    }
  }, [promptsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (vars: { key: PromptKey; value: string }) =>
      promptsApi.write(
        vars.key === "pptx_analysis"
          ? { pptx_analysis: vars.value }
          : { pptx_fill: vars.value },
      ),
    onSuccess: (data) => {
      qc.setQueryData(["settings", "prompts"], data);
      setSavedNotice(t("settings.saved"));
    },
  });

  if (promptsQuery.isLoading) {
    return (
      <div className="card">
        <span className="spinner" />
      </div>
    );
  }

  const fields: { key: PromptKey; label: string }[] = [
    { key: "pptx_analysis", label: t("settings.promptAnalysisLabel") },
    { key: "pptx_fill", label: t("settings.promptFillLabel") },
  ];

  return (
    <div className="card">
      <h2 className="card-title">{t("settings.promptsTitle")}</h2>
      <p style={{ color: "var(--fg-dim)", fontSize: "0.85rem", marginBottom: 12 }}>
        {t("settings.promptsSubtitle")}
      </p>
      <div className="form">
        {fields.map(({ key, label }) => {
          const isDefault = promptsQuery.data?.[key]?.is_default ?? true;
          return (
            <div key={key}>
              <div className="row" style={{ gap: 8, marginBottom: 4 }}>
                <span className="label">{label}</span>
                {isDefault ? (
                  <span className="badge off">{t("settings.promptDefault")}</span>
                ) : (
                  <span className="badge info">{t("settings.promptCustom")}</span>
                )}
              </div>
              <textarea
                rows={6}
                value={drafts[key]}
                onChange={(e) =>
                  setDrafts((d) => ({ ...d, [key]: e.target.value }))
                }
              />
              <div className="row" style={{ gap: 8, marginTop: 6 }}>
                <button
                  type="button"
                  className="btn primary small"
                  disabled={saveMutation.isPending}
                  onClick={() => {
                    setSavedNotice(null);
                    saveMutation.mutate({ key, value: drafts[key] });
                  }}
                >
                  {t("settings.save")}
                </button>
                <button
                  type="button"
                  className="btn ghost small"
                  disabled={saveMutation.isPending || isDefault}
                  onClick={() => {
                    setSavedNotice(null);
                    saveMutation.mutate({ key, value: "" });
                  }}
                >
                  {t("settings.promptReset")}
                </button>
              </div>
            </div>
          );
        })}
        {savedNotice ? <div className="success">{savedNotice}</div> : null}
      </div>
    </div>
  );
}
