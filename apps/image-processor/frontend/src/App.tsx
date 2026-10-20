import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Ai4TechDocLogo,
  AppShell,
  DemoModeBadge,
  DemoModeProvider,
  ErrorBoundary,
  LanguageSwitcher,
  sidebarNavItemClass,
} from "@internal/ui";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { settingsApi, type SettingsDto } from "./lib/api";
import { Home } from "./routes/Home";
import { History } from "./routes/History";
import { WorkflowProvider } from "./hooks/WorkflowProvider";
import { Settings } from "./routes/Settings";

const LANGUAGES = ["fr", "en"] as const;

declare global {
  interface Window {
    __TAURI__?: {
      window?: {
        getCurrentWindow?: () => {
          setTheme: (theme: "dark" | "light") => Promise<void>;
        };
      };
    };
  }
}

export function App() {
  useEffect(() => {
    const tauri = window.__TAURI__;
    if (!tauri) {
      if ("__TAURI_INTERNALS__" in window) {
        console.error("Tauri window API is unavailable; check withGlobalTauri.");
      }
      return;
    }

    const nativeWindow = tauri.window?.getCurrentWindow?.();
    if (!nativeWindow) {
      console.error("Tauri window API is unavailable; check withGlobalTauri.");
      return;
    }

    const syncTheme = () => {
      const theme = document.documentElement.classList.contains("dark") ? "dark" : "light";
      void nativeWindow.setTheme(theme).catch((error: unknown) => {
        console.error("Unable to synchronize desktop window theme:", error);
      });
    };
    const observer = new MutationObserver(syncTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    syncTheme();

    return () => observer.disconnect();
  }, []);

  const { t, i18n } = useTranslation();
  const currentLanguage = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);
  const settingsQuery = useQuery<SettingsDto>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });
  const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

  return (
    <AppShell
      className="[&>.ui-sidebar]:shrink-0"
      title={t("app.title")}
      brandTitle={t("app.description")}
      version={t("app.version")}
      headerStart={<Ai4TechDocLogo alt="" />}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      sidebarTop={
        demoEnabled ? (
          <div className="border-b border-md px-4 py-2">
            <DemoModeBadge label={t("demo.badge")} />
          </div>
        ) : null
      }
      navigation={
        <>
          <NavLink to="/" end className={({ isActive }) => sidebarNavItemClass(isActive)}>
            {t("nav.home")}
          </NavLink>
          <NavLink to="/history" className={({ isActive }) => sidebarNavItemClass(isActive)}>
            {t("nav.history")}
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
          onLanguageChange={(language) => void i18n.changeLanguage(language)}
          ariaLabel={t("nav.languageSwitcher")}
        />
      }
    >
      <DemoModeProvider
        mode={demoEnabled ? "demo" : "normal"}
        isReady={settingsQuery.isSuccess}
      >
        <ErrorBoundary>
          <WorkflowProvider>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/history" element={<History />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </WorkflowProvider>
        </ErrorBoundary>
      </DemoModeProvider>
    </AppShell>
  );
}
