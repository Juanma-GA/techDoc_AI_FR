import { ErrorBoundary } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
import i18n from "./i18n";
import { Checks } from "./routes/Checks";
import { Colorization } from "./routes/Colorization";
import { Conversion } from "./routes/Conversion";
import { Data } from "./routes/Data";
import { Diff } from "./routes/Diff";
import { Export } from "./routes/Export";
import { Identification } from "./routes/Identification";
import { Qc } from "./routes/Qc";
import { Replacement } from "./routes/Replacement";
import { Settings } from "./routes/Settings";
import { SmgxmlRecolor } from "./routes/SmgxmlRecolor";
import { SmgxmlRename } from "./routes/SmgxmlRename";
import { Suggestions } from "./routes/Suggestions";
import { Tree } from "./routes/Tree";

type NavLeaf = { to: string; labelKey: string; end?: boolean };
type NavGroup = { groupKey: string; items: NavLeaf[] };
type NavEntry = NavLeaf | NavGroup;

const isGroup = (e: NavEntry): e is NavGroup => "groupKey" in e;

/** Navigation groupee, ordre et libelles fideles au preview (lignes 176-206). */
const NAV: NavEntry[] = [
  {
    groupKey: "nav.groups.identification",
    items: [
      { to: "/identification", labelKey: "nav.identification" },
      { to: "/diff", labelKey: "nav.diff" },
    ],
  },
  {
    groupKey: "nav.groups.preparation",
    items: [{ to: "/conversion", labelKey: "nav.conversion" }],
  },
  {
    groupKey: "nav.groups.traitement",
    items: [
      { to: "/smgxml-recolor", labelKey: "nav.smgxmlRecolor" },
      { to: "/colorization", labelKey: "nav.colorization" },
      { to: "/tree", labelKey: "nav.tree" },
      { to: "/suggestions", labelKey: "nav.suggestions" },
      { to: "/export", labelKey: "nav.export" },
    ],
  },
  {
    groupKey: "nav.groups.integration",
    items: [
      { to: "/smgxml-rename", labelKey: "nav.smgxmlRename" },
      { to: "/replacement", labelKey: "nav.replacement" },
    ],
  },
  {
    groupKey: "nav.groups.controle",
    items: [
      { to: "/qc", labelKey: "nav.qc" },
      { to: "/checks", labelKey: "nav.checks" },
    ],
  },
  {
    groupKey: "nav.groups.outils",
    items: [
      { to: "/data", labelKey: "nav.data" },
      { to: "/settings", labelKey: "nav.settings" },
    ],
  },
];

/** Titre + sous-titre par route (entete centralise du main). */
export const ROUTE_META: Record<string, { titleKey: string; subKey: string }> = {
  "/identification": { titleKey: "page.identification.title", subKey: "page.identification.sub" },
  "/diff": { titleKey: "page.diff.title", subKey: "page.diff.sub" },
  "/conversion": { titleKey: "page.conversion.title", subKey: "page.conversion.sub" },
  "/smgxml-recolor": { titleKey: "page.smgxmlRecolor.title", subKey: "page.smgxmlRecolor.sub" },
  "/colorization": { titleKey: "page.colorization.title", subKey: "page.colorization.sub" },
  "/tree": { titleKey: "page.tree.title", subKey: "page.tree.sub" },
  "/suggestions": { titleKey: "page.suggestions.title", subKey: "page.suggestions.sub" },
  "/export": { titleKey: "page.export.title", subKey: "page.export.sub" },
  "/smgxml-rename": { titleKey: "page.smgxmlRename.title", subKey: "page.smgxmlRename.sub" },
  "/replacement": { titleKey: "page.replacement.title", subKey: "page.replacement.sub" },
  "/qc": { titleKey: "page.qc.title", subKey: "page.qc.sub" },
  "/checks": { titleKey: "page.checks.title", subKey: "page.checks.sub" },
  "/data": { titleKey: "page.data.title", subKey: "page.data.sub" },
  "/settings": { titleKey: "page.settings.title", subKey: "page.settings.sub" },
};

const navItemClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? "nav-item active" : "nav-item";

export function App() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const meta = ROUTE_META[pathname] ?? ROUTE_META["/identification"]!;
  const lang = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);

  return (
    <div className="ct">
      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-header">
            <span className="brand" title={t("app.description")} style={{ cursor: "help" }}>
              {t("app.title")}
            </span>
            <span className="label">v{t("app.version")}</span>
            <ThemeToggleButton />
          </div>

          <LlmBadge />

          <nav>
            {NAV.map((entry) =>
              isGroup(entry) ? (
                <div key={entry.groupKey} className="nav-group">
                  <div className="nav-group-title">{t(entry.groupKey)}</div>
                  {entry.items.map((it) => (
                    <NavLink key={it.to} to={it.to} className={navItemClass}>
                      {t(it.labelKey)}
                    </NavLink>
                  ))}
                </div>
              ) : (
                <NavLink key={entry.to} to={entry.to} end={entry.end} className={navItemClass}>
                  {t(entry.labelKey)}
                </NavLink>
              ),
            )}
          </nav>

          <div className="lang-switch" role="group" aria-label="Language">
            {(["fr", "en"] as const).map((code) => (
              <button
                key={code}
                type="button"
                className={lang === code ? "lang-btn active" : "lang-btn"}
                onClick={() => void i18n.changeLanguage(code)}
              >
                {code.toUpperCase()}
              </button>
            ))}
          </div>
        </aside>

        <main>
          <div className="page-header">
            <h1>{t(meta.titleKey)}</h1>
            <p>{t(meta.subKey)}</p>
          </div>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Navigate to="/identification" replace />} />
              <Route path="/identification" element={<Identification />} />
              <Route path="/diff" element={<Diff />} />
              <Route path="/conversion" element={<Conversion />} />
              <Route path="/smgxml-recolor" element={<SmgxmlRecolor />} />
              <Route path="/colorization" element={<Colorization />} />
              <Route path="/tree" element={<Tree />} />
              <Route path="/suggestions" element={<Suggestions />} />
              <Route path="/export" element={<Export />} />
              <Route path="/smgxml-rename" element={<SmgxmlRename />} />
              <Route path="/replacement" element={<Replacement />} />
              <Route path="/qc" element={<Qc />} />
              <Route path="/checks" element={<Checks />} />
              <Route path="/data" element={<Data />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
