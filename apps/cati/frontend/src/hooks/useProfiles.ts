import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { profilesApi, type ProfileDto, type ProfileInput } from "../lib/api";

export function useProfiles() {
  return useQuery<ProfileDto[]>({ queryKey: ["profiles"], queryFn: profilesApi.list });
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: ["profiles"] });
}

export function useCreateProfile() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (body: ProfileInput) => profilesApi.create(body), onSuccess: invalidate });
}

export function useUpdateProfile() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (args: { id: string; body: ProfileInput }) => profilesApi.update(args.id, args.body),
    onSuccess: invalidate,
  });
}

export function useSetDefaultProfile() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => profilesApi.setDefault(id), onSuccess: invalidate });
}

export function useDeleteProfile() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => profilesApi.remove(id), onSuccess: invalidate });
}
