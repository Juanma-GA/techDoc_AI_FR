import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  identificationApi,
  smgxmlApi,
  type NomenclatureRunDto,
  type RenamePair,
  type SmgxmlBatchDto,
  type SmgxmlRunDto,
} from "../lib/api";
import { FilePicker } from "../components/FilePicker";
import { useWorkspace } from "../stores/workspace";

const SMGXML_EXTS = [".smgxml", ".smg", ".xml"];
const CONFIRM_MS = 3000;

function fileName(ref: string): string {
  return (ref || "").split(/[\\/]/).pop() ?? "";
}

/**
 * Renommage EN MASSE (etape 4) : a partir d'un run de nomenclature, traite
 * toutes les pieces remplacees. Deux dossiers (racine COMPOSER + PIECES
 * CONVERTIES) memorises dans le workspace. Dry-run par defaut, apply en
 * double-clic. Le rapport liste chaque piece + son statut.
 */
function BatchRenameCard() {
  const { t } = useTranslation();
  const composerRoot = useWorkspace((s) => s.sources.composerRoot);
  const convertedRoot = useWorkspace((s) => s.sources.convertedRoot);
  const setSource = useWorkspace((s) => s.setSource);
  const [nomenId, setNomenId] = useState("");
  const [apply, setApply] = useState(false);
  const [armed, setArmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SmgxmlBatchDto | null>(null);

  const runsQuery = useQuery<NomenclatureRunDto[]>({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
  });
  const runs = runsQuery.data ?? [];

  const batchMutation = useMutation({
    mutationFn: () =>
      smgxmlApi.batchRename({
        composer_root: composerRoot.trim(),
        converted_root: convertedRoot.trim(),
        nomenclature_run_id: nomenId,
        apply,
      }),
    onSuccess: (data) => {
      setArmed(false);
      setError(null);
      setResult(data);
    },
    onError: (e) => {
      setArmed(false);
      setError(e instanceof ApiClientError ? e.message : String(e));
    },
  });

  const canRun = !!composerRoot.trim() && !!convertedRoot.trim() && !!nomenId;

  const onRun = () => {
    if (!canRun) {
      setError(t("smgxmlRename.batchRequired"));
      return;
    }
    setError(null);
    if (apply && !armed) {
      setArmed(true);
      window.setTimeout(() => setArmed(false), CONFIRM_MS);
      return;
    }
    batchMutation.mutate();
  };

  const statusLabel = (s: string) => t(`smgxmlRename.status.${s}`, { defaultValue: s });

  return (
    <article className="card">
      <h2 className="card-title">{t("smgxmlRename.batchTitle")}</h2>

      <div className="form">
        <div className="field">
          <span className="field-label">{t("smgxmlRename.composerRoot")}</span>
          <FilePicker mode="folder" exts={[]} value={composerRoot} onChange={(p) => setSource("composerRoot", p)} />
        </div>
        <div className="field">
          <span className="field-label">{t("smgxmlRename.convertedRoot")}</span>
          <FilePicker mode="folder" exts={[]} value={convertedRoot} onChange={(p) => setSource("convertedRoot", p)} />
        </div>

        <div className="field">
          <label htmlFor="batch-nomen" className="field-label">{t("smgxmlRecolor.nomenLabel")}</label>
          <select id="batch-nomen" className="input" value={nomenId} onChange={(e) => setNomenId(e.target.value)}>
            <option value="">{t("smgxmlRecolor.nomenEmpty")}</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>{fileName(r.source_ref)}</option>
            ))}
          </select>
        </div>

        <label className="checkbox">
          <input type="checkbox" checked={apply} onChange={(e) => setApply(e.target.checked)} />
          <span>{t("smgxml.apply")}</span>
        </label>

        <div className="row">
          <button type="button" className="btn primary" onClick={onRun} disabled={batchMutation.isPending || !canRun}>
            {batchMutation.isPending ? <span className="spinner" /> : null}
            <span>{armed ? t("smgxml.confirmWrite") : t("smgxmlRename.batchLaunch")}</span>
          </button>
          {error ? <span className="error">{error}</span> : null}
        </div>
      </div>

      {result ? (
        <div className="form" style={{ marginTop: "1rem" }}>
          <p className={result.summary.applied ? "banner success" : "banner warn"}>
            {t("smgxmlRename.batchSummary", {
              total: result.summary.total ?? 0,
              ok: result.summary.ok ?? 0,
              skipped: result.summary.skipped ?? 0,
            })}
          </p>
          <div style={{ overflow: "auto" }}>
            <table className="tbl" style={{ whiteSpace: "nowrap" }}>
              <thead>
                <tr>
                  <th>{t("identification.colSin")}</th>
                  <th>{t("smgxmlRename.colOld")}</th>
                  <th>{t("smgxmlRename.colNew")}</th>
                  <th>{t("smgxmlRename.colReplacements")}</th>
                  <th>{t("smgxmlRename.colStatus")}</th>
                </tr>
              </thead>
              <tbody>
                {result.items.map((it, i) => (
                  <tr key={i}>
                    <td>{it.sin}</td>
                    <td>{it.old_stem || it.old_pn}</td>
                    <td>{it.new_stem || it.new_pn}</td>
                    <td style={{ textAlign: "center" }}>{it.replacements}</td>
                    <td>
                      <span className={it.status === "ok" ? "badge ok" : "badge warn"}>
                        {statusLabel(it.status)}
                      </span>
                      {it.applied ? <span className="badge default" style={{ marginLeft: 4 }}>{t("smgxmlRename.doneBadge")}</span> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </article>
  );
}

/** Reproduit parseRenameMap du preview : une paire {old,new} par ligne "ancien=nouveau". */
function parseRenameMap(text: string): RenamePair[] {
  const out: RenamePair[] = [];
  text.split(/\n/).forEach((line) => {
    const m = line.split(/=|;/);
    if (m.length >= 2 && m[0]!.trim() && m[1]!.trim()) {
      out.push({ old: m[0]!.trim(), new: m.slice(1).join("=").trim() });
    }
  });
  return out;
}

/** Tableau des changements d'un run SMGXML + banniere dry-run / applique (showSmgxmlResult). */
function SmgxmlResult({ run }: { run: SmgxmlRunDto }) {
  const { t } = useTranslation();
  const changesQuery = useQuery({
    queryKey: ["smgxml", run.id, "changes"],
    queryFn: () => smgxmlApi.changes(run.id),
  });
  const changes = (changesQuery.data ?? []).slice(0, 200);

  return (
    <div className="form" style={{ marginTop: "1rem" }}>
      {run.applied ? (
        <p className="banner">
          {t("smgxml.appliedBanner", { path: run.backup_path || t("smgxml.noBackup") })}
        </p>
      ) : (
        <p className="banner warn">
          {t("smgxml.dryRunBanner", { count: run.summary.changes ?? 0 })}
        </p>
      )}

      {changesQuery.isLoading ? (
        <span className="spinner" />
      ) : changes.length ? (
        <table className="tbl">
          <thead>
            <tr>
              <th>{t("smgxml.colTarget")}</th>
              <th>{t("smgxml.colType")}</th>
              <th>{t("smgxml.colBefore")}</th>
              <th>{t("smgxml.colAfter")}</th>
            </tr>
          </thead>
          <tbody>
            {changes.map((c) => (
              <tr key={c.id}>
                <td>{c.target}</td>
                <td>{c.change_type}</td>
                <td>{c.old_value}</td>
                <td>{c.new_value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="empty-state">
          <h3 className="card-title">{t("smgxml.noChange")}</h3>
        </div>
      )}
    </div>
  );
}

export function SmgxmlRename() {
  const { t } = useTranslation();

  // Chemin SMGXML partage entre Recolor et Rename (memorise dans le workspace).
  const path = useWorkspace((s) => s.sources.smgxml);
  const setSource = useWorkspace((s) => s.setSource);
  const setPath = (p: string) => setSource("smgxml", p);
  const [mappingText, setMappingText] = useState("");
  const [apply, setApply] = useState(false);
  const [armed, setArmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [result, setResult] = useState<SmgxmlRunDto | null>(null);

  const renameMutation = useMutation({
    mutationFn: (mapping: RenamePair[]) =>
      smgxmlApi.rename({ scope: "input", path: path.trim(), mapping, apply }),
    onSuccess: (run) => {
      setArmed(false);
      setError(null);
      setFeedback(
        run.applied
          ? t("smgxml.applied", { count: run.summary.changes ?? 0 })
          : t("smgxml.dryRunDone", { count: run.summary.changes ?? 0 }),
      );
      setResult(run);
    },
    onError: (e) => {
      setArmed(false);
      setFeedback(null);
      setError(e instanceof ApiClientError ? e.message : String(e));
    },
  });

  const onRun = () => {
    setFeedback(null);
    if (!path.trim()) {
      setError(t("smgxml.pathRequired"));
      return;
    }
    const mapping = parseRenameMap(mappingText);
    if (!mapping.length) {
      setError(t("smgxmlRename.mappingRequired"));
      return;
    }
    setError(null);
    // Ecriture = action a confirmer (double-clic).
    if (apply && !armed) {
      setArmed(true);
      window.setTimeout(() => setArmed(false), CONFIRM_MS);
      return;
    }
    renameMutation.mutate(mapping);
  };

  return (
    <div className="form" style={{ maxWidth: "48rem" }}>
      <BatchRenameCard />

      <article className="card">
        <h2 className="card-title">{t("smgxmlRename.title")}</h2>
        <p className="banner warn">{t("smgxmlRename.banner")}</p>

        <div className="form">
          <div className="field">
            <span className="field-label">{t("smgxml.fileLabel")}</span>
            <FilePicker exts={SMGXML_EXTS} value={path} onChange={setPath} />
          </div>

          <div className="field">
            <label htmlFor="smg_map" className="field-label">
              {t("smgxmlRename.mappingLabel")}
            </label>
            <textarea
              id="smg_map"
              className="input"
              rows={6}
              placeholder="LEAP_U320_n-1.CATPart=LEAP_U320_n.CATPart"
              value={mappingText}
              onChange={(e) => setMappingText(e.target.value)}
            />
          </div>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={apply}
              onChange={(e) => setApply(e.target.checked)}
            />
            <span>{t("smgxml.apply")}</span>
          </label>

          <div className="row">
            <button type="button" className="btn primary" onClick={onRun} disabled={renameMutation.isPending}>
              {renameMutation.isPending ? <span className="spinner" /> : null}
              <span>{armed ? t("smgxml.confirmWrite") : t("common.launch")}</span>
            </button>
            {feedback ? <span className="success">{feedback}</span> : null}
            {error ? <span className="error">{error}</span> : null}
          </div>
        </div>

        {result ? <SmgxmlResult run={result} /> : null}
      </article>
    </div>
  );
}
