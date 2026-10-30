import { api, apiForm, apiBlob, apiValidated } from "./client";
import { z } from "zod";
import type { DocumentOut, S1000dIssue, ContextHint, MigrationInputKind, MigrationInputMapping } from "./types";

export const documentsApi = {
  list: () => api<DocumentOut[]>("/documents"),
  get: (docId: string) => api<DocumentOut>(`/documents/${docId}`),
  delete: (docId: string, confirmToken: string) =>
    api<{ id: string; status: string }>(
      `/documents/${docId}?confirm_token=${encodeURIComponent(confirmToken)}`,
      { method: "DELETE" },
    ),
  upload: async (
    file: File,
    issue: S1000dIssue,
    hint: ContextHint,
    brexId?: string,
  ): Promise<DocumentOut & { reused?: boolean }> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("s1000d_issue", issue);
    fd.append("context_hint", hint);
    if (brexId) fd.append("brex_id", brexId);
    return apiForm<DocumentOut>("/documents", fd);
  },
};


export const migrationInputsApi = {
  read: () => apiValidated("/migration-inputs", (value): MigrationInputMapping => {
    const file = z.object({ filename: z.string() }).optional();
    return z.object({
      issue: z.enum(["4.1", "4.2", "5.0"]), context_hint: z.enum(["mixed", "descriptive", "procedural"]),
      brex_id: z.string().nullable(),
      files: z.object({ document: file, dmrl: file, cir: file, brex_rules: file, dm_header: file }),
    }).parse(value);
  }),
  file: async (kind: MigrationInputKind, filename: string): Promise<File> => {
    return apiBlob(`/migration-inputs/${kind}`, filename);
  },
};
