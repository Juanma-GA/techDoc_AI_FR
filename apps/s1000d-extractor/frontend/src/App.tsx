import { useQuery } from "@tanstack/react-query";
import {
  AppShell,
  DemoModeBadge,
  DemoModeProvider,
  LanguageSwitcher,
  SidebarNavContent,
  sidebarNavItemClass,
} from "@internal/ui";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";

import { settingsApi, type SettingsDto } from "./lib/api";
import { Data } from "./routes/Data";
import { Migration } from "./routes/Migration";
import { Settings } from "./routes/Settings";
import { Validation } from "./routes/Validation";
import { Versioning } from "./routes/Versioning";

const navItems = [
  { to: "/migration", labelKey: "nav.migration", icon: "migration" },
  { to: "/validation", labelKey: "nav.validation", icon: "quality" },
  { to: "/data", labelKey: "nav.data", icon: "data" },
  { to: "/settings", labelKey: "nav.settings", icon: "settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const currentLang = (i18n.language || "fr").slice(0, 2);
  const showMigration = location.pathname === "/migration";
  const settingsQuery = useQuery<SettingsDto>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });
  const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

  return (
    <AppShell
      className="dw"
      title={t("app.title")}
      brandTitle={t("app.description")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
      sidebarTop={
        demoEnabled ? (
          <div className="border-b border-md px-4 py-2">
            <DemoModeBadge label={t("demo.badge")} />
          </div>
        ) : null
      }
      navigation={navItems.map(({ to, labelKey, icon }) => {
        const label = t(labelKey);
        return (
          <NavLink
            key={to}
            to={to}
            title={label}
            aria-label={label}
            className={({ isActive }) => sidebarNavItemClass(isActive)}
          >
            <SidebarNavContent icon={icon} label={label} />
          </NavLink>
        );
      })}
      languageSwitcher={
        <LanguageSwitcher
          languages={LANGS}
          currentLanguage={currentLang}
          onLanguageChange={(language) => void i18n.changeLanguage(language)}
        />
      }
    >
      <DemoModeProvider
        key={demoEnabled ? "demo" : "normal"}
        mode={demoEnabled ? "demo" : "normal"}
        isReady={settingsQuery.isSuccess}
      >
        <div hidden={!showMigration}>
          <Migration />
        </div>
        <Routes>
          <Route path="/" element={<Navigate to="/migration" replace />} />
          <Route path="/data" element={<Data />} />
          <Route path="/validation" element={<Validation />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/versioning" element={<Versioning />} />
        </Routes>
      </DemoModeProvider>
    </AppShell>
  );
}
