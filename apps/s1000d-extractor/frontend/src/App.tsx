import { useQuery } from "@tanstack/react-query";
import {
  AppShell,
  DemoModeBadge,
  DemoModeProvider,
  LanguageSwitcher,
  SidebarNavContent,
  sidebarNavItemClass,
  Spinner,
  Button,
} from "@internal/ui";
import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";

import { settingsApi, type SettingsDto } from "./lib/api";
import { formatApiError } from "./lib/migrationUtils";
const Data = lazy(() => import("./routes/Data").then((module) => ({ default: module.Data })));
const Migration = lazy(() => import("./routes/Migration").then((module) => ({ default: module.Migration })));
const Settings = lazy(() => import("./routes/Settings").then((module) => ({ default: module.Settings })));
const Validation = lazy(() => import("./routes/Validation").then((module) => ({ default: module.Validation })));

const navItems = [
  { to: "/migration", labelKey: "nav.migration", icon: "migration" },
  { to: "/validation", labelKey: "nav.validation", icon: "quality" },
  { to: "/data", labelKey: "nav.data", icon: "data" },
  { to: "/settings", labelKey: "nav.settings", icon: "settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.language || "fr").slice(0, 2);
  const settingsQuery = useQuery<SettingsDto>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });
  const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

  return (
    <AppShell
      mainClassName="relative"
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
        {settingsQuery.error ? <div role="alert" className="space-y-2 text-danger">
          <p>{formatApiError(t, settingsQuery.error)}</p>
          <Button type="button" variant="secondary" onClick={() => void settingsQuery.refetch()}>
            {t("common.retry")}
          </Button>
        </div> : null}
        <Suspense fallback={<Spinner aria-label={t("common.loading")} />}>
        <Routes>
          <Route path="/" element={<Navigate to="/migration" replace />} />
          <Route path="/migration/:docId?" element={<Migration />} />
          <Route path="/data" element={<Data />} />
          <Route path="/validation" element={<Validation />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/migration" replace />} />
        </Routes>
        </Suspense>
      </DemoModeProvider>
    </AppShell>
  );
}
