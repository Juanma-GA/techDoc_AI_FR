import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";
import { RejectionsSummaryCard } from "../components/RejectionsSummaryCard";
import { SeverityBadge } from "../components/SeverityBadge";
import { useDocuments } from "../hooks/useDocuments";
import { api } from "../lib/api";
import { localizedSuggestionMessage } from "../lib/suggestionText";
import type { Severity, Suggestion } from "../types/domain";

type KpiTone = "info" | "warn" | "ok" | "neutral";

const KPI_TONE: Record<KpiTone, string> = {
  info: "info",
  warn: "warn",
  ok: "ok",
  neutral: "",
};

// Bar fill colours are mapped per functional category, not per specific norm:
// S1000D / MAT10000 / ATA... all share the `standard` bucket emitted by the
// catalog runner. Falls back to the brand colour for unknown kinds.
const KIND_FILL: Record<string, string> = {
  standard: "var(--warning)",
  custom: "var(--brand)",
  units: "var(--info)",
  vision: "var(--info)",
};

const SEV_FILL: Record<Severity, string> = {
  error: "var(--danger)",
  warning: "var(--warning)",
  info: "var(--info)",
};

type BarRow = { label: string; count: number; fill: string };

type FrequentError = {
  ruleCode: string;
  message: string;
  severity: Severity;
  count: number;
};

export function Dashboard(): JSX.Element {
  const { t } = useTranslation();
  const docs = useDocuments();
  const suggestions = useQuery({
    queryKey: ["suggestions", "all"],
    queryFn: () => api.get<Suggestion[]>("/suggestions"),
  });

  const docList = docs.data ?? [];
  const sugList = suggestions.data ?? [];

  const isLoading = docs.isLoading || suggestions.isLoading;
  const error = docs.error ?? suggestions.error;

  const total = sugList.length;
  const open = sugList.filter((s) => s.status === "open").length;
  const applied = sugList.filter((s) => s.status === "applied").length;
  const rejected = sugList.filter((s) => s.status === "rejected").length;

  const sevCounts: Record<Severity, number> = { error: 0, warning: 0, info: 0 };
  for (const s of sugList) {
    if (s.severity in sevCounts) sevCounts[s.severity] = (sevCounts[s.severity] ?? 0) + 1;
  }
  const sevBars: BarRow[] = (["error", "warning", "info"] as const).map((sev) => ({
    label: t(`reviewer.suggestion.severity.${sev}`),
    count: sevCounts[sev] ?? 0,
    fill: SEV_FILL[sev] ?? "var(--info)",
  }));

  const kindCounts = new Map<string, number>();
  for (const s of sugList) {
    const k = s.rule_kind || "?";
    kindCounts.set(k, (kindCounts.get(k) ?? 0) + 1);
  }
  const kindBars: BarRow[] = [...kindCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, count]) => ({ label, count, fill: KIND_FILL[label] ?? "var(--brand)" }));

  const docName = (id: string): string =>
    docList.find((d) => d.id === id)?.original_filename ?? id;
  const byDoc = new Map<string, number>();
  for (const s of sugList) {
    if (s.status === "open") byDoc.set(s.document_id, (byDoc.get(s.document_id) ?? 0) + 1);
  }
  const topDocs: BarRow[] = [...byDoc.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([id, count]) => ({ label: docName(id), count, fill: "var(--warning)" }));

  const errorsByRule = new Map<string, FrequentError>();
  for (const s of sugList) {
    const ruleCode = s.rule_code || "?";
    const existing = errorsByRule.get(ruleCode);
    if (existing) {
      existing.count += 1;
    } else {
      errorsByRule.set(ruleCode, {
        ruleCode,
        message: localizedSuggestionMessage(s, t) || ruleCode,
        severity: s.severity,
        count: 1,
      });
    }
  }
  const frequentErrors = [...errorsByRule.values()]
    .sort((a, b) => b.count - a.count || a.ruleCode.localeCompare(b.ruleCode))
    .slice(0, 10);

  return (
    <div>
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />

      <Card title={t("dashboard.kpis")}>
        {isLoading ? (
          <p className="hint">{t("common.loading")}</p>
        ) : error ? (
          <p className="error">{error.message}</p>
        ) : (
          <div className="kpi-grid">
            <Kpi label={t("dashboard.kpi.pdfs")} value={docList.length} tone="info" />
            <Kpi label={t("dashboard.kpi.open")} value={open} tone="warn" />
            <Kpi label={t("dashboard.kpi.applied")} value={applied} tone="ok" />
            <Kpi label={t("dashboard.kpi.rejected")} value={rejected} tone="neutral" />
            <Kpi label={t("dashboard.kpi.total")} value={total} tone="neutral" />
          </div>
        )}
      </Card>

      <div className="grid-2">
        <Card title={t("dashboard.bySev")}>
          <BarList rows={sevBars} max={total} loading={isLoading} />
        </Card>
        <Card title={t("dashboard.byKind")}>
          <BarList rows={kindBars} max={total} loading={isLoading} />
        </Card>
      </div>

      <Card title={t("dashboard.topDocs")}>
        {isLoading ? (
          <p className="hint">{t("common.loading")}</p>
        ) : topDocs.length > 0 ? (
          <BarList
            rows={topDocs}
            max={Math.max(...topDocs.map((r) => r.count))}
            loading={false}
          />
        ) : (
          <p className="hint">{t("dashboard.noOpen")}</p>
        )}
      </Card>

      <Card title={t("dashboard.frequentErrors")}>
        {isLoading ? (
          <p className="hint">{t("common.loading")}</p>
        ) : frequentErrors.length === 0 ? (
          <p className="hint">{t("dashboard.frequentErrorsEmpty")}</p>
        ) : (
          <details className="collapsible">
            <summary
              className="collapsible-summary"
              style={{ cursor: "pointer", listStyle: "none", userSelect: "none" }}
            >
              <ChevronRight size={16} aria-hidden="true" />
              <span>{t("dashboard.frequentErrorsSummary", { count: frequentErrors.length })}</span>
            </summary>
            <ol style={{ margin: "12px 0 0", paddingLeft: 24 }}>
              {frequentErrors.map((error) => (
                <li key={error.ruleCode} style={{ padding: "8px 0 8px 4px" }}>
                  <div className="row" style={{ alignItems: "flex-start" }}>
                    <div className="grow" style={{ minWidth: 0 }}>
                      <div className="row" style={{ gap: 8 }}>
                        <strong
                          title={error.ruleCode}
                          style={{ overflow: "hidden", textOverflow: "ellipsis" }}
                        >
                          {error.ruleCode}
                        </strong>
                        <SeverityBadge severity={error.severity} />
                      </div>
                      <div style={{ color: "var(--fg-dim)", overflowWrap: "anywhere" }}>
                        {error.message}
                      </div>
                    </div>
                    <span className="label" style={{ whiteSpace: "nowrap" }}>
                      {error.count}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          </details>
        )}
      </Card>

      <RejectionsSummaryCard />
    </div>
  );
}

function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <article className="card">
      <h2 className="card-title">{title}</h2>
      {children}
    </article>
  );
}

function Kpi({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: KpiTone;
}): JSX.Element {
  return (
    <div className="kpi">
      <span className="label">{label}</span>
      <div className={["kpi-value", KPI_TONE[tone]].filter(Boolean).join(" ")}>
        {value}
      </div>
    </div>
  );
}

function BarList({
  rows,
  max,
  loading,
}: {
  rows: BarRow[];
  max: number;
  loading: boolean;
}): JSX.Element {
  const { t } = useTranslation();
  if (loading) return <p className="hint">{t("common.loading")}</p>;
  if (rows.length === 0) return <p className="hint">·</p>;
  const m = Math.max(1, max);
  return (
    <div className="form">
      {rows.map((r, i) => (
        <div key={`${r.label}-${i}`} className="bar-list-row">
          <span className="label dashboard-bar-label" title={r.label}>
            {r.label}
          </span>
          <div className="dashboard-bar-track">
            <div
              className="dashboard-bar-fill"
              style={{ background: r.fill, width: `${(r.count / m) * 100}%` }}
            />
          </div>
          <span className="label dashboard-bar-count">
            {r.count}
          </span>
        </div>
      ))}
    </div>
  );
}
