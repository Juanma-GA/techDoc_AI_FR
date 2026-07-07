import { create } from "zustand";

type CatiState = {
  selectedDocId: string | null;
  setSelectedDocId: (id: string | null) => void;
};

export const useCatiStore = create<CatiState>((set) => ({
  selectedDocId: null,
  setSelectedDocId: (id) => set({ selectedDocId: id }),
}));
