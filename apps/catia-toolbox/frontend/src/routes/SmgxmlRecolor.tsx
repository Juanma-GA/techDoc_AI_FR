import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  identificationApi,
  smgxmlApi,
  type NomenclatureRunDto,
  type SmgxmlChangeDto,
  type SmgxmlRunDto,
} from "../lib/api";
import { FilePicker } from "../components/FilePicker";
import { useWorkspace } from "../stores/workspace";

const SMGXML_EXTS = [".smgxml", ".smg", ".xml"];

function fileName(ref: string): string {
  return (ref || "").split(/[\\/]/).pop() ?? "";
}

function monoCount(run: NomenclatureRunDto): number {
  const v = run.summary.mono_color;
  return typeof v === "number" ? v : 0;
}

export function SmgxmlRecolor() {
  const { t } = useTranslation();

  // Chemin SMGXML partage entre Recolor et Rename (memorise dans le workspace).
  const path = useWorkspace((s) => s.sources.smgxml);
  const setSource = useWorkspace((s) => s.setSource);
  const setPath = (p: string) => setSource("smgxml", p);
  const [nomenId, setNomenId] = useState("");
  const [matchBy, setMatchBy] = useState<"sin" | "catpart">("sin");
  const [apply, setApply] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<SmgxmlRunDto | null>(null);

  const [armed, setArmed] = useState(false);
  const armTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const nomenQuery = useQuery<NomenclatureRunDto[]>({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
  });
  const runs = nomenQuery.data ?? [];

  const changesQuery = useQuery<SmgxmlChangeDto[]>({
    queryKey: ["smgxml", result?.id, "changes"],
    queryFn: () => smgxmlApi.changes(result!.id),
    enabled: !!result,
  });

  const disarm = () => {
    if (armTimer.current) clearTimeout(armTimer.current);
    armTimer.current = null;
    setArmed(false);
  };

  const recolorMutation = useMutation({
    mutationFn: () =>
      smgxmlApi.recolor({
        scope: "input",
        path: path.trim(),
        nomenclature_run_id: nomenId,
        match_by: matchBy,
        apply,
      }),
    onSuccess: (run) => {
      disarm();
      setError(null);
      setResult(run);
      const changes = run.summary.changes ?? 0;
      setNotice(
        run.applied
          ? t("smgxml.applied", { count: changes })
          : t("smgxml.dryRunDone", { count: changes }),
      );
    },
    onError: (e: unknown) => {
      disarm();
      setNotice(null);
      setError(e instanceof ApiClientError ? e.message : String(e));
    },
  });

  const launch = () => {
    setNotice(null);
    if (!path.trim()) {
      setError(t("smgxml.pathRequired"));
      return;
    }
    if (!nomenId) {
      setError(t("smgxmlRecolor.nomenRequired"));
      return;
    }
    setError(null);
    // Ecriture = action a confirmer (double-clic).
    if (apply && !armed) {
      setArmed(true);
      armTimer.current = setTimeout(() => {
        armTimer.current = null;
        setArmed(false);
      }, 3000);
      return;
    }
    disarm();
    recolorMutation.mutate();
  };

  const changes = changesQuery.data ?? [];

  return (
    <div className="form" style={{ maxWidth: "48rem" }}>
      <article className="card">
        <h2 className="card-title">{t("smgxmlRecolor.title")}</h2>
        <p className="banner warn">{t("smgxmlRecolor.banner")}</p>
        <div className="form">
          <div className="field">
            <label className="field-label">{t("smgxml.fileLabel")}</label>
            <FilePicker exts={SMGXML_EXTS} value={path} onChange={setPath} />
          </div>

          <div className="row">
            <div className="grow field">
              <label htmlFor="smg-nomen" className="field-label">
                {t("smgxmlRecolor.nomenLabel")}
              </label>
              <select
                className="input"
                id="smg-nomen"
                value={nomenId}
                onChange={(e) => setNomenId(e.target.value)}
              >
                {(runs.length
                  ? runs.map((r) => ({
                      value: r.id,
                      label: t("smgxmlRecolor.nomenOption", {
                        name: fileName(r.source_ref),
                        mono: monoCount(r),
                      }),
                    }))
                  : [{ value: "", label: t("smgxmlRecolor.nomenEmpty") }]
                ).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="smg-match" className="field-label">
                {t("smgxmlRecolor.matchLabel")}
              </label>
              <select
                className="input"
                id="smg-match"
                value={matchBy}
                onChange={(e) => setMatchBy(e.target.value as "sin" | "catpart")}
              >
                {[
                  { value: "sin", label: t("smgxmlRecolor.matchBySin") },
                  { value: "catpart", label: t("smgxmlRecolor.matchByCatpart") },
                ].map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <label className="checkbox">
            <input
              type="checkbox"
              id="smg-apply"
              checked={apply}
              onChange={(e) => {
                setApply(e.target.checked);
                disarm();
              }}
              aria-label={t("smgxml.apply")}
            />
            <span>{t("smgxml.apply")}</span>
          </label>

          <div className="row">
            <button type="button" className="btn primary" onClick={launch} disabled={recolorMutation.isPending}>
              {recolorMutation.isPending ? <span className="spinner" /> : null}
              <span>{armed ? t("smgxml.confirmWrite") : t("common.launch")}</span>
            </button>
            {notice ? <span className="success">{notice}</span> : null}
            {error ? <span className="error">{error}</span> : null}
          </div>
        </div>

        {result ? (
          <div className="form" style={{ marginTop: "1rem" }}>
            {result.applied ? (
              <p className="banner success">
                {t("smgxml.appliedBanner", {
                  path: result.backup_path || t("smgxml.noBackup"),
                })}
              </p>
            ) : (
              <p className="banner warn">
                {t("smgxml.dryRunBanner", { count: result.summary.changes ?? 0 })}
              </p>
            )}

            {changesQuery.isLoading ? (
              <span className="spinner" />
            ) : changes.length ? (
              <div style={{ overflow: "auto" }}>
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
                    {changes.slice(0, 200).map((c) => (
                      <tr key={c.id}>
                        <td>{c.target}</td>
                        <td>{c.change_type}</td>
                        <td>{c.old_value}</td>
                        <td>{c.new_value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <h3 className="card-title">{t("smgxml.noChange")}</h3>
              </div>
            )}
          </div>
        ) : null}
      </article>
    </div>
  );
}
