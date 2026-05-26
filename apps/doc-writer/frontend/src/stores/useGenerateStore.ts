import { create } from "zustand";

type Status = "idle" | "streaming" | "done" | "error";

type GenerateState = {
  prompt: string;
  scopeDocIds: string[];
  templateDocId: string | null;
  output: string;
  status: Status;
  errorMessage: string | null;
  currentSessionId: string | null;
  setPrompt: (value: string) => void;
  setScopeDocIds: (ids: string[]) => void;
  setTemplateDocId: (id: string | null) => void;
  beginStream: (sessionId: string) => void;
  appendToken: (delta: string) => void;
  finishStream: () => void;
  failStream: (message: string) => void;
  reset: () => void;
};

export const useGenerateStore = create<GenerateState>((set) => ({
  prompt: "",
  scopeDocIds: [],
  templateDocId: null,
  output: "",
  status: "idle",
  errorMessage: null,
  currentSessionId: null,
  setPrompt: (value) => set({ prompt: value }),
  setScopeDocIds: (ids) => set({ scopeDocIds: ids }),
  setTemplateDocId: (id) => set({ templateDocId: id }),
  beginStream: (sessionId) =>
    set({
      status: "streaming",
      output: "",
      errorMessage: null,
      currentSessionId: sessionId,
    }),
  appendToken: (delta) =>
    set((state) => ({ output: state.output + delta })),
  finishStream: () => set({ status: "done" }),
  failStream: (message) => set({ status: "error", errorMessage: message }),
  reset: () =>
    set({
      output: "",
      status: "idle",
      errorMessage: null,
      currentSessionId: null,
    }),
}));
