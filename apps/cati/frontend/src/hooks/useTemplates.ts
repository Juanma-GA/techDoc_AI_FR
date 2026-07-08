import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { templatesApi, type TemplateDto } from "../lib/api";

export function useTemplates() {
  return useQuery<TemplateDto[]>({ queryKey: ["templates"], queryFn: templatesApi.list });
}

export function useUploadTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { file: File; name: string }) => templatesApi.upload(args.file, args.name),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function useSetDefaultTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => templatesApi.setDefault(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => templatesApi.remove(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}
