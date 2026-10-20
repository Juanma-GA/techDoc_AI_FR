import { AppShell, ErrorBoundary, LanguageSwitcher, sidebarNavItemClass } from "@internal/ui";
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
  { to: "/", labelKey: "nav.ocr" },
  { to: "/extraction", labelKey: "nav.extraction" },
  { to: "/templates", labelKey: "nav.templates" },
  { to: "/data", labelKey: "nav.data" },
  { to: "/settings", labelKey: "nav.settings" },
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
      version={t("app.version")}
      llmStatus={<LlmBadge />}
      navigation={navItems.map(({ to, labelKey }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
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
