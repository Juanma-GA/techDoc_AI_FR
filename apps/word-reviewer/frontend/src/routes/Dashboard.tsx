import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { adminApi, documentsApi, type DashboardDto } from "../lib/api";

function Bars({ data, sev }: { data: Record<string, number>; sev?: boolean }) {
  const entries = Object.entries(data || {});
  if (!entries.length) return <div className="empty-state">-</div>;
  const max = Math.max(1, ...entries.map(([, v]) => v));
  const cls = (k: string) =>
    sev ? ({ error: "error", warning: "warn", info: "info" }[k] ?? "") : "";
  return (
    <>
      {entries.map(([k, v]) => (
        <div className="bar-row" key={k}>
          <span className="bar-label">{k}</span>
          <span className="bar-track">
            <span
              className={`bar-fill ${cls(k)}`}
              style={{ width: `${v > 0 ? Math.max(4, (v / max) * 100) : 0}%` }}
            />
          </span>
          <span className="bar-val">{v}</span>
        </div>
      ))}
    </>
  );
}

// Bouton corbeille (icône) à double-clic.
function TrashBtn({ onConfirm }: { onConfirm: () => void }) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  return (
    <button
      type="button"
      className={`icon-btn${armed ? " armed" : ""}`}
      title={armed ? "Cliquer encore pour confirmer" : "Supprimer"}
      onClick={(e) => {
        e.stopPropagation();
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
      🗑
    </button>
  );
}

export function Dashboard() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data } = useQuery<DashboardDto>({
    queryKey: ["dashboard"],
    queryFn: adminApi.dashboard,
  });
  const del = useMutation({
    mutationFn: (id: string) => documentsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard"] }),
  });

  const st = data?.by_status ?? {};
  const kpi = (label: string, val: number, cls: string) => (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className={`kpi-value ${cls}`}>{val}</div>
    </div>
  );

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Vue d'ensemble des documents et anomalies.</p>
      </div>

      {!data ? (
        <div className="card">
          <div className="empty-state">-</div>
        </div>
      ) : (
        <>
          <div className="card">
            <div className="kpi-grid">
              {kpi("Documents", data.documents, "info")}
              {kpi("Ouvertes", st.open || 0, "warn")}
              {kpi("Appliquées", (st.applied || 0) + (st.edited || 0), "ok")}
              {kpi("Rejetées", st.rejected || 0, "err")}
            </div>
          </div>
          <div className="grid-2">
            <div className="card">
              <h2 className="card-title">Par sévérité</h2>
              <Bars data={data.by_severity} sev />
            </div>
            <div className="card">
              <h2 className="card-title">Par règle</h2>
              <Bars data={data.by_kind} />
            </div>
          </div>
          <div className="card">
            <h2 className="card-title">Documents les plus signalés</h2>
            {(data.top_documents || []).length === 0 ? (
              <div className="empty-state">-</div>
            ) : (
              data.top_documents.map((td) => (
                <div
                  className="top-doc"
                  key={td.id}
                  onClick={() => navigate(`/review/${td.id}`)}
                >
                  <span className="grow">{td.original_filename}</span>
                  <span className="badge warn">{td.open_count}</span>
                  <TrashBtn onConfirm={() => del.mutate(td.id)} />
                </div>
              ))
            )}
          </div>
        </>
      )}
    </>
  );
}
