import { create } from "zustand";
import { persist } from "zustand/middleware";

/** Etat de travail partage entre onglets : import courant + run courant. */
type WorkspaceState = {
  importId: string | null;
  runId: string | null;
  setImport: (id: string | null) => void;
  setRun: (id: string | null) => void;
};

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set) => ({
      importId: null,
      runId: null,
      // Changer d'import invalide le run courant.
      setImport: (id) => set({ importId: id, runId: null }),
      setRun: (id) => set({ runId: id }),
    }),
    { name: "cto-workspace" },
  ),
);
