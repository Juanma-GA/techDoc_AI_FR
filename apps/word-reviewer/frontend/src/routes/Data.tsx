import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { adminApi, type StatsDto } from "../lib/api";

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
  const stats = statsQuery.data;

  const reset = async (scope: "all" | "rules") => {
    try {
      await adminApi.reset(scope);
      setFeedback({ kind: "ok", text: scope === "all" ? "Reset OK." : "Règles supprimées." });
      // Rafraichit les vues impactees : stats, dashboard, et la liste de regles /
      // standards de l'onglet "Standards & Regles" (sinon cache perime 30s).
      for (const key of [["wr-stats"], ["dashboard"], ["rules"], ["standards"], ["standard-detail"]]) {
        void qc.invalidateQueries({ queryKey: key });
      }
    } catch (e) {
      setFeedback({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Données</h1>
        <p>Statistiques et reset.</p>
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
