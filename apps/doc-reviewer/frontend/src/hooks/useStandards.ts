import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "../lib/api";
import { useFiltersStore } from "../stores/filtersStore";
import type { CatalogRule, Standard, StandardVersion, StandardVersionDetail } from "../types/domain";

export type CreateStandardInput = {
  code: string;
  label: string;
  description?: string;
};

export type CreateVersionInput = {
  standardId: string;
  label: string;
  catalog?: CatalogRule[];
};

export function useStandards() {
  const reconcileActiveStandardVersions = useFiltersStore(
    (state) => state.reconcileActiveStandardVersions,
  );
  const standards = useQuery({
    queryKey: ["standards"],
    queryFn: () => api.get<Standard[]>("/standards"),
  });

  useEffect(() => {
    if (!standards.data) return;
    const validVersionIds = standards.data.flatMap((standard) =>
      standard.versions.map((version) => version.id),
    );
    reconcileActiveStandardVersions(validVersionIds);
  }, [standards.data, reconcileActiveStandardVersions]);

  return standards;
}

export function useStandardVersionDetail(standardId: string | null, versionId: string | null) {
  return useQuery({
    queryKey: ["standard-version", standardId, versionId],
    queryFn: () =>
      api.get<StandardVersionDetail>(`/standards/${standardId}/versions/${versionId}`),
    enabled: Boolean(standardId && versionId),
  });
}

export function useCreateStandard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateStandardInput) => api.post<Standard>("/standards", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["standards"] }),
  });
}

export function useDeleteStandard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (standardId: string) => api.delete<void>(`/standards/${standardId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["standards"] }),
  });
}

export function useCreateVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ standardId, label, catalog }: CreateVersionInput) =>
      api.post<StandardVersion>(`/standards/${standardId}/versions`, {
        label,
        catalog: catalog ?? [],
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["standards"] }),
  });
}

export function useDeleteVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ standardId, versionId }: { standardId: string; versionId: string }) =>
      api.delete<void>(`/standards/${standardId}/versions/${versionId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["standards"] }),
  });
}

export function useToggleCatalogRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      standardId,
      versionId,
      code,
      enabled,
    }: {
      standardId: string;
      versionId: string;
      code: string;
      enabled: boolean;
    }) =>
      api.post<StandardVersionDetail>(
        `/standards/${standardId}/versions/${versionId}/rules/toggle`,
        { code, enabled },
      ),
    onSuccess: (_detail, variables) => {
      qc.invalidateQueries({
        queryKey: ["standard-version", variables.standardId, variables.versionId],
      });
      qc.invalidateQueries({ queryKey: ["compiled-rules"] });
    },
  });
}
