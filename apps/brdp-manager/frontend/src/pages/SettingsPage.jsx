import { useBRDPContext } from '../context/BRDPContext';
import AIConfigSection from '../components/AIConfigSection';
import ProjectConfigSection from '../components/ProjectConfigSection';
import AboutSection from '../components/AboutSection';
import styles from './SettingsPage.module.css';

/**
 * Settings Page component
 * Manages AI configuration, project metadata, and displays app information.
 * Data import/export/reset lives in the "Données" tab (rule #13).
 * @param {Object} props - Component props
 * @param {Function} props.showToast - Callback to show toast notifications
 * @returns {JSX.Element} Settings page with configuration sections
 */
export default function SettingsPage({ showToast }) {
  const { brdps } = useBRDPContext();
  void brdps;
  void showToast;

  return (
    <div className={styles.container}>
      <div className="page-header">
        <h1>Settings</h1>
        <p>Clé API Mistral, modèles utilisés, et métadonnées du projet S1000D.</p>
      </div>

      <div className={styles.settingsGrid}>
        <AIConfigSection />

        <ProjectConfigSection />

        <AboutSection />
      </div>
    </div>
  );
}
