import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Wand2 } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { streamOptimize, suggestionsApi, type SuggestionDto } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

const CONF_VARIANT: Record<string, "ok" | "warn" | "danger"> = {
  elevee: "ok",
  moyenne: "warn",
  faible: "danger",
};
const STATUS_VARIANT: Record<string, "ok" | "warn" | "danger"> = {
  accepted: "ok",
  pending: "warn",
  rejected: "danger",
};

export function Suggestions() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { importId, runId, setRun } = useWorkspace();
  const [maxDepth, setMaxDepth] = useState(5);
  const [useLlm, setUseLlm] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);

  const suggestionsQuery = useQuery<SuggestionDto[]>({
    queryKey: ["suggestions", runId],
    queryFn: () => suggestionsApi.list(runId as string),
    enabled: !!runId,
  });

  if (!importId) {
    return (
      <div className="empty-state">
        <Wand2 size={28} aria-hidden="true" />
        <h3 className="card-title">{t("suggestions.noImport")}</h3>
        <p className="hint">{t("tree.noImportDesc")}</p>
      </div>
    );
  }

  const launch = () => {
    setError(null);
    setOutput("");
    setStreaming(true);
    cancelRef.current = streamOptimize(
      importId,
      { target_max_depth: maxDepth, use_llm: useLlm },
      {
        onSession: (d) => setRun(d.run_id),
        onToken: (d) => setOutput((o) => o + d),
        onDone: () => {
          setStreaming(false);
          void qc.invalidateQueries({ queryKey: ["suggestions"] });
        },
        onError: (m) => {
          setStreaming(false);
          setError(m);
        },
      },
    );
  };

  const setStatus = async (id: string, status: string) => {
    await suggestionsApi.setStatus(id, status);
    void qc.invalidateQueries({ queryKey: ["suggestions", runId] });
  };

  const bulk = async (status: string) => {
    const items = suggestionsQuery.data ?? [];
    if (!items.length) return;
    await suggestionsApi.bulkStatus(items.map((s) => s.id), status);
    void qc.invalidateQueries({ queryKey: ["suggestions", runId] });
  };

  const suggestions = suggestionsQuery.data ?? [];

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <article className="card">
        <h2 className="card-title">{t("suggestions.generateTitle")}</h2>
        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
          <label className="field">
            <span className="field-label">{t("suggestions.maxDepth")}</span>
            <input
              className="input"
              type="number"
              min={1}
              max={20}
              value={maxDepth}
              onChange={(e) => setMaxDepth(Number(e.target.value) || 5)}
              style={{ width: 96 }}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={useLlm}
              onChange={(e) => setUseLlm(e.target.checked)}
              aria-label={t("suggestions.useLlm")}
            />
            {t("suggestions.useLlm")}
          </label>
          <button type="button" className="btn primary" onClick={launch} disabled={streaming}>
            {streaming ? t("suggestions.running") : t("suggestions.launch")}
          </button>
        </div>
        {streaming || output ? (
          <pre className="mt-3 max-h-56 overflow-y-auto whitespace-pre-wrap rounded-sm border bg-bg-2 p-3 font-mono text-sm">
            {output}
          </pre>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
      </article>

      <article className="card">
        <h2 className="card-title">
          <span className="row" style={{ justifyContent: "space-between" }}>
            <span>{t("suggestions.listTitle")}</span>
            <span className="row">
              <button type="button" className="btn secondary small" onClick={() => bulk("accepted")}>
                {t("suggestions.acceptAll")}
              </button>
              <button type="button" className="btn ghost small" onClick={() => bulk("rejected")}>
                {t("suggestions.rejectAll")}
              </button>
            </span>
          </span>
        </h2>
        {suggestions.length ? (
          <ul className="item-list">
            {suggestions.map((s) => (
              <li
                key={s.id}
                className="item-row"
                style={s.status === "rejected" ? { opacity: 0.6 } : undefined}
              >
                <div className="break-all font-mono text-sm">
                  {s.old_path} <span className="brand-color">&rarr;</span> {s.new_path}
                </div>
                <div className="row" style={{ flexWrap: "wrap", marginTop: 4 }}>
                  <span className="badge info">{t(`suggestions.action.${s.action}`)}</span>
                  <span className="badge default">{s.source}</span>
                  <span className={`badge ${CONF_VARIANT[s.confidence]}`}>{s.confidence}</span>
                  <span className={`badge ${STATUS_VARIANT[s.status]}`}>{s.status}</span>
                </div>
                {s.rationale ? <p className="hint" style={{ marginTop: 4 }}>{s.rationale}</p> : null}
                <div className="item-actions" style={{ marginTop: 8 }}>
                  <button type="button" className="btn secondary small" onClick={() => void setStatus(s.id, "accepted")}>
                    {t("suggestions.accept")}
                  </button>
                  <button type="button" className="btn ghost small" onClick={() => void setStatus(s.id, "rejected")}>
                    {t("suggestions.reject")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty-state">
            <Wand2 size={28} aria-hidden="true" />
            <h3 className="card-title">{t("suggestions.emptyTitle")}</h3>
            <p className="hint">{t("suggestions.emptyDesc")}</p>
          </div>
        )}
      </article>
    </div>
  );
}
