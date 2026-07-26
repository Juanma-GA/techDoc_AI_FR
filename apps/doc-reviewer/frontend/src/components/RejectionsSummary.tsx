import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { Suggestion } from "../types/domain";

const SEV_CLASS: Record<string, string> = {
  error: "danger",
  warning: "warn",
  info: "info",
};

function truncate(s: string, n = 70): string {
  const t = (s ?? "").replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n)}…` : t;
}

/**
 * Synthese exploitable des rejets : une ligne PAR anomalie rejetee (document
 * cliquable, page, regle, severite, texte rejete, motif) + export CSV. Utilisee
 * dans le Dashboard et la page Donnees.
 */
export function RejectionsSummary({
  rejected,
  docName,
  limit,
}: {
  rejected: Suggestion[];
  docName: (id: string) => string;
  limit?: number;
}): JSX.Element {
  const { t } = useTranslation();

  const rows = useMemo(
    () =>
      [...rejected].sort(
        (a, b) =>
          docName(a.document_id).localeCompare(docName(b.document_id)) ||
          a.page - b.page,
      ),
    [rejected, docName],
  );
  const shown = limit ? rows.slice(0, limit) : rows;

  const exportCsv = (): void => {
    const header = ["document", "page", "rule_code", "severity", "rejected_text", "motif"];
    const data = rows.map((s) => [
      docName(s.document_id),
      String(s.page),
      s.rule_code,
      s.severity,
      s.original_text ?? "",
      s.feedback ?? "",
    ]);
    const esc = (c: string): string => `"${(c ?? "").replace(/"/g, '""')}"`;
    const csv = [header, ...data].map((r) => r.map(esc).join(",")).join("\n");
    const blob = new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rejets.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div
        className="row"
        style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}
      >
        <span className="label">
          {t("data.rejects.total", { count: rejected.length })}
        </span>
        <button
          type="button"
          className="btn ghost small"
          disabled={rejected.length === 0}
          onClick={exportCsv}
        >
          {t("data.rejects.export")}
        </button>
      </div>

      {rejected.length === 0 ? (
        <p className="empty-state">{t("data.rejects.empty")}</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="rules-table">
            <thead>
              <tr>
                <th>{t("data.rejects.document")}</th>
                <th>{t("data.rejects.page")}</th>
                <th>{t("data.rejects.rule")}</th>
                <th>{t("reviewer.panel.filters.severity")}</th>
                <th>{t("data.rejects.rejectedText")}</th>
                <th>{t("data.rejects.motifs")}</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((s) => (
                <tr key={s.id}>
                  <td>
                    <Link to={`/documents/${s.document_id}`}>{truncate(docName(s.document_id), 34)}</Link>
                  </td>
                  <td>p.{s.page}</td>
                  <td><span className="badge default">{s.rule_code}</span></td>
                  <td><span className={`badge ${SEV_CLASS[s.severity] ?? "info"}`}>{s.severity}</span></td>
                  <td title={s.original_text}>{truncate(s.original_text) || <span className="label">—</span>}</td>
                  <td>{s.feedback?.trim() ? s.feedback : <span className="label">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {limit && rows.length > limit ? (
            <p className="label" style={{ marginTop: 6 }}>
              <Link to="/data">{t("data.rejects.seeAll", { count: rows.length })}</Link>
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
