import { api, apiForm } from "./client";
import type { BrexProfile, BrexProfileDetail, S1000dIssue } from "./types";

export const brexApi = {
  list: () => api<BrexProfile[]>("/brex"),
  detail: (brexId: string) => api<BrexProfileDetail>(`/brex/${encodeURIComponent(brexId)}`),
  delete: (brexId: string, confirmToken: string) =>
    api<{ id: string; status: string }>(
      `/brex/${encodeURIComponent(brexId)}?confirm_token=${encodeURIComponent(confirmToken)}`,
      { method: "DELETE" },
    ),
  upload: async (
    file: File,
    name: string,
    issue: S1000dIssue,
  ): Promise<BrexProfile> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", name);
    fd.append("s1000d_issue", issue);
    return apiForm<BrexProfile>("/brex", fd);
  },
};
