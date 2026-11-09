import { create } from "zustand";

export type ChatBubble = { role: "user" | "assistant" | "system"; content: string };

type ChatState = {
  draft: string;
  setDraft: (draft: string) => void;
  currentSessionId: string | null;
  pendingNew: boolean;
  scopeProjectIds: string[];
  messages: ChatBubble[];
  streaming: boolean;
  setScope: (ids: string[]) => void;
  startNew: () => void;
  selectSession: (id: string, messages: ChatBubble[]) => void;
  setSessionId: (id: string) => void;
  pushUser: (content: string) => void;
  startAssistant: () => void;
  appendToken: (delta: string) => void;
  setAssistant: (content: string) => void;
  endStream: () => void;
  reset: () => void;
};

function patchLastAssistant(messages: ChatBubble[], update: (content: string) => string): ChatBubble[] {
  const msgs = messages.slice();
  const last = msgs[msgs.length - 1];
  if (last && last.role === "assistant") {
    msgs[msgs.length - 1] = { ...last, content: update(last.content) };
  }
  return msgs;
}

export const useChatStore = create<ChatState>((set) => ({
  draft: "",
  setDraft: (draft) => set({ draft }),
  currentSessionId: null,
  pendingNew: false,
  scopeProjectIds: [],
  messages: [],
  streaming: false,
  setScope: (ids) => set({ scopeProjectIds: ids }),
  startNew: () => set({ draft: "", currentSessionId: null, pendingNew: true, messages: [] }),
  selectSession: (id, messages) => set({ draft: "", currentSessionId: id, pendingNew: false, messages }),
  setSessionId: (id) => set({ currentSessionId: id, pendingNew: false }),
  pushUser: (content) => set((s) => ({ messages: [...s.messages, { role: "user", content }] })),
  startAssistant: () =>
    set((s) => ({ streaming: true, messages: [...s.messages, { role: "assistant", content: "" }] })),
  appendToken: (delta) => set((s) => ({ messages: patchLastAssistant(s.messages, (c) => c + delta) })),
  setAssistant: (content) => set((s) => ({ messages: patchLastAssistant(s.messages, () => content) })),
  endStream: () => set({ streaming: false }),
  reset: () => set({ draft: "", currentSessionId: null, pendingNew: false, messages: [], streaming: false }),
}));
