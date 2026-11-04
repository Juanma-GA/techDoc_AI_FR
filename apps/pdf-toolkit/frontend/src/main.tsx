import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ErrorBoundary } from "@internal/ui";
import { setAi4TechDocFavicon } from "@internal/techdoc-brand";

import "./index.css";
import "./i18n";
import { App } from "./App";

setAi4TechDocFavicon();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("#root element is missing");
}

createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
