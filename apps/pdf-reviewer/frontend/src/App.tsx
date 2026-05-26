import { ThemeToggle } from "@internal/ui";
import { Route, Routes, useLocation } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { Sidebar } from "./components/Sidebar";
import { DocumentReviewer } from "./routes/DocumentReviewer";
import { DocumentsList } from "./routes/DocumentsList";
import { Rules } from "./routes/Rules";
import { Settings } from "./routes/Settings";
import { Standards } from "./routes/Standards";

export function App() {
  const location = useLocation();
  // Reviewer takes the full viewport — collapse the sidebar there.
  const isReviewer = location.pathname.startsWith("/documents/");

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-bg font-sans text-base text-fg">
        {isReviewer ? null : <Sidebar />}
        <main className="flex flex-1 flex-col overflow-hidden">
          <header className="flex h-topbar-h items-center justify-end gap-2 border-b px-4">
            <ThemeToggle />
          </header>
          <div className="flex flex-1 flex-col overflow-hidden">
            <Routes>
              <Route path="/" element={<DocumentsList />} />
              <Route path="/documents/:id" element={<DocumentReviewer />} />
              <Route path="/rules" element={<Rules />} />
              <Route path="/standards" element={<Standards />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
}
