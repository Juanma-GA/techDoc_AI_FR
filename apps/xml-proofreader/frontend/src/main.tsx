import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./ui/App";
import { ErrorBoundary } from "./ui/ErrorBoundary";
import "./ui/theme.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary onError={(err, info) => console.error("App error:", err, info)}>
      <App />
    </ErrorBoundary>
  </StrictMode>
);
