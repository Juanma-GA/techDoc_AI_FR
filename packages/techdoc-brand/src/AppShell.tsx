import { AppShell as SharedAppShell, type AppShellProps } from "@internal/ui";

import { Ai4TechDocLogo } from "./Ai4TechDocLogo";

export type { AppShellProps } from "@internal/ui";

export function AppShell({ brand, ...props }: AppShellProps) {
  return (
    <SharedAppShell
      {...props}
      brand={brand === undefined ? <Ai4TechDocLogo alt="" /> : brand}
    />
  );
}
