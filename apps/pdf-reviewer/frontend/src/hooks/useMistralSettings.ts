import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";

export type MistralSettings = {
  api_key_set: boolean;
  api_key_preview: string;
  base_url: string;
  chat_model: string;
  vision_model: string;
  vision_enabled: boolean;
  llm_enabled: boolean;
  llm_tested: boolean;
};

export type MistralSettingsInput = {
  api_key?: string;
  base_url?: string;
  chat_model?: string;
  vision_model?: string;
  vision_enabled?: boolean;
  llm_enabled?: boolean;
};

export type TestConnectionResult = {
  ok: boolean;
  message: string;
  models: string[];
};

export type AiPrompt = { prompt: string };

export function useMistralSettings() {
  return useQuery({
    queryKey: ["settings", "mistral"],
    queryFn: () => api.get<MistralSettings>("/settings/mistral"),
  });
}

/** Invalide la config Mistral ET le health (badge LLM sidebar, regle #14). */
function invalidateSettingsAndHealth(qc: ReturnType<typeof useQueryClient>): void {
  void qc.invalidateQueries({ queryKey: ["settings", "mistral"] });
  void qc.invalidateQueries({ queryKey: ["health"] });
}

export function useUpdateMistralSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MistralSettingsInput) =>
      api.post<MistralSettings>("/settings/mistral", body),
    onSuccess: () => invalidateSettingsAndHealth(qc),
  });
}

/** Interrupteur "LLM active" — POST /settings/mistral {llm_enabled}. */
export function useToggleLlm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (llm_enabled: boolean) =>
      api.post<MistralSettings>("/settings/mistral", { llm_enabled }),
    onSuccess: () => invalidateSettingsAndHealth(qc),
  });
}

export function useTestMistralConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<TestConnectionResult>("/settings/mistral/test"),
    // Un test (reussi ou non) pose llm_tested cote backend -> rafraichir le
    // badge LLM immediatement.
    onSuccess: () => invalidateSettingsAndHealth(qc),
  });
}

export function useAiPrompt() {
  return useQuery({
    queryKey: ["settings", "ai-prompt"],
    queryFn: () => api.get<AiPrompt>("/settings/ai-prompt"),
  });
}

export function useUpdateAiPrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prompt: string) => api.post<AiPrompt>("/settings/ai-prompt", { prompt }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", "ai-prompt"] }),
  });
}
