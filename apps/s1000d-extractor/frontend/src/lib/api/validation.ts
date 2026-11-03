import { apiForm } from "./client";
import type { DmValidationResult } from "../wizardTypes";
import { validationBatchSchema } from "../validationSchema";

export const validationApi = {
  validate: async (
    files: File[],
    issueOverrides: Array<string | null> = [],
    filenames: string[] = [],
  ): Promise<{ results: DmValidationResult[] }> => {
    const form = new FormData();
    files.forEach((file, index) => {
      form.append("files", file, filenames[index] || file.webkitRelativePath || file.name);
    });
    form.append("issue_overrides", JSON.stringify(issueOverrides));

    return apiForm<{ results: DmValidationResult[] }>("/validation/dms", form, (value) => {
      const parsed = validationBatchSchema.parse(value);
      if (parsed.results.length !== files.length) throw new Error("Validation response count mismatch.");
      return parsed;
    });
  },
};
