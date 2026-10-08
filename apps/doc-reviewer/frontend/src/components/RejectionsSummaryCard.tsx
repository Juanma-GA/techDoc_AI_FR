import { ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useRejectionsSummary } from "../hooks/useSuggestions";
import { toCsv } from "../lib/csv";
import { isAiGeneratedSuggestion, localizedRuleCode } from "../lib/suggestionText";
import type { RejectionItem } from "../types/domain";

const SEV_CLASS: Record<string, string> = {
  error: "danger",
  warning: "warn",
  info: "info",
};

export function RejectionsSummaryCard() {
  const { t } = useTranslation();
  const q = useRejectionsSummary(false);
  const data = q.data;
  const byDocument = new Map<string, { file: string; items: RejectionItem[] }>();
  for (const item of data?.items ?? []) {
    const group = byDocument.get(item.document_id);
    if (group) group.items.push(item);
    else byDocument.set(item.document_id, { file: item.file, items: [item] });
  }
  const documents = Array.from(byDocument, ([documentId, group]) => ({
    documentId,
    ...group,
  })).sort((left, right) => left.file.localeCompare(right.file));

  const exportCsv = (): void => {
    if (!data) return;
    const header = ["fichier", "regle", "severite", "message", "motif"];
    const rows = data.items.map((i) => [
      i.file,
      localizedRuleCode(i.rule_code, t),
      t(`reviewer.suggestion.severity.${i.severity}`),
      i.message,
      i.feedback,
    ]);
    const csv = toCsv([header, ...rows]);
    const blob = new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rejets.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <article className="card">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        {data ? (
          <span className="label">{t("data.rejects.total", { count: data.total })}</span>
        ) : <span />}
        <button
          type="button"
          className="btn ghost small"
          disabled={!data || data.total === 0}
          onClick={exportCsv}
        >
          {t("data.rejects.export")}
        </button>
      </div>

      {q.isLoading ? (
        <div className="empty-state">{t("common.loading")}</div>
      ) : q.error ? (
        <div className="empty-state error">{q.error.message}</div>
      ) : !data || data.total === 0 ? (
        <div className="empty-state">{t("data.rejects.empty")}</div>
      ) : (
        <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
          {documents.map((document) => (
            <details className="collapsible" key={document.documentId}>
              <summary
                className="collapsible-summary"
                style={{ cursor: "pointer", listStyle: "none", userSelect: "none" }}
              >
                <ChevronRight size={16} aria-hidden="true" />
                <strong
                  className="grow"
                  title={document.file}
                  style={{ overflow: "hidden", textOverflow: "ellipsis" }}
                >
                  {document.file}
                </strong>
                <span className="label" style={{ whiteSpace: "nowrap" }}>
                  {t("data.rejects.total", { count: document.items.length })}
                </span>
              </summary>
              <ul style={{ listStyle: "none", margin: 0, padding: "0 10px" }}>
                {document.items.map((item) => (
                  <li
                    key={item.id}
                    style={{ padding: "12px 0", borderBottom: "1px solid var(--border)" }}
                  >
                    <div className="row" style={{ alignItems: "flex-start" }}>
                      <div className="grow" style={{ minWidth: 0 }}>
                        <div className="row" style={{ gap: 6 }}>
                          <span className="badge default">
                            {localizedRuleCode(item.rule_code, t)}
                          </span>
                          <span className={`badge ${SEV_CLASS[item.severity] ?? "info"}`}>
                            {t(`reviewer.suggestion.severity.${item.severity}`)}
                          </span>
                          {isAiGeneratedSuggestion(item.source_kind, item.rule_code) ? (
                            <span className="badge info">{t("reviewer.source.ai")}</span>
                          ) : null}
                        </div>
                        <p style={{ margin: "8px 0 0", overflowWrap: "anywhere" }}>
                          {item.message}
                        </p>
                        {item.feedback?.trim() ? (
                          <p style={{ margin: "6px 0 0", overflowWrap: "anywhere" }}>
                            <strong>{t("data.rejects.motifs")}:</strong> {item.feedback}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </details>
          ))}
          </div>
      )}
    </article>
  );
}
