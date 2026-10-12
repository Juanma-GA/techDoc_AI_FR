import { create } from "zustand";
import { persist } from "zustand/middleware";

/** Types de fichiers source memorises entre onglets (evite de re-piocher).
 *  Chaque etape memorise son propre chemin sous la racine commune. */
export type SourceKind =
  | "smgxml"
  | "nomenclature"
  | "mapping"
  | "composerRoot"
  | "convertedRoot"
  | "smgxmlFolder"
  | "profilesRoot";

/** Etat de travail partage entre onglets : import courant, run courant, et les
 *  chemins de fichiers source deja choisis (pre-remplissage des selecteurs). */
/** Dernier mapping de nomenclature utilise (champ -> index colonne 0-based) +
 *  ligne d'en-tete, persiste pour pre-remplir le mapping au prochain preview. */
export type NomenMapping = { headerRow: number; cols: Record<string, number> };

type WorkspaceState = {
  importId: string | null;
  nomenclatureRunId: string | null;
  /** Dernier chemin choisi par type de source (persiste). */
  sources: Record<SourceKind, string>;
  /** Dernier mapping nomenclature valide (null tant qu'aucune analyse). */
  nomenMapping: NomenMapping | null;
  setImport: (id: string | null) => void;
  setNomenclatureRun: (id: string | null) => void;
  resetWorkspace: () => void;
  setSource: (kind: SourceKind, path: string) => void;
  setNomenMapping: (mapping: NomenMapping) => void;
};

const EMPTY_SOURCES: Record<SourceKind, string> = {
  smgxml: "",
  nomenclature: "",
  mapping: "",
  composerRoot: "",
  convertedRoot: "",
  smgxmlFolder: "",
  profilesRoot: "",
};

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set) => ({
      importId: null,
      nomenclatureRunId: null,
      sources: { ...EMPTY_SOURCES },
      nomenMapping: null,
      setImport: (id) => set({ importId: id }),
      setNomenclatureRun: (id) => set({ nomenclatureRunId: id }),
      resetWorkspace: () =>
        set({
          importId: null,
          nomenclatureRunId: null,
          sources: { ...EMPTY_SOURCES },
          nomenMapping: null,
        }),
      setSource: (kind, path) => set((s) => ({ sources: { ...s.sources, [kind]: path } })),
      setNomenMapping: (mapping) => set({ nomenMapping: mapping }),
    }),
    {
      name: "cto-workspace",
      // Tolere les versions persistees anterieures sans `sources` / `nomenMapping`.
      merge: (persisted, current) => ({
        ...current,
        ...(persisted as Partial<WorkspaceState>),
        sources: { ...EMPTY_SOURCES, ...(persisted as { sources?: Record<string, string> })?.sources },
      }),
    },
  ),
);
