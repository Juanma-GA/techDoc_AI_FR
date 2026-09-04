import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { anomaliesApi } from "../lib/api";
import type { RejectionsSummaryOut } from "../lib/types";

import { BarList, type BarItem } from "./BarList";

const SEV_CLASS: Record<string, string> = {
  high: "danger",
  medium: "warn",
  low: "info",
};

function truncate(s: string, n = 90): string {
  const t = (s ?? "").replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n)}…` : t;
}

/**
 * Synthèse des rejets d'un projet : paragraphe de synthèse IA (motifs récurrents,
 * règles à affiner) + répartition des rejets par sujet + tableau exploitable
 * (fichier, sujet, sévérité, message, motif) + export CSV. Affiché dans le
 * Manager quand un seul projet est sélectionné.
 */
export function RejectionsSummaryCard({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const q = useQuery<RejectionsSummaryOut>({
    queryKey: ["rejections-summary", projectId],
    queryFn: () => anomaliesApi.rejectionsSummary(projectId, true),
  });

  const data = q.data;
  const byCat: BarItem[] = (data?.by_category ?? []).map((c) => ({
    label: c.category || t("rejections.noSubject"),
    value: c.count,
  }));

  const exportCsv = (): void => {
    if (!data) return;
    const header = ["fichier", "sujet", "severite", "message", "motif"];
    const rows = data.items.map((i) => [
      i.file,
      i.category,
      i.severity,
      i.message,
      i.feedback,
    ]);
    const esc = (c: string): string => `"${(c ?? "").replace(/"/g, '""')}"`;
    const csv = [header, ...rows].map((r) => r.map(esc).join(";")).join("\n");
    const blob = new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rejets.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2 className="card-title" style={{ margin: 0 }}>
          {t("rejections.title")}
        </h2>
        <button
          type="button"
          className="btn ghost small"
          disabled={!data || data.total === 0}
          onClick={exportCsv}
        >
          {t("rejections.export")}
        </button>
      </div>

      {q.isLoading ? (
        <div className="empty-state">{t("common.loading")}</div>
      ) : !data || data.total === 0 ? (
        <div className="empty-state">{t("rejections.empty")}</div>
      ) : (
        <>
          <div className="label" style={{ margin: "4px 0 10px" }}>
            {t("rejections.total", { count: data.total })}
          </div>

          {/* Synthèse IA (ou note si indisponible). */}
          {data.llm_used && data.synthese ? (
            <div
              className="banner"
              style={{ display: "block", marginBottom: 12, lineHeight: 1.5, whiteSpace: "pre-wrap" }}
            >
              <strong style={{ display: "block", marginBottom: 4 }}>
                {t("rejections.aiTitle")}
              </strong>
              {data.synthese}
            </div>
          ) : (
            <div className="label" style={{ marginBottom: 12 }}>
              {t("rejections.aiDisabled")}
            </div>
          )}

          {/* Répartition par sujet (indice de faux positifs par règle). */}
          <h3 className="card-title" style={{ fontSize: "0.95rem" }}>
            {t("rejections.bySubject")}
          </h3>
          <BarList items={byCat} />

          {/* Tableau exploitable des rejets. */}
          <div style={{ overflowX: "auto", marginTop: 12 }}>
            <table className="rules-table">
              <thead>
                <tr>
                  <th>{t("rejections.colFile")}</th>
                  <th>{t("rejections.colSubject")}</th>
                  <th>{t("rejections.colSeverity")}</th>
                  <th>{t("rejections.colMessage")}</th>
                  <th>{t("rejections.colMotif")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.id}>
                    <td title={i.file}>{truncate(i.file, 34)}</td>
                    <td>{i.category || <span className="label">—</span>}</td>
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
    </div>
  );
}
