import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "../lib/utils";

/**
 * Toggle between dark and light themes. Adds/removes `.dark` class on
 * <html> and persists the choice in `localStorage["theme"]`. Place once
 * in the app shell (topbar, right side). The anti-flash snippet in
 * `index.html` ensures the right theme is applied before React mounts.
 */

type Theme = "dark" | "light";

function readInitialTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  localStorage.setItem("theme", theme);
}

export type ThemeToggleProps = {
  className?: string;
  "aria-label"?: string;
};

export function ThemeToggle({ className, ...rest }: ThemeToggleProps) {
  const [theme, setTheme] = useState<Theme>(readInitialTheme);

  useEffect(() => {
    setTheme(readInitialTheme());
  }, []);

  const next: Theme = theme === "dark" ? "light" : "dark";
  const Icon = theme === "dark" ? Sun : Moon;

  return (
    <button
      type="button"
      aria-label={rest["aria-label"] ?? `Switch to ${next} theme`}
      onClick={() => {
        applyTheme(next);
        setTheme(next);
      }}
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-sm",
        "text-fg-dim transition-colors hover:bg-card-hover hover:text-fg",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue-light",
        className,
      )}
    >
      <Icon size={16} aria-hidden="true" />
    </button>
  );
}
