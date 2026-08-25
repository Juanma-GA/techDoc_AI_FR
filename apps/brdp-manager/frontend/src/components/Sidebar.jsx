import { useTranslation } from 'react-i18next';
import i18n from '../i18n';
import ThemeToggleButton from './ThemeToggleButton';
import LlmBadge from './LlmBadge';

const LANGS = ['fr', 'en'];

/**
 * Sidebar navigation — shell.css golden classes (rule #13 min tabs Home /
 * Architecture / Data / Settings), plus this app's own "BRDP Records" tab.
 * @param {Object} props
 * @param {string} props.currentPage
 * @param {Function} props.onNavigate
 */
export default function Sidebar({ currentPage, onNavigate }) {
  const { t } = useTranslation();
  const currentLang = (i18n.resolvedLanguage ?? i18n.language ?? 'fr').slice(0, 2);

  const navItems = [
    { key: 'home', labelKey: 'nav.home' },
    { key: 'brdp', labelKey: 'nav.brdp' },
    { key: 'data', labelKey: 'nav.data' },
    { key: 'settings', labelKey: 'nav.settings' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="brand">{t('app.title')}</span>
        <span className="label">v{t('app.version')}</span>
        <ThemeToggleButton />
      </div>

      <LlmBadge />

      <nav>
        {navItems.map(({ key, labelKey }) => (
          <button
            key={key}
            type="button"
            onClick={() => onNavigate(key)}
            className={currentPage === key ? 'nav-item active' : 'nav-item'}
          >
            {t(labelKey)}
          </button>
        ))}
      </nav>

      <div className="lang-switch" role="group" aria-label="Language">
        {LANGS.map((lng) => (
          <button
            key={lng}
            type="button"
            className={currentLang === lng ? 'lang-btn active' : 'lang-btn'}
            onClick={() => void i18n.changeLanguage(lng)}
          >
            {lng.toUpperCase()}
          </button>
        ))}
      </div>
    </aside>
  );
}
