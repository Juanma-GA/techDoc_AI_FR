import { ThemeToggle } from "@internal/ui";
import {
  Boxes,
  Download,
  FolderTree,
  GitCompare,
  Home as HomeIcon,
  Palette,
  Replace,
  Settings as SettingsIcon,
  ShieldCheck,
  Upload,
  Wand2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { Checks } from "./routes/Checks";
import { Colorization } from "./routes/Colorization";
import { Conversion } from "./routes/Conversion";
import { Diff } from "./routes/Diff";
import { Export } from "./routes/Export";
import { Home } from "./routes/Home";
import { Import } from "./routes/Import";
import { Replacement } from "./routes/Replacement";
import { Settings } from "./routes/Settings";
import { Suggestions } from "./routes/Suggestions";
import { Tree } from "./routes/Tree";

const navItems = [
  { to: "/", labelKey: "nav.home", icon: HomeIcon },
  { to: "/import", labelKey: "nav.import", icon: Upload },
  { to: "/tree", labelKey: "nav.tree", icon: FolderTree },
  { to: "/suggestions", labelKey: "nav.suggestions", icon: Wand2 },
  { to: "/export", labelKey: "nav.export", icon: Download },
  { to: "/diff", labelKey: "nav.diff", icon: GitCompare },
  { to: "/checks", labelKey: "nav.checks", icon: ShieldCheck },
  { to: "/conversion", labelKey: "nav.conversion", icon: Boxes },
  { to: "/replacement", labelKey: "nav.replacement", icon: Replace },
  { to: "/colorization", labelKey: "nav.colorization", icon: Palette },
  { to: "/settings", labelKey: "nav.settings", icon: SettingsIcon },
] as const;

export function App() {
  const { t } = useTranslation();
  return (
    <div className="flex h-screen bg-bg font-sans text-base text-fg">
      <aside className="flex w-sidebar-w shrink-0 flex-col border-r bg-bg-2">
        <div className="flex h-topbar-h items-center px-4">
          <span className="font-display text-lg text-brand-blue-light">{t("app.title")}</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-2">
          {navItems.map(({ to, labelKey, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                [
                  "flex items-center gap-3 rounded-sm px-3 py-2 text-sm transition-colors",
                  isActive ? "bg-card text-fg" : "text-fg-dim hover:bg-card-hover hover:text-fg",
                ].join(" ")
              }
            >
              <Icon size={16} aria-hidden="true" />
              <span>{t(labelKey)}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-topbar-h items-center justify-end border-b px-4">
          <ThemeToggle />
        </header>
        <main className="flex-1 overflow-auto p-6">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/import" element={<Import />} />
              <Route path="/tree" element={<Tree />} />
              <Route path="/suggestions" element={<Suggestions />} />
              <Route path="/export" element={<Export />} />
              <Route path="/diff" element={<Diff />} />
              <Route path="/checks" element={<Checks />} />
              <Route path="/conversion" element={<Conversion />} />
              <Route path="/replacement" element={<Replacement />} />
              <Route path="/colorization" element={<Colorization />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
