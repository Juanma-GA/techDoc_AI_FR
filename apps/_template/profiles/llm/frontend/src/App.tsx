import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  Ai4TechDocLogo,
  AppShell,
  DemoModeBadge,
  DemoModeProvider,
  ErrorBoundary,
  LanguageSwitcher,
  LlmStatus,
  SidebarNavContent,
  sidebarNavItemClass,
} from "@internal/ui";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { healthApi, settingsApi, type HealthDto, type SettingsDto } from "./lib/api";
import { Data } from "./routes/Data";
import { Home } from "./routes/Home";
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

const NAV_ITEMS = [
  { to: "/", key: "nav.home", icon: "home" },
  { to: "/data", key: "nav.data", icon: "data" },
  { to: "/settings", key: "nav.settings", icon: "settings" },
] as const;

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
  const appTitle = t("app.title");
  const currentLanguage = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);
  const healthQuery = useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.read,
    refetchInterval: 15_000,
  });
  const settingsQuery = useQuery<SettingsDto>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });
  const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

  useEffect(() => {
    document.title = appTitle;
  }, [appTitle]);

  return (
    <AppShell
      title={appTitle}
      brandTitle={t("app.description")}
      headerStart={<Ai4TechDocLogo alt="" />}
      navigationLabel={t("nav.ariaLabel")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
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
          {NAV_ITEMS.map(({ to, key, icon }) => {
            const label = t(key);

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
        </>
      }
      llmStatus={
        <LlmStatus
          status={healthQuery.data?.llm}
          labels={{
            label: t("llm.label"),
            title: t("llm.title"),
            on: t("llm.on"),
            off: t("llm.off"),
            untested: t("llm.untested"),
            noKey: t("llm.noKey"),
          }}
        />
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
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/data" element={<Data />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </ErrorBoundary>
      </DemoModeProvider>
    </AppShell>
  );
}
