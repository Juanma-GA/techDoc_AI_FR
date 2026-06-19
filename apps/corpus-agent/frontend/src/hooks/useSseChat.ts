import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { streamAsk } from "../lib/api";
import { useChatStore } from "../stores/useChatStore";

// Envoi d'une question + streaming SSE, branché sur le store de chat.
// Bulles optimistes (user + assistant vide), append des tokens, invalidation
// des sessions/messages au `done`.
export function useSseChat() {
  const qc = useQueryClient();
  const store = useChatStore();

  const send = useCallback(
    (question: string, projectIds: string[], lang: string) => {
      const sessionId = useChatStore.getState().currentSessionId;
      store.pushUser(question);
      store.startAssistant();
      streamAsk(
        { session_id: sessionId, project_ids: projectIds, question, lang },
        {
          onSession: (info) => {
            useChatStore.getState().setSessionId(info.session_id);
            void qc.invalidateQueries({ queryKey: ["chat-sessions"] });
          },
          onToken: (delta) => useChatStore.getState().appendToken(delta),
          onError: (msg) => {
            useChatStore.getState().setAssistant(`✗ ${msg}`);
            useChatStore.getState().endStream();
          },
          onDone: () => {
            const st = useChatStore.getState();
            st.endStream();
            void qc.invalidateQueries({ queryKey: ["chat-sessions"] });
            if (st.currentSessionId) {
              void qc.invalidateQueries({ queryKey: ["chat-messages", st.currentSessionId] });
            }
          },
        },
      );
    },
    [qc, store],
  );

  return { send, streaming: store.streaming };
}
