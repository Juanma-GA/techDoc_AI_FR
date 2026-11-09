import { AppShell } from "@internal/techdoc-brand";

import {
  DemoModeBadge,
  DemoModeProvider,
  ErrorBoundary,
  LanguageSwitcher,
  LlmStatus,
  SidebarNavContent,
  Spinner,
  sidebarNavItemClass,
} from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";

import { useHealth } from "./hooks/useHealth";
import { settingsApi } from "./lib/api";

const Editor = lazy(() => import("./routes/Editor").then((m) => ({ default: m.Editor })));
const Data = lazy(() => import("./routes/Data").then((m) => ({ default: m.Data })));
const Settings = lazy(() => import("./routes/Settings").then((m) => ({ default: m.Settings })));

const NAV = [
  { to: "/editor", key: "nav.editor", icon: "editor" },
  { to: "/data", key: "nav.data", icon: "data" },
  { to: "/settings", key: "nav.settings", icon: "settings" },
] as const;
const LANGUAGES = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLanguage = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: settingsApi.read });
  const healthQuery = useHealth();
  const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

  return (
    <AppShell
      title={t("app.title")}
      brandTitle={t("app.description")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
      sidebarTop={demoEnabled ? <DemoModeBadge label={t("demo.badge")} /> : null}
      navigation={
        <>
          {NAV.map(({ to, key, icon }) => {
            const label = t(key);
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
      <DemoModeProvider mode={demoEnabled ? "demo" : "normal"} isReady={settingsQuery.isSuccess}>
        <ErrorBoundary>
          <Suspense fallback={<Spinner />}>
            <Routes>
              <Route path="/" element={<Navigate to="/editor" replace />} />
              <Route path="/editor" element={<Editor />} />
              <Route path="/data" element={<Data />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/editor" replace />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </DemoModeProvider>
    </AppShell>
  );
}
