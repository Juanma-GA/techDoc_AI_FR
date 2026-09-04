import { create } from "zustand";

type ViewerState = {
  pdfVersion: number;
  currentPage: number;
  zoom: number;
  selectedSuggestionId: string | null;
  setPdfVersion: (v: number) => void;
  setCurrentPage: (p: number) => void;
  setZoom: (z: number) => void;
  setSelectedSuggestionId: (id: string | null) => void;
  reset: () => void;
};

const initial = {
  pdfVersion: 0,
  currentPage: 1,
  zoom: 1,
  selectedSuggestionId: null as string | null,
};

export const useViewerStore = create<ViewerState>((set) => ({
  ...initial,
  setPdfVersion: (v) => set({ pdfVersion: v }),
  setCurrentPage: (p) => set({ currentPage: Math.max(1, p) }),
  setZoom: (z) => set({ zoom: Math.min(3, Math.max(0.5, z)) }),
  setSelectedSuggestionId: (id) => set({ selectedSuggestionId: id }),
  reset: () => set({ ...initial }),
}));
