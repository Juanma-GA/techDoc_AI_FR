import {
  AppShell,
  ErrorBoundary,
  LanguageSwitcher,
  sidebarNavItemClass,
} from "@internal/ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import type { AppendTrackerDto, CreateFoldersDto } from "./lib/api";
import { Home } from "./routes/Home";
import { Settings } from "./routes/Settings";

const LANGUAGES = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLanguage = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);
  const [lastFolderResult, setLastFolderResult] = useState<CreateFoldersDto | null>(null);
  const [lastTrackerResult, setLastTrackerResult] = useState<AppendTrackerDto | null>(null);

  return (
    <AppShell
      className="ecm"
      title={t("app.title")}
      brandTitle={t("app.description")}
      version={t("app.version")}
      navigationLabel={t("app.navigation")}
      navigation={
        <>
          <NavLink to="/" end className={({ isActive }) => sidebarNavItemClass(isActive)}>
            {t("nav.home")}
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => sidebarNavItemClass(isActive)}>
            {t("nav.settings")}
          </NavLink>
        </>
      }
      languageSwitcher={
        <LanguageSwitcher
          languages={LANGUAGES}
          currentLanguage={currentLanguage}
          ariaLabel={t("app.language")}
          onLanguageChange={(language) => void i18n.changeLanguage(language)}
        />
      }
    >
      <ErrorBoundary>
        <Routes>
          <Route
            path="/"
            element={
              <Home
                folderResult={lastFolderResult}
                trackerResult={lastTrackerResult}
                onFoldersCreated={setLastFolderResult}
                onTrackerUpdated={setLastTrackerResult}
                onClearResults={() => {
                  setLastFolderResult(null);
                  setLastTrackerResult(null);
                }}
                onClearFolderResult={() => setLastFolderResult(null)}
              />
            }
          />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </ErrorBoundary>
    </AppShell>
  );
}
