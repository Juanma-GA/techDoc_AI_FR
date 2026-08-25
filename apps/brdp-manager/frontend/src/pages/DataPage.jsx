import { useState, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useBRDPContext } from '../context/BRDPContext';
import { fetchAdminStats, resetAllData } from '../services/api';

/**
 * Double-click-to-confirm button (rule #13) — same pattern as every other
 * ATEXIS POC's "Données" tab (see e.g. s1000d-extractor/frontend/src/routes/Data.tsx).
 */
function ConfirmButton({ label, onConfirm, variant = 'danger' }) {
  const [armed, setArmed] = useState(false);
  const timer = useRef(null);

  return (
    <button
      type="button"
      className={`btn ${variant}`}
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
      {armed ? 'Click again to confirm' : label}
    </button>
  );
}

/**
 * "Données" tab (STANDARD_POC.md rule #13/#14) — overview KPIs + reset only.
 * Import/export live on the BRDP Records page (see ImportSection.jsx).
 */
export default function DataPage() {
  const qc = useQueryClient();
  const { resetToMock } = useBRDPContext();
  const [feedback, setFeedback] = useState(null);

  const statsQuery = useQuery({ queryKey: ['admin', 'stats'], queryFn: fetchAdminStats });
  const stats = statsQuery.data;

  const handleDeleteAll = async () => {
    try {
      const result = await resetAllData();
      const items = Object.entries(result.deleted ?? {}).map(([k, v]) => `${k}: ${v}`).join(', ') || '(rien à supprimer)';
      setFeedback({ kind: 'ok', text: `Reset OK (${items}).` });
      void qc.invalidateQueries({ queryKey: ['admin', 'stats'] });
    } catch (err) {
      setFeedback({ kind: 'error', text: err.message || 'Reset failed.' });
    }
  };

  const handleResetDemo = async () => {
    try {
      await resetToMock();
      setFeedback({ kind: 'ok', text: 'Reset to demo data.' });
      void qc.invalidateQueries({ queryKey: ['admin', 'stats'] });
    } catch (err) {
      setFeedback({ kind: 'error', text: err.message || 'Reset failed.' });
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Data</h1>
        <p>Overview and reset operations.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Overview</h2>
        {stats ? (
          <div className="kpi-grid">
            <div className="kpi">
              <div className="label">Total</div>
              <div className="kpi-value info">{stats.total}</div>
            </div>
            <div className="kpi">
              <div className="label">Validated</div>
              <div className="kpi-value ok">{stats.validated}</div>
            </div>
            <div className="kpi">
              <div className="label">Refused</div>
              <div className="kpi-value err">{stats.refused}</div>
            </div>
            <div className="kpi">
              <div className="label">Pending</div>
              <div className="kpi-value warn">{stats.pending}</div>
            </div>
          </div>
        ) : (
          <div className="empty-state">Stats unavailable.</div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">Reset</h2>
        <div className="banner warn">
          Operation is <strong>irreversible</strong>. The Mistral configuration
          (<code>app_config</code>) and project configuration are preserved.
        </div>
        <div className="row">
          <ConfirmButton label="Reset to demo data" onConfirm={handleResetDemo} variant="secondary" />
          <ConfirmButton label="Delete all BRDPs" onConfirm={handleDeleteAll} variant="danger" />
        </div>
        {feedback && (
          <div className={feedback.kind === 'ok' ? 'success' : 'error'}>{feedback.text}</div>
        )}
      </div>
    </>
  );
}
