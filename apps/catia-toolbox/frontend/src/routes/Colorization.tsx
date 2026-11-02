import { Badge, Button, Checkbox, Input, Select, Spinner } from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Palette } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { FilePicker } from "../components/FilePicker";
import {
  ApiClientError,
  browseApi,
  colorizationApi,
  identificationApi,
  treeOptimizationApi,
  type MonoBodyColorizationDto,
  type NomenclatureItemDto,
  type NomenclatureRunDto,
} from "../lib/api";
import { useWorkspace } from "../stores/workspace";

const CONFIRM_MS = 3000;
const RESULT_LIMIT = 200;

function fileName(ref: string): string {
  return (ref || "").split(/[\\/]/).pop() ?? "";
}

export function Colorization() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const piecesRoot = useWorkspace((state) => state.sources.optimizedPiecesRoot);
  const profilesRoot = useWorkspace((state) => state.sources.profilesRoot);
  const preferredRunId = useWorkspace((state) => state.nomenclatureRunId);
  const setSource = useWorkspace((state) => state.setSource);
  const rootsQuery = useQuery({ queryKey: ["browse", "roots"], queryFn: browseApi.roots });
  const hasInputRoot = Boolean(rootsQuery.data?.input);
  const [runId, setRunId] = useState(preferredRunId ?? "");
  const [apply, setApply] = useState(false);
  const [armed, setArmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profilesPickerError, setProfilesPickerError] = useState<string | null>(null);
  const [result, setResult] = useState<MonoBodyColorizationDto | null>(null);

  const runsQuery = useQuery<NomenclatureRunDto[]>({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
  });
  const runs = runsQuery.data ?? [];
  const monoPartsQuery = useQuery<NomenclatureItemDto[]>({
    queryKey: ["identification", runId, "colorization-mono-body"],
    queryFn: () => identificationApi.items(runId, { monoBody: true }),
    enabled: !!runId,
  });
  const monoParts = monoPartsQuery.data ?? [];
  const distinctOldPns = new Set(monoParts.map((item) => item.old_pn.trim()).filter(Boolean));
  const missingProfiles = monoParts.filter((item) => !item.mono_texture.trim()).length;
  const pickProfilesFolderMutation = useMutation({
    mutationFn: () =>
      treeOptimizationApi.pickFolder(profilesRoot.trim() || undefined, t("colorization.profilesRoot")),
    onSuccess: ({ path }) => {
      if (!path) return;
      setSource("profilesRoot", path);
      setProfilesPickerError(null);
    },
    onError: (reason: unknown) =>
      setProfilesPickerError(reason instanceof Error ? reason.message : String(reason)),
  });
  const displayError = (reason: unknown) =>
    reason instanceof ApiClientError && reason.code === "PIECES_FOLDER_CONTENT_INVALID"
      ? t("colorization.invalidFolderContents")
      : reason instanceof Error
        ? reason.message
        : String(reason);

  useEffect(() => {
    if (preferredRunId) setRunId(preferredRunId);
  }, [preferredRunId]);

  useEffect(() => {
    setResult(null);
    setError(null);
    setArmed(false);
  }, [runId, piecesRoot, profilesRoot]);

  const colorizeMutation = useMutation({
    mutationFn: () =>
      colorizationApi.monoBody({
        scope: "input",
        pieces_root: piecesRoot.trim(),
        profiles_root: profilesRoot.trim(),
        nomenclature_run_id: runId,
        apply,
      }),
    onSuccess: (data) => {
      setArmed(false);
      setError(null);
      setResult(data);
      if (data.summary.applied) {
        void queryClient.invalidateQueries({ queryKey: ["identification", runId] });
      }
    },
    onError: (cause) => {
      setArmed(false);
      setError(displayError(cause));
    },
  });

  const canRun =
    !!piecesRoot.trim() &&
    !!profilesRoot.trim() &&
    !!runId &&
    monoPartsQuery.isSuccess &&
    monoParts.length > 0 &&
    missingProfiles === 0;

  const onRun = () => {
    if (!canRun) {
      setError(t("colorization.required"));
      return;
    }
    setError(null);
    if (apply && !armed) {
      setArmed(true);
      window.setTimeout(() => setArmed(false), CONFIRM_MS);
      return;
    }
    colorizeMutation.mutate();
  };

  const resultRows = result?.items.slice(0, RESULT_LIMIT) ?? [];
  const statusLabel = (status: string) => t(`colorization.statusLabel.${status}`, { defaultValue: status });

  return (
    <div className="form">
      <section className="workflow-section">
        <h2 className="section-title">{t("colorization.title")}</h2>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="colorization-nomenclature" className="field-label">
              {t("colorization.nomenLabel")}
            </label>
            <Select options={[]}
              id="colorization-nomenclature"

              value={runId}
              onChange={(event) => setRunId(event.target.value)}
              disabled={runsQuery.isLoading}
            >
              <option value="">{t("colorization.nomenEmpty")}</option>
              {runs.map((run) => (
                <option key={run.id} value={run.id}>{fileName(run.source_ref)}</option>
              ))}
            </Select>
          </div>
          <div className="field">
            <span className="field-label">{t("colorization.selectionSummary", {
              parts: monoParts.length,
              oldPns: distinctOldPns.size,
            })}</span>
            {monoPartsQuery.isLoading ? <Spinner aria-label={t("common.loading")} /> : null}
            {runId && monoPartsQuery.isSuccess && monoParts.length === 0 ? (
              <p className="hint">{t("colorization.noMonoParts")}</p>
            ) : null}
            {missingProfiles > 0 ? (
              <p className="error">{t("colorization.missingProfiles", { count: missingProfiles })}</p>
            ) : null}
          </div>
        </div>

        <div className="grid-2">
          <div className="field">
            <label htmlFor="colorization-pieces-root" className="field-label">
              {t("colorization.piecesRoot")}
            </label>
            <Input
              id="colorization-pieces-root"

              value={piecesRoot}
              readOnly
            />
            {!piecesRoot ? <p className="hint" role="status">{t("colorization.required")}</p> : null}
          </div>
          <div className="field">
            <span className="field-label">{t("colorization.profilesRoot")}</span>
            {rootsQuery.isLoading ? (
              <Spinner aria-label={t("common.loading")} />
            ) : rootsQuery.isError ? (
              <p className="error" role="alert">
                {rootsQuery.error instanceof Error ? rootsQuery.error.message : String(rootsQuery.error)}
              </p>
            ) : hasInputRoot ? (
              <FilePicker
                mode="folder"
                exts={[]}
                value={profilesRoot}
                onChange={(path) => setSource("profilesRoot", path)}
              />
            ) : (
              <>
                <div className="row">
                  <Input
                    type="text"
                    className="grow"
                    aria-label={t("colorization.profilesRoot")}
                    placeholder={t("picker.folderPlaceholder")}
                    value={profilesRoot}
                    onChange={(event) => setSource("profilesRoot", event.target.value)}
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => pickProfilesFolderMutation.mutate()}
                    disabled={pickProfilesFolderMutation.isPending}
                  >
                    {pickProfilesFolderMutation.isPending ? (
                      <Spinner aria-label={t("common.loading")} />
                    ) : null}
                    <span>{t("picker.browse")}</span>
                  </Button>
                </div>
                <p className="hint">{t("treeOptimization.noInputRootHint")}</p>
                {profilesPickerError ? (
                  <p className="error" role="alert">{profilesPickerError}</p>
                ) : null}
              </>
            )}
          </div>
        </div>

        <label className="checkbox">
          <Checkbox  checked={apply} onCheckedChange={(checked) => setApply(checked)} />
          <span>{t("colorization.apply")}</span>
        </label>

        <div className="row colorization-actions">
          <Button
            type="button"
            variant="primary"
            onClick={onRun}
            disabled={colorizeMutation.isPending || !canRun}
          >
            {colorizeMutation.isPending ? <Spinner aria-label={t("common.loading")} /> : <Palette className="h-4 w-4" />}
            <span>{armed ? t("colorization.confirmWrite") : t("colorization.launch")}</span>
          </Button>
          {error ? <span className="error">{error}</span> : null}
        </div>
      </section>

      {result ? (
        <section className="workflow-section">
          <h2 className="section-title">{t("colorization.resultsTitle")}</h2>
          <p className={result.summary.applied ? "banner success" : "banner warn"}>
            {t("colorization.summary", {
              files: result.summary.files_found ?? 0,
              changed: result.summary.files_changed ?? 0,
              actors: result.summary.actors_changed ?? 0,
              skipped: result.summary.skipped ?? 0,
            })}
          </p>
          {resultRows.length ? (
            <div style={{ overflow: "auto" }}>
              <table className="tbl" style={{ whiteSpace: "nowrap" }}>
                <thead>
                  <tr>
                    <th>{t("identification.colOldPn")}</th>
                    <th>{t("colorization.profile")}</th>
                    <th>{t("colorization.file")}</th>
                    <th>{t("colorization.actors")}</th>
                    <th>{t("colorization.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {resultRows.map((item, index) => (
                    <tr key={`${item.path}-${index}`}>
                      <td>{item.old_pn}</td>
                      <td>{item.texture_ref}</td>
                      <td title={item.path}>{fileName(item.path)}</td>
                      <td>{item.actors_changed}/{item.actors_total}</td>
                      <td>
                        <Badge variant={item.status === "applied" || item.status === "planned" ? "success" : "warning"}>
                          {statusLabel(item.status)}
                        </Badge>
                        {item.message ? <span className="hint"> {item.message}</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="hint">{t("colorization.noFiles")}</p>
          )}
          {result.items.length > RESULT_LIMIT ? (
            <p className="hint">{t("colorization.resultsLimit", { shown: RESULT_LIMIT, total: result.items.length })}</p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
