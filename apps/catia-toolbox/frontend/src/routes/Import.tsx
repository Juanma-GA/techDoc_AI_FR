import { FileDropzone } from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { FilePicker } from "../components/FilePicker";
import {
  ApiClientError,
  browseApi,
  importsApi,
  type BrowseRootsDto,
  type ImportDto,
} from "../lib/api";
import { useWorkspace } from "../stores/workspace";

type ScanForm = { path: string };

export function Import() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { importId, setImport } = useWorkspace();
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [selection, setSelection] = useState<string[]>([]);
  const [currentFolder, setCurrentFolder] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const importsQuery = useQuery<ImportDto[]>({ queryKey: ["imports"], queryFn: importsApi.list });
  const rootsQuery = useQuery<BrowseRootsDto>({ queryKey: ["browse", "roots"], queryFn: browseApi.roots });

  const { register, handleSubmit, reset } = useForm<ScanForm>({ defaultValues: { path: "" } });

  const onDone = (imp: ImportDto, message: string) => {
    setError(null);
    setFeedback(message);
    setImport(imp.id);
    void qc.invalidateQueries({ queryKey: ["imports"] });
  };
  const onError = (e: unknown) => {
    setFeedback(null);
    setError(e instanceof ApiClientError ? e.message : String(e));
  };

  const scanMutation = useMutation({
    mutationFn: (path: string) => importsApi.scan(path),
    onSuccess: (imp) => {
      onDone(imp, t("import.scanned", { count: imp.node_count }));
      reset();
    },
    onError,
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => importsApi.upload(file),
    onSuccess: (imp) => onDone(imp, t("import.listingImported", { count: imp.node_count })),
    onError,
  });

  const selectMutation = useMutation({
    mutationFn: (paths: string[]) => importsApi.select(paths, "input"),
    onSuccess: (imp) => {
      onDone(imp, t("import.imported", { count: imp.node_count }));
      setSelection([]);
    },
    onError,
  });

  const scanHereMutation = useMutation({
    mutationFn: (absPath: string) => importsApi.scan(absPath),
    onSuccess: (imp) => onDone(imp, t("import.scanned", { count: imp.node_count })),
    onError,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => importsApi.remove(id),
    onSuccess: (_d, id) => {
      if (importId === id) setImport(null);
      void qc.invalidateQueries({ queryKey: ["imports"] });
    },
  });

  const imports = importsQuery.data ?? [];
  const browserBusy = selectMutation.isPending || scanHereMutation.isPending;

  return (
    <div className="grow form" style={{ maxWidth: "48rem" }}>
      {/* ---- Action principale : naviguer la Source et choisir ----------------- */}
      <article className="card">
        <h2 className="card-title">{t("browse.title")}</h2>
        <p className="banner warn">{t("import.metadataNotice")}</p>
        {rootsQuery.data?.input ? (
          <div className="form">
            <FilePicker
              mode="multi"
              exts={[]}
              value={selection}
              onChange={setSelection}
              onFolderChange={setCurrentFolder}
            />
            <div className="row">
              <button
                type="button"
                className="btn primary"
                disabled={selection.length === 0 || browserBusy}
                onClick={() => {
                  if (selection.length === 0) {
                    setError(t("import.nothingSelected"));
                    return;
                  }
                  selectMutation.mutate(selection);
                }}
              >
                {t("browse.importSelection", { count: selection.length })}
              </button>
              <button
                type="button"
                className="btn secondary"
                disabled={browserBusy || !currentFolder}
                onClick={() => scanHereMutation.mutate(currentFolder)}
              >
                {t("import.scanHere")}
              </button>
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <h3 className="card-title">{t("browse.noRootTitle")}</h3>
            <p className="hint">{t("browse.noRootDesc")}</p>
          </div>
        )}
        {feedback ? <p className="success">{feedback}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </article>

      {/* ---- Options avancees : scan par chemin + import d'un listing --------- */}
      <article className="card">
        <button
          type="button"
          className="btn ghost"
          style={{ width: "100%", justifyContent: "flex-start" }}
          onClick={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced ? <ChevronDown className="mr-1 h-4 w-4" /> : <ChevronRight className="mr-1 h-4 w-4" />}
          {t("import.advancedTitle")}
        </button>

        {showAdvanced ? (
          <div className="form" style={{ marginTop: "0.75rem" }}>
            <form
              onSubmit={handleSubmit((v) => {
                const p = v.path.trim();
                if (!p) {
                  setError(t("import.pathRequired"));
                  return;
                }
                scanMutation.mutate(p);
              })}
              className="form"
            >
              <label htmlFor="path" className="field-label">
                {t("import.pathLabel")}
              </label>
              <div className="row">
                <input className="input grow" id="path" placeholder="C:\\chemin\\vers\\export_catia" {...register("path")} />
                <button type="submit" className="btn secondary" disabled={scanMutation.isPending}>
                  {t("import.scan")}
                </button>
              </div>
            </form>

            <div className="field">
              <span className="field-label">{t("import.uploadTitle")}</span>
              <FileDropzone
                accept=".csv,.json"
                multiple={false}
                label={t("import.dropLabel")}
                description={t("import.dropDescription")}
                disabled={uploadMutation.isPending}
                onFiles={(files) => files[0] && uploadMutation.mutate(files[0])}
              />
            </div>
          </div>
        ) : null}
      </article>

      {/* ---- Imports existants ------------------------------------------------ */}
      <article className="card">
        <h2 className="card-title">{t("import.existingTitle")}</h2>
        {imports.length ? (
          <ul className="item-list">
            {imports.map((imp) => (
              <li key={imp.id} className={imp.id === importId ? "item-row clickable" : "item-row"}>
                <span className="item-main">
                  <strong>{imp.root_label}</strong>{" "}
                  <span className="badge info">{t("import.nodeCount", { count: imp.node_count })}</span>{" "}
                  <span className="badge default">{imp.source_mode}</span>
                  {imp.id === importId ? (
                    <>
                      {" "}
                      <span className="badge ok">{t("import.current")}</span>
                    </>
                  ) : null}
                </span>
                <div className="item-actions">
                  <button type="button" className="btn secondary small" onClick={() => setImport(imp.id)}>
                    {t("import.choose")}
                  </button>
                  <button type="button" className="btn ghost small" onClick={() => deleteMutation.mutate(imp.id)}>
                    {t("common.delete")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty-state">
            <h3 className="card-title">{t("import.emptyTitle")}</h3>
            <p className="hint">{t("import.emptyDesc")}</p>
          </div>
        )}
      </article>
    </div>
  );
}
