import {
  AppShell,
  ErrorBoundary,
  LanguageSwitcher,
  SidebarNavContent,
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
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
      navigation={
        <>
          <NavLink
            to="/"
            end
            title={t("nav.home")}
            aria-label={t("nav.home")}
            className={({ isActive }) => sidebarNavItemClass(isActive)}
          >
            <SidebarNavContent icon="home" label={t("nav.home")} />
          </NavLink>
          <NavLink
            to="/settings"
            title={t("nav.settings")}
            aria-label={t("nav.settings")}
            className={({ isActive }) => sidebarNavItemClass(isActive)}
          >
            <SidebarNavContent icon="settings" label={t("nav.settings")} />
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
                onClearTrackerResult={() => setLastTrackerResult(null)}
              />
            }
          />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </ErrorBoundary>
    </AppShell>
  );
}
