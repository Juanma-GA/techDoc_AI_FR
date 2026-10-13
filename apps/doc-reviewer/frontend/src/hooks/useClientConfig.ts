import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";

export type ClientCatalog = {
  code: string;
  version: string;
  standard_version_id: string;
};

export type ClientMappingField = {
  type: "string" | "enum" | "string_list" | "integer" | "number" | "boolean";
  required: boolean;
  default?: string | number | boolean | string[] | null;
  labels?: Record<string, string>;
  max_length?: number | null;
  max_items?: number | null;
  allowed_values?: string[] | null;
  pattern?: string | null;
  format_hint?: Record<string, string> | null;
};

export type ClientConfig = {
  client_code: string;
  label: string;
  bundle: string;
  bundle_version: string;
  contract_version: string;
  manifest_hash: string;
  mapping_hash: string;
  bundle_hash: string;
  catalogs: ClientCatalog[];
  mapping: {
    fields: Record<string, ClientMappingField>;
    entities: Record<string, string>;
    tokens: Record<string, string>;
  };
  ui_options: Record<string, unknown>;
};

export type ClientRule = {
  code: string;
  name: string;
  description: string;
  message: string;
  rule_number: number;
  kind: string;
  severity: "info" | "warning" | "error";
  execution: "deterministic" | "semantic" | "manual" | "unsupported";
  active: boolean;
  catalog_code: string;
  catalog_version: string;
  translations: Record<string, Record<string, string>>;
};

export function useClientConfig() {
  return useQuery({
    queryKey: ["client-config"],
    queryFn: () => api.get<ClientConfig>("/client-config"),
  });
}

export function useClientRules() {
  return useQuery({
    queryKey: ["client-rules"],
    queryFn: () => api.get<ClientRule[]>("/client-rules"),
  });
}

export function usePatchClientRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ code, active }: { code: string; active: boolean }) =>
      api.patch<ClientRule>(`/client-rules/${encodeURIComponent(code)}`, { active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["client-rules"] }),
  });
}