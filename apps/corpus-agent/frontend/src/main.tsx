import "./index.css";
import "./styles/preview-skin.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { bootstrapI18n } from "./i18n";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
});

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("#root element missing in index.html");
}

// Charge les traductions backend (source de vérité, comme le preview) avant le
// premier rendu ; en cas d'échec on garde le fallback local minimal.
void bootstrapI18n().finally(() => {
  createRoot(rootElement).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename={import.meta.env.BASE_URL}>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
});
