import {
  BookOpen,
  FileText,
  Settings as SettingsIcon,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

type NavItem = { to: string; icon: LucideIcon; labelKey: string };

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { to: "/", icon: FileText, labelKey: "nav.documents" },
  { to: "/standards", icon: BookOpen, labelKey: "nav.standards" },
  { to: "/rules", icon: SlidersHorizontal, labelKey: "nav.rules" },
  { to: "/settings", icon: SettingsIcon, labelKey: "nav.settings" },
];

export function Sidebar() {
  const { t } = useTranslation();
  return (
    <aside
      aria-label={t("nav.section")}
      className="flex w-sidebar-w shrink-0 flex-col border-r bg-bg-2"
    >
      <header className="flex items-baseline gap-2 border-b px-4 py-4">
        <span className="font-display text-lg text-brand-blue-light">{t("app.title")}</span>
        <span className="label">{t("app.version")}</span>
      </header>
      <nav className="flex flex-col gap-1 p-3">
        {NAV_ITEMS.map(({ to, icon: Icon, labelKey }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 rounded-sm px-3 py-2 transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue-light",
                isActive
                  ? "bg-brand text-fg"
                  : "text-fg-dim hover:bg-card-hover hover:text-fg",
              ].join(" ")
            }
          >
            <Icon size={16} aria-hidden="true" />
            <span>{t(labelKey)}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
