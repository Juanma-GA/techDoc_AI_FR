import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { ComparisonResults } from "../components/comparison/ComparisonResults";
import { ComparisonSetupCard } from "../components/comparison/ComparisonSetupCard";
import { PageHeader } from "../components/PageHeader";
import { comparisonApi, type ComparisonDetail } from "../lib/comparisonApi";
import i18n from "../i18n";

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

export function DocumentComparison() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [armedDeleteId, setArmedDeleteId] = useState<string | null>(null);
  const [formVersion, setFormVersion] = useState(0);
  const language = (i18n.resolvedLanguage ?? "fr").startsWith("en") ? "en" : "fr";
  const saved = useQuery({ queryKey: ["comparisons"], queryFn: comparisonApi.list });
  const selected = useQuery({
    queryKey: ["comparison", selectedId],
    queryFn: () => comparisonApi.read(selectedId as string),
    enabled: selectedId !== null,
  });
  const summary = useMutation({
    mutationFn: ({ id, lang }: { id: string; lang: "fr" | "en" }) => comparisonApi.synthesize(id, lang),
    onSuccess: (result, variables) => {
      queryClient.setQueryData<ComparisonDetail>(["comparison", variables.id], (old) =>
        old ? { ...old, ...result } : old,
      );
      void queryClient.invalidateQueries({ queryKey: ["comparisons"] });
    },
  });
  const create = useMutation({
    mutationFn: ({
      files,
      referenceIndex,
      pageSimilarityThreshold,
    }: {
      files: File[];
      referenceIndex: number;
      pageSimilarityThreshold: number;
    }) => comparisonApi.create(files, referenceIndex, pageSimilarityThreshold),
    onSuccess: (result) => {
      setFormVersion((version) => version + 1);
      setSelectedId(result.id);
      queryClient.setQueryData(["comparison", result.id], result);
      void queryClient.invalidateQueries({ queryKey: ["comparisons"] });
      summary.mutate({ id: result.id, lang: language });
    },
  });
  const remove = useMutation({
    mutationFn: comparisonApi.delete,
    onSuccess: async (_result, id) => {
      if (selectedId === id) setSelectedId(null);
      setArmedDeleteId(null);
      queryClient.removeQueries({ queryKey: ["comparison", id] });
      await queryClient.invalidateQueries({ queryKey: ["comparisons"] });
    },
  });

  useEffect(() => {
    if (!armedDeleteId) return;
    const timer = window.setTimeout(() => setArmedDeleteId(null), 3000);
    return () => window.clearTimeout(timer);
  }, [armedDeleteId]);
  useEffect(() => {
    const firstSaved = saved.data?.[0];
    if (!selectedId && firstSaved && !remove.isPending) setSelectedId(firstSaved.id);
  }, [remove.isPending, saved.data, selectedId]);

  const confirmDelete = (id: string) =>
    armedDeleteId === id ? remove.mutate(id) : setArmedDeleteId(id);
  const selectedComparison = selected.data;
  const retrySelectedSummary = () => {
    const current = selected.data;
    if (current) summary.mutate({ id: current.id, lang: language });
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("comparison.title")} subtitle={t("comparison.subtitle")} />
      <div className="grid gap-6 lg:grid-cols-2">
        <ComparisonSetupCard
          key={formVersion}
          onCompare={(files, referenceIndex, pageSimilarityThreshold) =>
            create.mutate({ files, referenceIndex, pageSimilarityThreshold })
          }
          isCreating={create.isPending}
          createError={create.isError ? t("comparison.createError", { message: errorMessage(create.error) }) : null}
        />

        <section className="card" aria-labelledby="comparison-saved-title">
          <h2 id="comparison-saved-title" className="card-title">{t("comparison.savedTitle")}</h2>
          <div className="mt-5 space-y-4">
            {saved.isLoading ? <p className="empty-state">{t("common.loading")}</p> : null}
            {saved.isError ? <p className="error" role="alert">{t("comparison.loadError", { message: errorMessage(saved.error) })}</p> : null}
            {saved.data?.length ? (
              <ul className="item-list">
                {saved.data.map((item) => (
                  <li key={item.id} className="item-row">
                    <button
                      type="button"
                      className="btn ghost small"
                      aria-pressed={selectedId === item.id}
                      onClick={() => setSelectedId(item.id)}
                    >
                      {item.title} · {item.file_count}
                    </button>
                    <button
                      type="button"
                      className={`btn small ${armedDeleteId === item.id ? "danger" : "ghost"}`}
                      disabled={remove.isPending}
                      onClick={() => confirmDelete(item.id)}
                    >
                      {armedDeleteId === item.id ? t("comparison.deleteAgain") : t("comparison.delete")}
                    </button>
                  </li>
                ))}
              </ul>
            ) : saved.isSuccess ? <p className="empty-state">{t("comparison.savedEmpty")}</p> : null}
            {remove.isError ? <p className="error" role="alert">{t("comparison.deleteError", { message: errorMessage(remove.error) })}</p> : null}
          </div>
        </section>
      </div>

      {selected.isLoading ? <p className="empty-state" aria-busy="true">{t("comparison.loading")}</p> : null}
      {selected.isError ? <p className="error" role="alert">{t("comparison.loadError", { message: errorMessage(selected.error) })}</p> : null}
      {selectedId && selectedComparison ? (
        <ComparisonResults
          comparison={selectedComparison}
          language={language}
          isSummarizing={summary.isPending && summary.variables?.id === selectedComparison.id}
          summaryError={summary.isError && summary.variables?.id === selectedComparison.id ? errorMessage(summary.error) : ""}
          onRetrySummary={retrySelectedSummary}
        />
      ) : null}
    </div>
  );
}
