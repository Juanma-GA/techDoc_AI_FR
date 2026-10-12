import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Palette } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { FilePicker } from "../components/FilePicker";
import {
  ApiClientError,
  colorizationApi,
  identificationApi,
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
  const piecesRoot = useWorkspace((state) => state.sources.smgxmlFolder);
  const profilesRoot = useWorkspace((state) => state.sources.profilesRoot);
  const preferredRunId = useWorkspace((state) => state.nomenclatureRunId);
  const setSource = useWorkspace((state) => state.setSource);
  const [runId, setRunId] = useState(preferredRunId ?? "");
  const [apply, setApply] = useState(false);
  const [armed, setArmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      setError(cause instanceof ApiClientError ? cause.message : String(cause));
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
      <article className="card">
        <h2 className="card-title">{t("colorization.title")}</h2>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="colorization-nomenclature" className="field-label">
              {t("colorization.nomenLabel")}
            </label>
            <select
              id="colorization-nomenclature"
              className="input"
              value={runId}
              onChange={(event) => setRunId(event.target.value)}
              disabled={runsQuery.isLoading}
            >
              <option value="">{t("colorization.nomenEmpty")}</option>
              {runs.map((run) => (
                <option key={run.id} value={run.id}>{fileName(run.source_ref)}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="field-label">{t("colorization.selectionSummary", {
              parts: monoParts.length,
              oldPns: distinctOldPns.size,
            })}</span>
            {monoPartsQuery.isLoading ? <span className="spinner" /> : null}
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
            <span className="field-label">{t("colorization.piecesRoot")}</span>
            <FilePicker
              mode="folder"
              exts={[]}
              value={piecesRoot}
              onChange={(path) => setSource("smgxmlFolder", path)}
            />
          </div>
          <div className="field">
            <span className="field-label">{t("colorization.profilesRoot")}</span>
            <FilePicker
              mode="folder"
              exts={[]}
              value={profilesRoot}
              onChange={(path) => setSource("profilesRoot", path)}
            />
          </div>
        </div>

        <label className="checkbox">
          <input type="checkbox" checked={apply} onChange={(event) => setApply(event.target.checked)} />
          <span>{t("colorization.apply")}</span>
        </label>

        <div className="row">
          <button
            type="button"
            className="btn primary"
            onClick={onRun}
            disabled={colorizeMutation.isPending || !canRun}
          >
            {colorizeMutation.isPending ? <span className="spinner" /> : <Palette className="h-4 w-4" />}
            <span>{armed ? t("colorization.confirmWrite") : t("colorization.launch")}</span>
          </button>
          {error ? <span className="error">{error}</span> : null}
        </div>
      </article>

      {result ? (
        <article className="card">
          <h2 className="card-title">{t("colorization.resultsTitle")}</h2>
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
                        <span className={item.status === "applied" || item.status === "planned" ? "badge ok" : "badge warn"}>
                          {statusLabel(item.status)}
                        </span>
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
        </article>
      ) : null}
    </div>
  );
}