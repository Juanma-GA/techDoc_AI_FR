import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { adminApi, type AdminStatsDto } from "../lib/api";

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function ConfirmButton({
  label,
  onConfirm,
}: {
  label: string;
  onConfirm: () => void;
}) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  return (
    <button
      type="button"
      className="btn danger"
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
  const statsQuery = useQuery<AdminStatsDto>({
    queryKey: ["admin", "stats"],
    queryFn: adminApi.stats,
  });
  const stats = statsQuery.data;

  const reset = async (scope: "documents" | "all") => {
    try {
      // HR9: Generate a confirmation token for server-side deletion validation.
      const confirmToken = btoa(Math.random().toString()).substring(0, 16);
      const r = await adminApi.reset(scope, confirmToken);
      const items =
        Object.entries(r.deleted ?? {})
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ") || "(rien à supprimer)";
      setFeedback({ kind: "ok", text: `Reset OK (${items}).` });
      void qc.invalidateQueries({ queryKey: ["admin", "stats"] });
    } catch (e) {
      setFeedback({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Données</h1>
        <p>Vue d'ensemble et opérations de reset.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Vue d'ensemble</h2>
        {stats ? (
          <div className="kpi-grid">
            <div className="kpi">
              <div className="label">Documents</div>
              <div className="kpi-value info">{stats.documents}</div>
            </div>
            <div className="kpi">
              <div className="label">Extraits</div>
              <div className="kpi-value info">{stats.extracted}</div>
            </div>
            <div className="kpi">
              <div className="label">Profils BREX</div>
              <div className="kpi-value info">{stats.brex_profiles}</div>
            </div>
            <div className="kpi">
              <div className="label">Taille totale</div>
              <div className="kpi-value">{formatSize(stats.total_size_bytes)}</div>
            </div>
          </div>
        ) : (
          <div className="empty-state">Stats indisponibles.</div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">Réinitialiser</h2>
        <div className="banner warn">
          Opération <strong>irréversible</strong>. La configuration Mistral
          (<code>app_config</code>) et les profils BREX sont préservés.
        </div>
        <div className="row">
          <ConfirmButton
            label="Supprimer les documents"
            onConfirm={() => void reset("documents")}
          />
          <ConfirmButton label="Tout supprimer" onConfirm={() => void reset("all")} />
        </div>
        {feedback ? (
          <div className={feedback.kind === "ok" ? "success" : "error"}>
            {feedback.text}
          </div>
        ) : null}
      </div>
    </>
  );
}
