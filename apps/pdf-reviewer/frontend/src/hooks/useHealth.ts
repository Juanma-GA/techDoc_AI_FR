import { useQuery } from "@tanstack/react-query";

import { healthApi, type HealthDto } from "../lib/api";

/** Lecture de l'etat backend + LLM (badge sidebar, regle CLAUDE.md #13). */
export function useHealth() {
  return useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.read,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}
