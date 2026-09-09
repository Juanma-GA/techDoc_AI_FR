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

export type ChecklistContext = {
  meta_revision_date: string | null;
  meta_cmm_number: string | null;
  meta_first_issue_date: string | null;
  meta_revision_number: string | null;
  document_language: "fr" | "en" | null;
};

export type ChecklistContextInput = Partial<ChecklistContext>;

export function useChecklistContext() {
  return useQuery({
    queryKey: ["settings", "checklist-context"],
    queryFn: () => api.get<ChecklistContext>("/settings/checklist-context"),
  });
}

export function useUpdateChecklistContext() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ChecklistContextInput) =>
      api.post<ChecklistContext>("/settings/checklist-context", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", "checklist-context"] }),
  });
}

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

// ----- Fiabilisation IA (verification adversariale + feedback global) --------

export type Reliability = {
  verify_enabled: boolean;
  verify_passes: number;
  max_calls: number;
  feedback_enabled: boolean;
};

export type ReliabilityInput = Partial<Reliability>;

export function useReliability() {
  return useQuery({
    queryKey: ["settings", "reliability"],
    queryFn: () => api.get<Reliability>("/settings/reliability"),
  });
}

export function useUpdateReliability() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ReliabilityInput) =>
      api.post<Reliability>("/settings/reliability", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", "reliability"] }),
  });
}

export function useUpdateAiPrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prompt: string) => api.post<AiPrompt>("/settings/ai-prompt", { prompt }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", "ai-prompt"] }),
  });
}
