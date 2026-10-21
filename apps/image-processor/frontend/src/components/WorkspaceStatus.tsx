import { Button } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { useWorkflow } from "../hooks/WorkflowProvider";
import { requestError } from "../lib/workspace-api";

export function WorkspaceStatus() {
  const { t } = useTranslation();
  const workflow = useWorkflow();
  const { storage } = workflow;
  const failure = storage.startupError ?? storage.saveError;
  return (
    <div className="space-y-2">
      {failure ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-md border border-danger/40 p-3">
          <p className="min-w-0 flex-1 text-sm text-danger">
            {t(storage.startupError ? "history.startupError" : "history.saveError")}{" "}
            {requestError(failure, t("image.errorGeneric"))}
          </p>
          <Button
            variant="secondary" size="sm" disabled={storage.saving}
            onClick={storage.startupError ? storage.retryStartup : workflow.retrySave}
          >
            {t("history.retry")}
          </Button>
        </div>
      ) : (
        <p role="status" className="text-xs text-fg-dim">
          {t(!storage.ready ? "history.restoringExcel" : storage.saving ? "history.saving" : "history.saved")}
        </p>
      )}
    </div>
  );
}
