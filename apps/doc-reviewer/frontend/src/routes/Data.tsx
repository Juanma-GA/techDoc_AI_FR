import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import { RejectionsSummary } from "../components/RejectionsSummary";
import { useDocuments } from "../hooks/useDocuments";
import { useRules } from "../hooks/useRules";
import { api } from "../lib/api";
import type {
  ResetAllResult,
  Rule,
  Suggestion,
  WipeSuggestionsResult,
} from "../types/domain";

type Dialog = "sugs" | "all" | null;

export function Data(): JSX.Element {
  const { t } = useTranslation();

  const docs = useDocuments();
  const rules = useRules();
  const suggestions = useQuery({
    queryKey: ["suggestions", "all"],
    queryFn: () => api.get<Suggestion[]>("/suggestions"),
  });

  const [dialog, setDialog] = useState<Dialog>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = async (): Promise<void> => {
    await Promise.all([docs.refetch(), rules.refetch(), suggestions.refetch()]);
  };

  const wipeSuggestions = (): void => {
    setBusy(true);
    setFeedback(null);
    api
      .post<WipeSuggestionsResult>("/admin/wipe-suggestions")
      .then(async (r) => {
        setFeedback(t("data.wipedSugs", { count: r.deleted }));
        await refresh();
      })
      .catch((err: unknown) => {
        setFeedback(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setBusy(false));
  };

  const resetAll = (): void => {
    setBusy(true);
    setFeedback(null);
    api
      .post<ResetAllResult>("/admin/reset")
      .then(async (r) => {
        const folders = r.storage_folders_cleaned + r.orphan_folders_cleaned;
        setFeedback(
          t("data.resetDone", { docs: r.documents_deleted, folders }),
        );
        await refresh();
      })
      .catch((err: unknown) => {
        setFeedback(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setBusy(false));
  };

  const loading = docs.isLoading || rules.isLoading || suggestions.isLoading;
  const error = docs.error ?? rules.error ?? suggestions.error;

  // Synthese des rejets (composant partage, table exploitable + CSV).
  const rejected = (suggestions.data ?? []).filter((s) => s.status === "rejected");
  const docName = (id: string): string =>
    docs.data?.find((d) => d.id === id)?.original_filename ?? id;

  return (
    <div>
      <PageHeader title={t("data.title")} subtitle={t("data.subtitle")} />

      <article className="card">
        <h2 className="card-title">{t("data.overview")}</h2>
        {loading ? (
          <p className="hint">{t("common.loading")}</p>
        ) : error ? (
          <p className="error">
            {error instanceof Error ? error.message : String(error)}
          </p>
        ) : (
          <div className="kpi-grid">
            <Kpi label={t("data.kpi.pdfs")} value={docs.data?.length ?? 0} />
            <Kpi
              label={t("data.kpi.sugs")}
              value={suggestions.data?.length ?? 0}
            />
            <Kpi label={t("data.kpi.rejects")} value={rejected.length} />
            <Kpi label={t("data.kpi.rules")} value={countRules(rules.data)} />
          </div>
        )}
      </article>

      {/* Synthese des rejets : table exploitable (document / page / regle / motif) + CSV. */}
      <article className="card">
        <h2 className="card-title">{t("data.rejects.title")}</h2>
        <p className="card-sub">{t("data.rejects.subtitle")}</p>
        <RejectionsSummary rejected={rejected} docName={docName} />
      </article>

      <article className="card">
        <h2 className="card-title">{t("data.reset")}</h2>
        <div className="banner warn">{t("data.resetWarn")}</div>
        <div className="row">
          <button
            type="button"
            disabled={busy}
            onClick={() => setDialog("sugs")}
            className="btn secondary"
          >
            {t("data.resetSugs")}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => setDialog("all")}
            className="btn danger"
          >
            {t("data.resetAll")}
          </button>
          {feedback ? (
            <span className="hint" style={{ marginLeft: "auto" }}>
              {feedback}
            </span>
          ) : null}
        </div>
      </article>

      <ConfirmDialog
        open={dialog === "sugs"}
        onOpenChange={(o) => setDialog(o ? "sugs" : null)}
        title={t("data.resetSugs")}
        description={t("data.confirmSugs")}
        confirmLabel={t("data.resetSugs")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={wipeSuggestions}
      />
      <ConfirmDialog
        open={dialog === "all"}
        onOpenChange={(o) => setDialog(o ? "all" : null)}
        title={t("data.resetAll")}
        description={t("data.confirmAll")}
        confirmLabel={t("data.resetAll")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={resetAll}
      />
    </div>
  );
}

function countRules(rules: Rule[] | undefined): number {
  return rules?.length ?? 0;
}

function Kpi({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <div className="kpi">
      <span className="label">{label}</span>
      <div className="kpi-value">{value}</div>
    </div>
  );
}
