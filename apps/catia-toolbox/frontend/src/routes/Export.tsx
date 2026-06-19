import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiClientError, exportApi, exportUrl } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

export function Export() {
  const { t } = useTranslation();
  const { runId } = useWorkspace();
  const [status, setStatus] = useState("accepted");
  const [filename, setFilename] = useState("plan_lot3");
  const [kind, setKind] = useState<"csv" | "bat" | "sh">("csv");
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const saveMutation = useMutation({
    mutationFn: () => exportApi.save(runId as string, filename.trim(), kind, status),
    onSuccess: (data) => setSaveMsg({ ok: true, text: t("export.saved", { path: data.path }) }),
    onError: (e) =>
      setSaveMsg({ ok: false, text: e instanceof ApiClientError ? e.message : String(e) }),
  });

  if (!runId) {
    return (
      <div className="empty-state">
        <h3 className="card-title">{t("export.noRun")}</h3>
        <p className="hint">{t("export.noRunDesc")}</p>
      </div>
    );
  }

  return (
    <div className="form" style={{ maxWidth: "42rem" }}>
      <article className="card">
        <h2 className="card-title">{t("export.downloadTitle")}</h2>
        <p className="banner warn">
          <strong>{t("export.dryRunTitle")}</strong> {t("export.dryRunBody")}
        </p>
        <label className="field" style={{ maxWidth: "20rem" }}>
          <span className="field-label">{t("export.statusLabel")}</span>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            {[
              { value: "accepted", label: t("export.statusAccepted") },
              { value: "all", label: t("export.statusAll") },
            ].map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <a href={exportUrl.csv(runId, status)}>
            <button type="button" className="btn primary">{t("export.csv")}</button>
          </a>
          <a href={exportUrl.script(runId, "bat", status)}>
            <button type="button" className="btn secondary">{t("export.scriptBat")}</button>
          </a>
          <a href={exportUrl.script(runId, "sh", status)}>
            <button type="button" className="btn secondary">{t("export.scriptSh")}</button>
          </a>
        </div>
      </article>

      <article className="card">
        <h2 className="card-title">{t("export.saveTitle")}</h2>
        <p className="banner">{t("export.saveNotice")}</p>
        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
          <label className="field grow">
            <span className="field-label">{t("export.filename")}</span>
            <input className="input" value={filename} onChange={(e) => setFilename(e.target.value)} placeholder="plan_lot3" />
          </label>
          <label className="field">
            <span className="field-label">{t("export.format")}</span>
            <select
              className="input"
              value={kind}
              onChange={(e) => setKind(e.target.value as "csv" | "bat" | "sh")}
            >
              {[
                { value: "csv", label: "CSV" },
                { value: "bat", label: t("export.scriptBat") },
                { value: "sh", label: t("export.scriptSh") },
              ].map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="btn primary"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !filename.trim()}
          >
            {saveMutation.isPending ? <span className="spinner" /> : null}
            <span>{t("export.saveToOutput")}</span>
          </button>
        </div>
        {saveMsg ? <p className={saveMsg.ok ? "success" : "error"}>{saveMsg.text}</p> : null}
      </article>
    </div>
  );
}
