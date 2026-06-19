import { useQuery } from "@tanstack/react-query";

import { healthApi, type HealthDto, type LlmState } from "../lib/api";

/** Lecture de l'etat backend + LLM (badge sidebar). */
export function useHealth() {
  return useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.get,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

/** Variantes Badge de @internal/ui (pas de "off" : gris = "default"). */
export type LlmBadgeMeta = {
  label: string;
  variant: "default" | "success" | "warning";
};

/**
 * Mappe l'etat LLM vers le libelle + la variante du badge, conformement au
 * preview (llmBadgeClass / llmBadgeLabel) :
 *   ok             -> ON / success
 *   disabled       -> OFF / default (gris)
 *   untested       -> A TESTER / warning
 *   not_configured -> NO KEY / warning
 */
export function llmBadgeMeta(state: LlmState | undefined): LlmBadgeMeta {
  switch (state) {
    case "ok":
      return { label: "ON", variant: "success" };
    case "disabled":
      return { label: "OFF", variant: "default" };
    case "untested":
      return { label: "A TESTER", variant: "warning" };
    case "not_configured":
      return { label: "NO KEY", variant: "warning" };
    default:
      return { label: "?", variant: "warning" };
  }
}
