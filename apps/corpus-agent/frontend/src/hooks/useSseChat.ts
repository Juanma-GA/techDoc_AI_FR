import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import { streamAsk } from "../lib/api";
import { useChatStore } from "../stores/useChatStore";

// Codes d'erreur (backend : AppError.code ; frontend : "CLIENT_*" côté
// streamAsk pour les pannes de transport) -> clé i18n. Un code absent de
// cette table retombe sur le message brut envoyé par streamAsk (jamais
// bloquant, juste non traduit).
const ERROR_CODE_KEYS: Record<string, string> = {
  MISTRAL_NOT_CONFIGURED: "chatbot.notConfigured",
  LLM_DISABLED: "chatbot.errorLlmDisabled",
  CLIENT_STREAM_TIMEOUT_CONNECT: "chatbot.errorStreamTimeoutConnect",
  CLIENT_NO_STREAM: "chatbot.errorNoStream",
  CLIENT_STREAM_TIMEOUT_READ: "chatbot.errorStreamTimeoutRead",
};

// Envoi d'une question + streaming SSE, branché sur le store de chat.
// Bulles optimistes (user + assistant vide), append des tokens, invalidation
// des sessions/messages au `done`.
export function useSseChat() {
  const { t } = useTranslation();
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
          onError: (msg, code) => {
            const key = code ? ERROR_CODE_KEYS[code] : undefined;
            useChatStore.getState().setAssistant(`✗ ${key ? t(key) : msg}`);
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
    [qc, store, t],
  );

  return { send, streaming: store.streaming };
}
