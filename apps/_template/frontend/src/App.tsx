import { ThemeToggle } from "@internal/ui";
import { Route, Routes } from "react-router-dom";

import { Home } from "./routes/Home";

export function App() {
  return (
    <div className="flex h-screen flex-col bg-bg font-sans text-base text-fg">
      <header className="flex h-topbar-h items-center justify-between border-b px-4">
        {/* Standard : le nom/logo porte une description breve en infobulle (title). */}
        <span
          className="font-display text-lg text-brand-blue-light"
          title="Description breve de l'app (a personnaliser au bootstrap)"
          style={{ cursor: "help" }}
        >
          TEMPLATE
        </span>
        <ThemeToggle />
      </header>
      <main className="flex-1 overflow-auto p-6">
        <Routes>
          <Route path="/" element={<Home />} />
        </Routes>
      </main>
    </div>
  );
}
