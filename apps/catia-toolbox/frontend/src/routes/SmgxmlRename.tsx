import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  smgxmlApi,
  type RenamePair,
  type SmgxmlRunDto,
} from "../lib/api";
import { FilePicker } from "../components/FilePicker";
import { useWorkspace } from "../stores/workspace";

const SMGXML_EXTS = [".smgxml", ".smg", ".xml"];
const CONFIRM_MS = 3000;

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
