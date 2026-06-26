import { create } from "zustand";

// Scope du Manager + passage de relais inter-onglets (preview : « ouvrir la
// fiche projet » / « aller en Rédacteur » présélectionnent un projet).
type ScopeState = {
  managerScope: string[];
  redacteurProjectId: string | null;
  setManagerScope: (ids: string[]) => void;
  setRedacteurProjectId: (id: string | null) => void;
};

export const useScopeStore = create<ScopeState>((set) => ({
  managerScope: [],
  redacteurProjectId: null,
  setManagerScope: (ids) => set({ managerScope: ids }),
  setRedacteurProjectId: (id) => set({ redacteurProjectId: id }),
}));
