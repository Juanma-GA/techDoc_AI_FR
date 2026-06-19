import { create } from "zustand";
import { persist } from "zustand/middleware";

/** Types de fichiers source memorises entre onglets (evite de re-piocher). */
export type SourceKind = "smgxml" | "nomenclature" | "mapping";

/** Etat de travail partage entre onglets : import courant, run courant, et les
 *  chemins de fichiers source deja choisis (pre-remplissage des selecteurs). */
type WorkspaceState = {
  importId: string | null;
  runId: string | null;
  /** Dernier chemin choisi par type de source (persiste). */
  sources: Record<SourceKind, string>;
  setImport: (id: string | null) => void;
  setRun: (id: string | null) => void;
  setSource: (kind: SourceKind, path: string) => void;
};

const EMPTY_SOURCES: Record<SourceKind, string> = { smgxml: "", nomenclature: "", mapping: "" };

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set) => ({
      importId: null,
      runId: null,
      sources: { ...EMPTY_SOURCES },
      // Changer d'import invalide le run courant.
      setImport: (id) => set({ importId: id, runId: null }),
      setRun: (id) => set({ runId: id }),
      setSource: (kind, path) => set((s) => ({ sources: { ...s.sources, [kind]: path } })),
    }),
    {
      name: "cto-workspace",
      // Tolere les versions persistees anterieures sans `sources`.
      merge: (persisted, current) => ({
        ...current,
        ...(persisted as Partial<WorkspaceState>),
        sources: { ...EMPTY_SOURCES, ...(persisted as { sources?: Record<string, string> })?.sources },
      }),
    },
  ),
);
