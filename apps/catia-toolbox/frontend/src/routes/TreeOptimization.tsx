import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { FilePicker } from "../components/FilePicker";
import {
  ApiClientError,
  browseApi,
  treeOptimizationApi,
  type TreeOptimizationRunDto,
} from "../lib/api";

export function TreeOptimization() {
  const { t } = useTranslation();
  const [path, setPath] = useState("");
  const selectedPathRef = useRef("");
  const [filesToAnalyze, setFilesToAnalyze] = useState<number | null>(null);
  const [result, setResult] = useState<TreeOptimizationRunDto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rootsQuery = useQuery({ queryKey: ["browse", "roots"], queryFn: browseApi.roots });
  const hasInputRoot = Boolean(rootsQuery.data?.input);

  const countMutation = useMutation({
    mutationFn: async (folderPath: string) => ({
      folderPath,
      data: await treeOptimizationApi.count(folderPath),
    }),
    onSuccess: ({ folderPath, data }) => {
      if (folderPath !== selectedPathRef.current) return;
      setFilesToAnalyze(data.files_count);
      setResult(null);
      setError(null);
    },
    onError: (reason: unknown) =>
      setError(reason instanceof ApiClientError ? reason.message : String(reason)),
  });

  const pickFolderMutation = useMutation({
    mutationFn: () => treeOptimizationApi.pickFolder(path.trim() || undefined, t("treeOptimization.folderLabel")),
    onSuccess: ({ path: selectedPath }) => {
      if (!selectedPath) return;
      selectedPathRef.current = selectedPath;
      setPath(selectedPath);
      setFilesToAnalyze(null);
      setError(null);
      countMutation.mutate(selectedPath);
    },
    onError: (reason: unknown) =>
      setError(reason instanceof ApiClientError ? reason.message : String(reason)),
  });

  const optimizeMutation = useMutation({
    mutationFn: () => treeOptimizationApi.run(path.trim(), true),
    onSuccess: (data) => {
      setResult(data);
      setFilesToAnalyze(null);
      setError(null);
    },
    onError: (reason: unknown) =>
      setError(reason instanceof ApiClientError ? reason.message : String(reason)),
  });

  const isPending =
    pickFolderMutation.isPending || countMutation.isPending || optimizeMutation.isPending;

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <article className="card">
        <div className="field">
          <span className="field-label">{t("treeOptimization.folderLabel")}</span>
          {rootsQuery.isLoading ? (
            <span className="spinner" />
          ) : hasInputRoot ? (
            <FilePicker
              mode="folder"
              scope="input"
              exts={[]}
              value={path}
              onChange={(nextPath) => {
                selectedPathRef.current = nextPath;
                setPath(nextPath);
                setFilesToAnalyze(null);
                setResult(null);
                setError(null);
                if (nextPath.trim()) countMutation.mutate(nextPath.trim());
              }}
            />
          ) : (
            <>
              <div className="row">
                <input
                  type="text"
                  className="input grow"
                  placeholder={t("treeOptimization.absolutePathPlaceholder")}
                  value={path}
                  onChange={(event) => {
                    selectedPathRef.current = event.target.value;
                    setPath(event.target.value);
                    setFilesToAnalyze(null);
                    setResult(null);
                    setError(null);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && event.currentTarget.value.trim()) {
                      countMutation.mutate(event.currentTarget.value.trim());
                    }
                  }}
                />
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() => pickFolderMutation.mutate()}
                  disabled={isPending}
                >
                  {pickFolderMutation.isPending ? <span className="spinner" /> : null}
                  <span>{t("picker.browse")}</span>
                </button>
              </div>
              <p className="hint">{t("treeOptimization.noInputRootHint")}</p>
            </>
          )}
        </div>
        {countMutation.isPending ? (
          <div className="row" style={{ marginTop: "0.75rem" }} role="status">
            <span className="spinner" />
            <span className="hint">{t("treeOptimization.counting")}</span>
          </div>
        ) : null}
        {filesToAnalyze !== null ? (
          <div className="row" style={{ flexWrap: "wrap", marginTop: "0.75rem" }} role="status">
            {filesToAnalyze === 0 ? (
              <span className="hint">{t("treeOptimization.noFiles")}</span>
            ) : (
              <>
                <span className="badge info">
                  {t("treeOptimization.filesToAnalyze", { count: filesToAnalyze })}
                </span>
                <button
                  type="button"
                  className="btn primary"
                  onClick={() => optimizeMutation.mutate()}
                  disabled={isPending || countMutation.isPending}
                >
                  {optimizeMutation.isPending ? <span className="spinner" /> : null}
                  <span>{t("treeOptimization.confirmAnalyze", { count: filesToAnalyze })}</span>
                </button>
              </>
            )}
          </div>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
      </article>

      {result ? (
        <article className="card">
          <h2 className="card-title">{t("treeOptimization.resultTitle")}</h2>
          <div className="row" style={{ flexWrap: "wrap", marginBottom: "0.75rem" }}>
            <span className="badge info">
              {t("treeOptimization.filesScanned", { count: result.files_scanned })}
            </span>
            <span className={`badge ${result.applied ? "ok" : "warn"}`}>
              {result.applied
                ? t("treeOptimization.filesModified", { count: result.files_modified })
                : t("treeOptimization.filesWithChanges", { count: result.files_with_changes })}
            </span>
            {result.applied && result.removed_elements ? (
              <span className="badge default">
                {t("treeOptimization.elementsRemoved", { count: result.removed_elements })}
              </span>
            ) : null}
            {result.files_scanned === 0 ? <span className="hint">{t("treeOptimization.noFiles")}</span> : null}
            {result.files_scanned > 0 && result.files_with_changes === 0 ? (
              <span className="hint">{t("treeOptimization.noChanges")}</span>
            ) : null}
          </div>
        </article>
      ) : null}
    </div>
  );
}