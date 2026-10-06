import { AppShell, LanguageSwitcher, sidebarNavItemClass } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import { Data } from "./routes/Data";
import { Migration } from "./routes/Migration";
import { Settings } from "./routes/Settings";
import { Versioning } from "./routes/Versioning";

const navItems = [
  { to: "/migration", labelKey: "nav.migration" },
  { to: "/data", labelKey: "nav.data" },
  { to: "/settings", labelKey: "nav.settings" },
  { to: "/versioning", labelKey: "nav.versioning" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const currentLang = (i18n.language || "fr").slice(0, 2);
  const showMigration = location.pathname === "/migration";

  return (
    <AppShell
      className="dw"
      title={t("app.title")}
      brandTitle={t("app.description")}
      version={t("app.version")}
      llmStatus={<LlmBadge />}
      navigation={navItems.map(({ to, labelKey }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) => sidebarNavItemClass(isActive)}
        >
          {t(labelKey)}
        </NavLink>
      ))}
      languageSwitcher={
        <LanguageSwitcher
          languages={LANGS}
          currentLanguage={currentLang}
          onLanguageChange={(language) => void i18n.changeLanguage(language)}
        />
      }
    >
      <div hidden={!showMigration}>
        <Migration />
      </div>
      <Routes>
        <Route path="/" element={<Navigate to="/migration" replace />} />
        <Route path="/data" element={<Data />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/versioning" element={<Versioning />} />
      </Routes>
    </AppShell>
  );
}
