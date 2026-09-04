import styles from './AboutSection.module.css';

/**
 * About section component
 * Displays application information and version
 * @returns {JSX.Element} About section with app details
 */
export default function AboutSection() {
  return (
    <div className={styles.section}>
      <h3 className={styles.title}>About</h3>

      <div className={styles.info}>
        <div className={styles.infoItem}>
          <label className={styles.label}>App Name</label>
          <p className={styles.value}>BRDP Manager</p>
        </div>

        <div className={styles.infoItem}>
          <label className={styles.label}>Version</label>
          <p className={styles.value}>1.0.0</p>
        </div>

        <div className={styles.infoItem}>
          <label className={styles.label}>Description</label>
          <p className={styles.value}>
            Business Rules Decision Points management tool for Technical Publication projects.
          </p>
        </div>
      </div>
    </div>
  );
}
