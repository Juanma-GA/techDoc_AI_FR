import { useQuery } from "@tanstack/react-query";

import { healthApi } from "../lib/api";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: healthApi.read, refetchInterval: 30_000 });
}
