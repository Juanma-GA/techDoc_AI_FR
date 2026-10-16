import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export type ThemeToggleProps = {
  className?: string;
  "aria-label"?: string;
};

type Theme = "dark" | "light";

function readInitialTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  localStorage.setItem("theme", theme);
  document
    .querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    ?.setAttribute("content", theme === "dark" ? "#0e1117" : "#ffffff");
}

export function ThemeToggle({ className = "", ...rest }: ThemeToggleProps) {
  const [theme, setTheme] = useState<Theme>(readInitialTheme);
  const next: Theme = theme === "dark" ? "light" : "dark";
  const Icon = theme === "dark" ? Sun : Moon;

  useEffect(() => {
    setTheme(readInitialTheme());
  }, []);

  return (
    <button
      type="button"
      aria-label={rest["aria-label"] ?? `Switch to ${next} theme`}
      onClick={() => {
        applyTheme(next);
        setTheme(next);
      }}
      className={`ui-theme-toggle ${className}`.trim()}
    >
      <Icon size={16} aria-hidden="true" />
    </button>
  );
}
