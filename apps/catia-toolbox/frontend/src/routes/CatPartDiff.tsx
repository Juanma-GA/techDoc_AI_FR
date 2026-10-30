import { Button, Spinner } from "@internal/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { CatPartDiffResults } from "../components/business/CatPartDiffResults";
import { FilePicker } from "../components/FilePicker";
import { ApiClientError } from "../lib/api";
import { catpartDiffApi } from "../lib/catpartApi";

function downloadWorkbook(blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "catpart-ge-screening.xlsx";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function CatPartDiff() {
  const { t } = useTranslation();
  const [oldPath, setOldPath] = useState("");
  const [newPath, setNewPath] = useState("");
  const compareMutation = useMutation({
    mutationFn: async () => {
      const comparedOldPath = oldPath;
      const comparedNewPath = newPath;
      const result = await catpartDiffApi.compare(comparedOldPath, comparedNewPath);
      return { result, oldPath: comparedOldPath, newPath: comparedNewPath };
    },
  });
  const exportMutation = useMutation({
    mutationFn: () => {
      const compared = compareMutation.data;
      if (!compared) throw new Error(t("catpartDiff.exportErrorFallback"));
      return catpartDiffApi.exportExcel(compared.oldPath, compared.newPath);
    },
    onSuccess: downloadWorkbook,
  });
  const comparison = compareMutation.data;
  const errorMessage = (error: Error | null) =>
    error instanceof ApiClientError ? error.message : error ? t("catpartDiff.errorFallback") : null;

  return (
    <div className="form">
      <section className="workflow-section">
        <h2 className="section-title">{t("catpartDiff.title")}</h2>
        <p className="hint">{t("catpartDiff.description")}</p>
        <p className="hint">{t("catpartDiff.limit")}</p>
        <div className="row">
          <div className="field grow">
            <span className="field-label">{t("catpartDiff.oldFolder")}</span>
            <FilePicker
              mode="folder"
              scope="input"
              exts={[".CATPart"]}
              value={oldPath}
              onChange={setOldPath}
              label={t("catpartDiff.selectFolder")}
            />
          </div>
          <div className="field grow">
            <span className="field-label">{t("catpartDiff.newFolder")}</span>
            <FilePicker
              mode="folder"
              scope="input"
              exts={[".CATPart"]}
              value={newPath}
              onChange={setNewPath}
              label={t("catpartDiff.selectFolder")}
            />
          </div>
          <Button
            type="button"
            variant="primary"
            onClick={() => compareMutation.mutate()}
            disabled={!oldPath || !newPath || compareMutation.isPending}
          >
            {compareMutation.isPending ? <Spinner aria-label={t("common.loading")} /> : null}
            {compareMutation.isPending ? t("catpartDiff.analyzing") : t("catpartDiff.compare")}
          </Button>
        </div>
        {errorMessage(compareMutation.error) ? (
          <p className="error" role="alert">{errorMessage(compareMutation.error)}</p>
        ) : null}
      </section>

      {comparison ? (
        <CatPartDiffResults
          result={comparison.result}
          isExporting={exportMutation.isPending || compareMutation.isPending}
          exportError={errorMessage(exportMutation.error)}
          onExportExcel={() => exportMutation.mutate()}
        />
      ) : (
        <div className="empty-state">
          <h3 className="section-title">{t("catpartDiff.runPrompt")}</h3>
        </div>
      )}
    </div>
  );
}
