import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FileSearch } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { SeverityBadge } from "../components/SeverityBadge";
import { useClientRules } from "../hooks/useClientConfig";
import { useDocuments } from "../hooks/useDocuments";
import { api } from "../lib/api";
import { localizedRuleCode, localizedSuggestionMessage } from "../lib/suggestionText";
import type { Severity, Suggestion } from "../types/domain";

type KpiTone = "info" | "warn" | "danger";

const KPI_TONE: Record<KpiTone, string> = {
  info: "info",
  warn: "warn",
  danger: "err",
};

const SEV_FILL: Record<Severity, string> = {
  error: "var(--danger)",
  warning: "var(--warning)",
  info: "var(--info)",
};

type BarRow = { label: string; count: number; fill: string };

type FrequentError = {
  ruleCode: string;
  ruleNumber: number | null;
  message: string;
  severity: Severity;
  count: number;
};

export function Dashboard(): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const docs = useDocuments();
  const clientRules = useClientRules();
  const suggestions = useQuery({
    queryKey: ["suggestions", "all"],
    queryFn: () => api.get<Suggestion[]>("/suggestions"),
  });
  const ruleNumberByCode = new Map(
    (clientRules.data ?? []).map((rule) => [rule.code, rule.rule_number]),
  );

  const docList = docs.data ?? [];
  const sugList = suggestions.data ?? [];

  const isLoading = docs.isLoading || suggestions.isLoading;
  const error = docs.error ?? suggestions.error;

  const total = sugList.length;
  const proposed = sugList.filter((s) => s.status === "open").length;
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

  const errorsByRule = new Map<string, FrequentError>();
  for (const s of sugList) {
    const ruleCode = s.rule_code || "?";
    const existing = errorsByRule.get(ruleCode);
    if (existing) {
      existing.count += 1;
    } else {
      errorsByRule.set(ruleCode, {
        ruleCode,
        ruleNumber: ruleNumberByCode.get(ruleCode) ?? null,
        message: localizedSuggestionMessage(s, t) || localizedRuleCode(ruleCode, t),
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
      <PageHeader title={t("dashboard.title")} />

      <Card title={t("dashboard.kpis")}>
        {isLoading ? (
          <p className="hint">{t("common.loading")}</p>
        ) : error ? (
          <p className="error">{error.message}</p>
        ) : (
          <div className="kpi-grid">
            <Kpi label={t("dashboard.kpi.pdfs")} value={docList.length} tone="info" />
            <Kpi label={t("dashboard.kpi.open")} value={proposed} tone="warn" />
            <Kpi
              label={t("dashboard.kpi.rejected")}
              value={rejected}
              tone="danger"
              onClick={() => navigate("/rejections")}
            />
          </div>
        )}
      </Card>

      <div className="grid-2">
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
                          {error.ruleNumber != null ? (
                            <Link
                              className="badge default suggestion-rule-number"
                              to={`/rules?rule=${encodeURIComponent(error.ruleCode)}`}
                              title={t("rules.client.openRule", { number: error.ruleNumber })}
                              aria-label={t("rules.client.openRule", { number: error.ruleNumber })}
                            >
                              #{error.ruleNumber}
                            </Link>
                          ) : null}
                          <strong
                            title={localizedRuleCode(error.ruleCode, t)}
                            style={{ overflow: "hidden", textOverflow: "ellipsis" }}
                          >
                            {localizedRuleCode(error.ruleCode, t)}
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
        <Card title={t("dashboard.bySev")}>
          <BarList rows={sevBars} max={total} loading={isLoading} />
        </Card>
      </div>

      <div className="dashboard-cta-wrap">
        <button
          type="button"
          className="btn primary dashboard-cta"
          onClick={() => navigate("/documents", { state: { openUploadDialog: true } })}
        >
          <FileSearch size={18} aria-hidden="true" />
          {t("dashboard.analyzeDocument")}
        </button>
      </div>
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
  onClick,
}: {
  label: string;
  value: number;
  tone: KpiTone;
  onClick?: () => void;
}): JSX.Element {
  const content = (
    <>
      <span className="label">{label}</span>
      <span className={["kpi-value", KPI_TONE[tone]].filter(Boolean).join(" ")}>
        {value}
      </span>
    </>
  );

  return onClick ? (
    <button type="button" className="kpi kpi-clickable" onClick={onClick}>
      {content}
    </button>
  ) : (
    <div className="kpi">
      {content}
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
