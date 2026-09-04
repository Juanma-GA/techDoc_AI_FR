import { useBRDPContext } from '../context/BRDPContext';
import styles from './SettingsPage.module.css';

/**
 * "Home" tab (STANDARD_POC.md rule #13) — quick overview of the BRDP dataset.
 */
export default function HomePage({ onNavigate }) {
  const { stats } = useBRDPContext();

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>BRDP Manager</h2>
      <p>
        Manage Business Rules Decision Points for S1000D / DITA technical documentation
        projects: import, validate, generate BREX / Schematron, and get AI-assisted
        extraction and expert guidance.
      </p>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', margin: '16px 0' }}>
        <div>
          <strong>{stats.total}</strong> BRDPs total
        </div>
        <div>{stats.validated} validated</div>
        <div>{stats.refused} refused</div>
        <div>{stats.pending} pending</div>
      </div>

      <button type="button" onClick={() => onNavigate?.('brdp')}>
        Go to BRDP Records →
      </button>
    </div>
  );
}
