import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { documentsApi, itemsApi, type ItemFields, type ItemsDto } from "../lib/api";

export function useItems(docId: string | null) {
  return useQuery<ItemsDto>({
    queryKey: ["items", docId],
    queryFn: () => documentsApi.items(docId as string),
    enabled: !!docId,
  });
}

export function usePatchItem(docId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { itemId: string; fields?: ItemFields; included?: boolean }) =>
      itemsApi.patch(docId, args.itemId, { fields: args.fields, included: args.included }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["items", docId] }),
  });
}

export function useCreateItem(docId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fields: ItemFields) => itemsApi.create(docId, fields),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["items", docId] }),
  });
}

export function useDeleteItem(docId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => itemsApi.remove(docId, itemId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["items", docId] }),
  });
}
