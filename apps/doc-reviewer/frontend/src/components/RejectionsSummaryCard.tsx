import { useTranslation } from "react-i18next";

import { useRejectionsSummary } from "../hooks/useSuggestions";

import { BarList, type BarItem } from "./BarList";

const SEV_CLASS: Record<string, string> = {
  error: "danger",
  warning: "warn",
  info: "info",
};

function truncate(s: string, n = 90): string {
  const t = (s ?? "").replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n)}…` : t;
}

/**
 * Synthèse des rejets (parité 1:1 avec corpus-agent) : paragraphe de synthèse
 * IA (motifs récurrents, règles à affiner) + répartition des rejets par règle
 * + tableau exploitable (fichier, règle, sévérité, message, motif) + export CSV.
 * Tout provient de `GET /suggestions/rejections-summary`.
 */
export function RejectionsSummaryCard() {
  const { t } = useTranslation();
  const q = useRejectionsSummary();
  const data = q.data;

  const byRule: BarItem[] = (data?.by_rule ?? []).map((r) => ({
    label: r.rule_code || t("data.rejects.noRule"),
    value: r.count,
  }));

  const exportCsv = (): void => {
    if (!data) return;
    const header = ["fichier", "regle", "severite", "message", "motif"];
    const rows = data.items.map((i) => [i.file, i.rule_code, i.severity, i.message, i.feedback]);
    const esc = (c: string): string => `"${(c ?? "").replace(/"/g, '""')}"`;
    const csv = [header, ...rows].map((r) => r.map(esc).join(";")).join("\n");
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
        <h2 className="card-title" style={{ margin: 0 }}>
          {t("data.rejects.title")}
        </h2>
        <button
          type="button"
          className="btn ghost small"
          disabled={!data || data.total === 0}
          onClick={exportCsv}
        >
          {t("data.rejects.export")}
        </button>
      </div>
      <p className="card-sub">{t("data.rejects.subtitle")}</p>

      {q.isLoading ? (
        <div className="empty-state">{t("common.loading")}</div>
      ) : !data || data.total === 0 ? (
        <div className="empty-state">{t("data.rejects.empty")}</div>
      ) : (
        <>
          <div className="label" style={{ margin: "4px 0 10px" }}>
            {t("data.rejects.total", { count: data.total })}
          </div>

          {/* Synthèse IA (ou note si indisponible). */}
          {data.llm_used && data.synthese ? (
            <div
              className="banner"
              style={{ display: "block", marginBottom: 12, lineHeight: 1.5, whiteSpace: "pre-wrap" }}
            >
              <strong style={{ display: "block", marginBottom: 4 }}>
                {t("data.rejects.aiTitle")}
              </strong>
              {data.synthese}
            </div>
          ) : (
            <p className="hint" style={{ marginBottom: 12 }}>
              {t("data.rejects.aiDisabled")}
            </p>
          )}

          {/* Répartition par règle (indice de faux positifs par règle). */}
          <h3 className="card-title">
            {t("data.rejects.byRule")}
          </h3>
          <div style={{ marginBottom: 12 }}>
            <BarList items={byRule} />
          </div>

          {/* Tableau exploitable des rejets. */}
          <div className="table-scroll">
            <table className="rules-table">
              <thead>
                <tr>
                  <th>{t("data.rejects.document")}</th>
                  <th>{t("data.rejects.rule")}</th>
                  <th>{t("data.rejects.colSeverity")}</th>
                  <th>{t("data.rejects.colMessage")}</th>
                  <th>{t("data.rejects.motifs")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.id}>
                    <td title={i.file}>{truncate(i.file, 34)}</td>
                    <td>
                      <span className="badge default">{i.rule_code}</span>
                    </td>
                    <td>
                      <span className={`badge ${SEV_CLASS[i.severity] ?? "info"}`}>{i.severity}</span>
                    </td>
                    <td title={i.message}>{truncate(i.message)}</td>
                    <td>{i.feedback?.trim() ? i.feedback : <span className="label">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </article>
  );
}
