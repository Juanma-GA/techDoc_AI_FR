import { create } from "zustand";

import type {
  AssistantDocument,
  AssistantReply,
  ChatMessage,
  FlowGraph,
  FlowOut,
  ParseResult,
  SourceType,
} from "../types/flow";

// Etat de l'editeur, en memoire uniquement (aucune persistance navigateur).
type EditorState = {
  graph: FlowGraph | null;
  name: string;
  sourceType: SourceType;
  // Source effectivement analysee, enregistree avec le flux.
  source: string;
  currentFlowId: string | null;
  warnings: string[];
  llmUsed: boolean;
  messages: ChatMessage[];
  // Documents de reference joints a l'assistant, renvoyes a chaque echange.
  documents: AssistantDocument[];
  // Toute modification du graphe invalide la validation : export uniquement apres "Valider".
  validated: boolean;
  applyParse: (result: ParseResult, sourceType: SourceType, sourceText: string) => void;
  pushMessage: (message: ChatMessage) => void;
  applyAssistant: (reply: AssistantReply) => void;
  addDocument: (doc: AssistantDocument) => void;
  removeDocument: (name: string) => void;
  setValidated: (validated: boolean) => void;
  setName: (name: string) => void;
  loadFlow: (flow: FlowOut) => void;
  setSaved: (id: string, name: string) => void;
  clear: () => void;
};

const INITIAL = {
  graph: null,
  name: "",
  sourceType: "text" as SourceType,
  source: "",
  currentFlowId: null,
  warnings: [],
  llmUsed: false,
  messages: [] as ChatMessage[],
  documents: [] as AssistantDocument[],
  validated: false,
};

const MAX_DOCUMENTS = 10;

const userPrompts = (messages: ChatMessage[]) =>
  messages
    .filter((m) => m.role === "user")
    .map((m) => m.content)
    .join("\n\n");

export const useEditorStore = create<EditorState>((set, get) => ({
  ...INITIAL,
  applyParse: (result, sourceType, sourceText) =>
    set({
      graph: result.graph,
      warnings: result.warnings,
      llmUsed: result.llm_used,
      validated: false,
      sourceType,
      source: sourceText,
      name: get().name || result.graph.title,
    }),
  pushMessage: (message) => set({ messages: [...get().messages, message] }),
  applyAssistant: (reply) => {
    const messages: ChatMessage[] = [...get().messages, { role: "assistant", content: reply.message }];
    if (!reply.graph) {
      set({ messages, warnings: reply.warnings });
      return;
    }
    set({
      messages,
      graph: reply.graph,
      warnings: reply.warnings,
      llmUsed: reply.llm_used,
      validated: false,
      sourceType: "text",
      source: userPrompts(messages).slice(0, 200000),
      name: get().name || reply.graph.title,
    });
  },
  addDocument: (doc) => {
    const others = get().documents.filter((d) => d.name !== doc.name);
    set({ documents: [...others, doc].slice(-MAX_DOCUMENTS) });
  },
  removeDocument: (name) => set({ documents: get().documents.filter((d) => d.name !== name) }),
  setValidated: (validated) => set({ validated }),
  setName: (name) => set({ name }),
  loadFlow: (flow) =>
    set({
      graph: flow.graph,
      name: flow.name,
      sourceType: flow.source_type,
      source: flow.source_text,
      currentFlowId: flow.id,
      warnings: [],
      llmUsed: false,
      messages: [],
      documents: [],
      validated: false,
    }),
  setSaved: (currentFlowId, name) => set({ currentFlowId, name }),
  clear: () => set(INITIAL),
}));
