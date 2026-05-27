import { create } from "zustand";

type Status = "idle" | "streaming" | "done" | "error";

export type OutputLang = "fr" | "en" | "es";

const OUTPUT_LANG_KEY = "doc-writer-output-lang";

function readInitialOutputLang(): OutputLang {
  if (typeof window === "undefined") return "fr";
  const stored = window.localStorage.getItem(OUTPUT_LANG_KEY);
  if (stored === "fr" || stored === "en" || stored === "es") return stored;
  // Defaut = langue UI detectee par i18next (i18next-browser-languagedetector
  // ecrit la cle 'i18nextLng'). Sinon FR.
  const uiLang = (window.localStorage.getItem("i18nextLng") || "").slice(0, 2);
  if (uiLang === "en" || uiLang === "es") return uiLang;
  return "fr";
}

type GenerateState = {
  prompt: string;
  scopeDocIds: string[];
  templateDocId: string | null;
  outputLang: OutputLang;
  output: string;
  status: Status;
  errorMessage: string | null;
  currentSessionId: string | null;
  setPrompt: (value: string) => void;
  setScopeDocIds: (ids: string[]) => void;
  setTemplateDocId: (id: string | null) => void;
  setOutputLang: (lang: OutputLang) => void;
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
  outputLang: readInitialOutputLang(),
  output: "",
  status: "idle",
  errorMessage: null,
  currentSessionId: null,
  setPrompt: (value) => set({ prompt: value }),
  setScopeDocIds: (ids) => set({ scopeDocIds: ids }),
  setTemplateDocId: (id) => set({ templateDocId: id }),
  setOutputLang: (lang) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(OUTPUT_LANG_KEY, lang);
    }
    set({ outputLang: lang });
  },
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
