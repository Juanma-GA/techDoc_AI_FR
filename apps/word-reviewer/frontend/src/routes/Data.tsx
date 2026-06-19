import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { adminApi, type MetricsDto, type StatsDto } from "../lib/api";

function ConfirmButton({
  label,
  variant,
  onConfirm,
}: {
  label: string;
  variant: "danger" | "secondary";
  onConfirm: () => void;
}) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  return (
    <button
      type="button"
      className={`btn ${armed ? "danger" : variant}`}
      onClick={() => {
        if (!armed) {
          setArmed(true);
          timer.current = setTimeout(() => setArmed(false), 3000);
          return;
        }
        if (timer.current) clearTimeout(timer.current);
        setArmed(false);
        onConfirm();
      }}
    >
      {armed ? "Cliquer encore pour confirmer" : label}
    </button>
  );
}

export function Data() {
  const qc = useQueryClient();
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );
  const statsQuery = useQuery<StatsDto>({ queryKey: ["wr-stats"], queryFn: adminApi.stats });
  const metricsQuery = useQuery<MetricsDto>({ queryKey: ["wr-metrics"], queryFn: adminApi.metrics });
  const stats = statsQuery.data;
  const metrics = metricsQuery.data?.rules ?? [];

  const reset = async (scope: "all" | "rules") => {
    try {
      await adminApi.reset(scope);
      setFeedback({ kind: "ok", text: scope === "all" ? "Reset OK." : "Règles supprimées." });
      void qc.invalidateQueries({ queryKey: ["wr-stats"] });
      void qc.invalidateQueries({ queryKey: ["wr-metrics"] });
    } catch (e) {
      setFeedback({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Données</h1>
        <p>Statistiques, métriques par règle et reset.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Vue d'ensemble</h2>
        {stats ? (
          <div className="kpi-grid">
            <div className="kpi"><div className="label">Documents</div><div className="kpi-value info">{stats.documents}</div></div>
            <div className="kpi"><div className="label">Lots</div><div className="kpi-value info">{stats.batches}</div></div>
            <div className="kpi"><div className="label">Suggestions</div><div className="kpi-value">{stats.suggestions}</div></div>
            <div className="kpi"><div className="label">Règles</div><div className="kpi-value">{stats.rules}</div></div>
            <div className="kpi"><div className="label">Standards</div><div className="kpi-value ok">{stats.standards}</div></div>
          </div>
        ) : (
          <div className="empty-state">-</div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">Métriques par règle</h2>
        {metrics.length ? (
          <table className="tbl">
            <thead>
              <tr>
                <th>Rule</th>
                <th>Total</th>
                <th>Acc.</th>
                <th>Rej.</th>
                <th>Taux</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((r) => (
                <tr key={r.rule_code}>
                  <td className="mono">{r.rule_code}</td>
                  <td>{r.total}</td>
                  <td>{r.accepted}</td>
                  <td>{r.rejected}</td>
                  <td>{(r.acceptance_rate * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">-</div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">Reset</h2>
        <div className="banner warn">
          Opération <strong>irréversible</strong>. La config Mistral et les standards
          builtin sont préservés.
        </div>
        <div className="row">
          <ConfirmButton label="Tout supprimer" variant="danger" onConfirm={() => void reset("all")} />
          <ConfirmButton label="Supprimer les règles" variant="secondary" onConfirm={() => void reset("rules")} />
        </div>
        {feedback ? (
          <div className={feedback.kind === "ok" ? "success" : "error"}>{feedback.text}</div>
        ) : null}
      </div>
    </>
  );
}
