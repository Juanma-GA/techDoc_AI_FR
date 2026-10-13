import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ecmAutomationApi, type PathPreferencesDto } from "../lib/api";

const EMPTY_PATHS: PathPreferencesDto = {
  source_path: "",
  tracker_path: "",
  output_path: "",
};

export function usePathPreferences() {
  const preferencesQuery = useQuery({
    queryKey: ["ecm-automation", "path-preferences"],
    queryFn: ecmAutomationApi.getPathPreferences,
  });
  const [editedPaths, setEditedPaths] = useState<PathPreferencesDto | null>(null);
  const saveMutation = useMutation({
    mutationFn: ecmAutomationApi.savePathPreferences,
    scope: { id: "ecm-automation-path-preferences" },
  });
  const paths = editedPaths ?? preferencesQuery.data ?? EMPTY_PATHS;

  function setPath(field: keyof PathPreferencesDto, value: string) {
    setEditedPaths((current) => ({
      ...(current ?? preferencesQuery.data ?? EMPTY_PATHS),
      [field]: value,
    }));
  }

  function savePaths(overrides: Partial<PathPreferencesDto> = {}) {
    const nextPaths = { ...paths, ...overrides };
    setEditedPaths(nextPaths);
    saveMutation.mutate(nextPaths);
  }

  return {
    paths,
    isLoading: preferencesQuery.isPending,
    loadError: preferencesQuery.error,
    saveError: saveMutation.error,
    setPath,
    savePaths,
  };
}