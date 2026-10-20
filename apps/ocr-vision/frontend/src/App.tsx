import {
  AppShell,
  ErrorBoundary,
  LanguageSwitcher,
  SidebarNavContent,
  sidebarNavItemClass,
} from "@internal/ui";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import { Architecture } from "./routes/Architecture";
import { Data } from "./routes/Data";
import { Extraction } from "./routes/Extraction";
import { Home } from "./routes/Home";
import { Ocr } from "./routes/Ocr";
import { Settings } from "./routes/Settings";
import { Templates } from "./routes/Templates";

const navItems = [
  { to: "/", labelKey: "nav.ocr", icon: "scan" },
  { to: "/extraction", labelKey: "nav.extraction", icon: "file" },
  { to: "/templates", labelKey: "nav.templates", icon: "templates" },
  { to: "/data", labelKey: "nav.data", icon: "data" },
  { to: "/settings", labelKey: "nav.settings", icon: "settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.language || "fr").slice(0, 2);

  return (
    <ErrorBoundary>
    <AppShell
      className="dw"
      title={t("app.title")}
      brandTitle={t("app.description")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
      llmStatus={<LlmBadge />}
      navigation={navItems.map(({ to, labelKey, icon }) => {
        const label = t(labelKey);
        return (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
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
      <Routes>
        <Route path="/" element={<Ocr />} />
        <Route path="/extraction" element={<Extraction />} />
        <Route path="/templates" element={<Templates />} />
        <Route path="/home" element={<Home />} />
        <Route path="/architecture" element={<Architecture />} />
        <Route path="/data" element={<Data />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </AppShell>
    </ErrorBoundary>
  );
}
