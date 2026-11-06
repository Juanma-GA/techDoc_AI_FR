import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { useTranslation } from "react-i18next";
import {
  Card,
  CardContent,
  CardHeader,
  LoadingOverlay,
} from "@internal/ui";
import { Ai4TechDocLogo } from "@internal/techdoc-brand";

import "./i18n";
import "./index.css";

function DesktopStartup() {
  const { t } = useTranslation();

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6 py-8 text-fg">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <Ai4TechDocLogo alt="" className="h-14 w-14" />
          <h1 className="font-display text-xl text-fg">{document.title}</h1>
        </CardHeader>
        <CardContent className="w-full text-center">
          <div id="startup-loading" className="relative h-12 w-full">
            <LoadingOverlay
              visible
              label={t("common.loading")}
              className="rounded-xl bg-card/90"
            />
          </div>
          <p
            id="status"
            hidden
            role="alert"
            aria-live="assertive"
            className="mt-4 text-sm text-fg-dim"
          />
        </CardContent>
      </Card>
    </main>
  );
}

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing in desktop-startup.html");

createRoot(root).render(
  <StrictMode>
    <DesktopStartup />
  </StrictMode>,
);
