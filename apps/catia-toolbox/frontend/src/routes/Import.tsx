import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  FileDropzone,
  Input,
} from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderTree } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { ApiClientError, browseApi, importsApi, type BrowseRootsDto, type ImportDto } from "../lib/api";
import { DirectoryBrowser } from "../components/business/DirectoryBrowser";
import { useWorkspace } from "../stores/workspace";

type ScanForm = { path: string };

export function Import() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { importId, setImport } = useWorkspace();
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Set<string>>(new Set());

  const importsQuery = useQuery<ImportDto[]>({ queryKey: ["imports"], queryFn: importsApi.list });
  const rootsQuery = useQuery<BrowseRootsDto>({ queryKey: ["browse", "roots"], queryFn: browseApi.roots });

  const { register, handleSubmit, reset } = useForm<ScanForm>({ defaultValues: { path: "" } });

  const onDone = (imp: ImportDto) => {
    setError(null);
    setImport(imp.id);
    void qc.invalidateQueries({ queryKey: ["imports"] });
  };
  const onError = (e: unknown) =>
    setError(e instanceof ApiClientError ? e.message : String(e));

  const scanMutation = useMutation({
    mutationFn: (path: string) => importsApi.scan(path),
    onSuccess: (imp) => {
      onDone(imp);
      reset();
    },
    onError,
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => importsApi.upload(file),
    onSuccess: onDone,
    onError,
  });

  const selectMutation = useMutation({
    mutationFn: (paths: string[]) => importsApi.select(paths, "input"),
    onSuccess: (imp) => {
      onDone(imp);
      setSelection(new Set());
    },
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

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("import.title")}</h1>
        <p className="text-fg-dim">{t("import.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("browse.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 rounded-sm border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
            {t("import.metadataNotice")}
          </p>
          {rootsQuery.data?.input ? (
            <div className="flex flex-col gap-3">
              <DirectoryBrowser scope="input" selection={selection} onSelectionChange={setSelection} />
              <div className="flex items-center gap-2">
                <Button
                  disabled={selection.size === 0 || selectMutation.isPending}
                  onClick={() => selectMutation.mutate(Array.from(selection))}
                >
                  {t("browse.importSelection", { count: selection.size })}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setSelection(new Set())}>
                  {t("browse.clear")}
                </Button>
              </div>
            </div>
          ) : (
            <EmptyState
              icon={FolderTree}
              title={t("browse.noRootTitle")}
              description={t("browse.noRootDesc")}
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("import.scanTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 rounded-sm border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
            {t("import.metadataNotice")}
          </p>
          <form
            onSubmit={handleSubmit((v) => v.path.trim() && scanMutation.mutate(v.path.trim()))}
            className="flex flex-col gap-2"
          >
            <label htmlFor="path" className="label">
              {t("import.pathLabel")}
            </label>
            <div className="flex gap-2">
              <Input id="path" placeholder="C:\\export_catia" {...register("path")} />
              <Button type="submit" disabled={scanMutation.isPending}>
                {t("import.scan")}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("import.uploadTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <FileDropzone
            accept=".csv,.json"
            multiple={false}
            label={t("import.dropLabel")}
            description={t("import.dropDescription")}
            disabled={uploadMutation.isPending}
            onFiles={(files) => files[0] && uploadMutation.mutate(files[0])}
          />
        </CardContent>
      </Card>

      {error ? <p className="text-sm text-danger">{error}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("import.existingTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          {imports.length ? (
            <ul className="flex flex-col gap-2">
              {imports.map((imp) => (
                <li
                  key={imp.id}
                  className={[
                    "flex items-center gap-2 rounded-sm border bg-bg-2 px-3 py-2",
                    imp.id === importId ? "border-success" : "border-md",
                  ].join(" ")}
                >
                  <span className="flex-1 truncate">
                    <strong>{imp.root_label}</strong>{" "}
                    <Badge variant="info">{imp.node_count} noeuds</Badge>{" "}
                    <Badge>{imp.source_mode}</Badge>
                    {imp.id === importId ? <Badge variant="success"> courant</Badge> : null}
                  </span>
                  <Button variant="secondary" size="sm" onClick={() => setImport(imp.id)}>
                    {t("import.choose")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => deleteMutation.mutate(imp.id)}
                  >
                    {t("common.delete")}
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={FolderTree} title={t("import.emptyTitle")} description={t("import.emptyDesc")} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
