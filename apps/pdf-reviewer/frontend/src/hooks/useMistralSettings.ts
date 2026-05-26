import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";

export type MistralSettings = {
  api_key_set: boolean;
  api_key_preview: string;
  base_url: string;
  chat_model: string;
};

export type MistralSettingsInput = {
  api_key?: string;
  base_url?: string;
  chat_model?: string;
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

export function useUpdateMistralSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MistralSettingsInput) =>
      api.post<MistralSettings>("/settings/mistral", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", "mistral"] }),
  });
}

export function useTestMistralConnection() {
  return useMutation({
    mutationFn: () => api.post<TestConnectionResult>("/settings/mistral/test"),
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
