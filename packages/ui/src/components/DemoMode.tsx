import { createContext, useContext, type ReactNode } from "react";

import { Badge } from "./Badge";
import { Button } from "./Button";

export type DemoMode = "normal" | "demo";

export type DemoModeContextValue = {
  mode: DemoMode;
  isReady: boolean;
};

const DemoModeContext = createContext<DemoModeContextValue>({ mode: "normal", isReady: false });

export type DemoModeProviderProps = DemoModeContextValue & {
  children: ReactNode;
};

export function DemoModeProvider({ mode, isReady, children }: DemoModeProviderProps) {
  return (
    <DemoModeContext.Provider value={{ mode, isReady }}>{children}</DemoModeContext.Provider>
  );
}

export function useDemoMode(): DemoModeContextValue {
  return useContext(DemoModeContext);
}

export type DemoModeSelectorProps = {
  mode: DemoMode;
  labels: { normal: string; demo: string };
  ariaLabel: string;
  onModeChange: (mode: DemoMode) => void;
  disabled?: boolean;
};

export function DemoModeSelector({
  mode,
  labels,
  ariaLabel,
  onModeChange,
  disabled = false,
}: DemoModeSelectorProps) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={ariaLabel}>
      <Button
        variant={mode === "normal" ? "primary" : "secondary"}
        size="sm"
        aria-pressed={mode === "normal"}
        disabled={disabled}
        onClick={() => onModeChange("normal")}
      >
        {labels.normal}
      </Button>
      <Button
        variant={mode === "demo" ? "primary" : "secondary"}
        size="sm"
        aria-pressed={mode === "demo"}
        disabled={disabled}
        onClick={() => onModeChange("demo")}
      >
        {labels.demo}
      </Button>
    </div>
  );
}

export type DemoModeBadgeProps = {
  label: string;
  visible?: boolean;
};

export function DemoModeBadge({ label, visible = true }: DemoModeBadgeProps) {
  return visible ? (
    <Badge variant="info" role="status">
      {label}
    </Badge>
  ) : null;
}