import { useState } from 'react';
import { downloadReport } from '../../api/buildBREXdocReport';
import styles from './BREXdocModal.module.css';

export default function BREXdocModal({ brdps, projectConfig, onClose }) {
  const [format, setFormat] = useState('html');

  const total     = brdps.length;
  const validated = brdps.filter(b => b.validation === 'Validated').length;
  const refused   = brdps.filter(b => b.validation === 'Refused').length;
  const pending   = brdps.filter(b => b.validation === 'Pending').length;

  const handleDownload = () => {
    downloadReport(brdps, projectConfig, format);
    onClose();
  };

  return (
    <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>

        <div className={styles.header}>
          <div>
            <h2 className={styles.title}>Generate BREXdoc Report</h2>
            <span className={styles.subtitle}>Review closure document — all BRDPs included</span>
          </div>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div className={styles.content}>

          <div className={styles.statsRow}>
            <div className={styles.stat}>
              <span className={styles.statNum}>{total}</span>
              <span className={styles.statLbl}>Total</span>
            </div>
            <div className={`${styles.stat} ${styles.green}`}>
              <span className={styles.statNum}>{validated}</span>
              <span className={styles.statLbl}>Validated</span>
            </div>
            <div className={`${styles.stat} ${styles.red}`}>
              <span className={styles.statNum}>{refused}</span>
              <span className={styles.statLbl}>Refused</span>
            </div>
            <div className={`${styles.stat} ${styles.amber}`}>
              <span className={styles.statNum}>{pending}</span>
              <span className={styles.statLbl}>Pending</span>
            </div>
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Output format</label>
            <div className={styles.radioGroup}>
              <label className={styles.radioLabel}>
                <input type="radio" value="html" checked={format === 'html'} onChange={() => setFormat('html')} />
                HTML <span className={styles.hint}>— opens in browser, print to PDF</span>
              </label>
              <label className={styles.radioLabel}>
                <input type="radio" value="md" checked={format === 'md'} onChange={() => setFormat('md')} />
                Markdown <span className={styles.hint}>— plain text, Git-friendly</span>
              </label>
            </div>
          </div>

          <div className={styles.projectRow}>
            <span>Project: <strong>{projectConfig?.projectName || '—'}</strong></span>
            <span>Model: <strong>{projectConfig?.modelIdentCode || '—'}</strong></span>
          </div>

        </div>

        <div className={styles.footer}>
          <button className={styles.downloadBtn} onClick={handleDownload}>
            Download {format === 'html' ? '.html' : '.md'}
          </button>
        </div>

      </div>
    </div>
  );
}