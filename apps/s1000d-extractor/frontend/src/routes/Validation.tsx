import {
  AlertCircle,
  CheckCircle2,
  FileUp,
  FolderOpen,
  Loader2,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  validationApi,
  wizardApi,
  type DmValidationResult,
  type DmValidationStatus,
  type DmValidationViolation,
} from "../lib/api";
import { ValidationQueue, VALIDATION_BATCH_SIZE } from "../lib/validationQueue";
import { collectDroppedFiles } from "../lib/validationDrop";

const ISSUES = ["4.1", "4.2"] as const;

type ValidationItem = Omit<DmValidationResult, "status"> & {
  id: string;
  file: File | null;
  generated?: { docId: string; dmId: string };
  displayName: string;
  status: DmValidationStatus | "checking";
};

type GeneratedState = {
  generated?: {
    documentId: string;
    dmIds: string[];
  };
};

function newItem(file: File, displayName = file.webkitRelativePath || file.name): ValidationItem {
  return {
    id: crypto.randomUUID(),
    file,
    displayName,
    filename: displayName,
    dmc: "",
    issue: null,
    schema: null,
    status: "checking",
    error_count: 0,
    violations: [],
  };
}

function statusClass(status: DmValidationStatus | "checking"): string {
  if (status === "valid") return "ok";
  if (status === "invalid" || status === "unverifiable") return "warn";
  return "info";
}

function statusIcon(status: DmValidationStatus | "checking") {
  if (status === "valid") return <CheckCircle2 aria-hidden="true" size={15} />;
  if (status === "invalid" || status === "unverifiable")
    return <AlertCircle aria-hidden="true" size={15} />;
  return <Loader2 aria-hidden="true" className="validation-spin" size={15} />;
}

function errorTypes(item: ValidationItem, t: (key: string) => string): string {
  const rules = [...new Set(item.violations.filter((violation) => violation.severity === "error").map((v) => v.rule))];
  if (rules.length) return rules.join(", ");
  if (item.status === "unverifiable") return t("validation.status.unverifiable");
  if (item.status === "needs_issue") return t("validation.status.needsIssue");
  return "—";
}

function locationLabel(
  violation: DmValidationViolation,
  t: ReturnType<typeof useTranslation>["t"],
) {
  if (violation.line == null) return violation.path || "/";
  const line = t("validation.line", { line: violation.line });
  return violation.column == null ? line : `${line}:${violation.column}`;
}

export function Validation() {
  const { t } = useTranslation();
  const location = useLocation();
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement | null>(null);
  const importedGenerated = useRef<string | null>(null);
  const pendingGenerated = useRef(new Map<string, ReturnType<typeof wizardApi.validate>>());
  const [items, setItems] = useState<ValidationItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [listDragging, setListDragging] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [queue] = useState(() => new ValidationQueue(2));
  const [progress, setProgress] = useState({ completed: 0, total: 0 });
  const generated = (location.state as GeneratedState | null)?.generated;

  const visibleItems = errorsOnly ? items.filter((item) => item.error_count > 0) : items;
  const selected = visibleItems.find((item) => item.id === selectedId) ?? visibleItems[0] ?? null;

  const updateFromResults = (entries: ValidationItem[], results: DmValidationResult[]) => {
    const updated = new Map(
      entries.map((entry, index) => [
        entry.id,
        results[index]
          ? { ...entry, ...results[index], id: entry.id, file: entry.file, displayName: entry.displayName }
          : entry,
      ]),
    );
    setItems((current) => current.map((item) => updated.get(item.id) ?? item));
  };

  const markRequestFailed = (entries: ValidationItem[], error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    const ids = new Set(entries.map((entry) => entry.id));
    setItems((current) => current.map((item) =>
      ids.has(item.id)
        ? {
            ...item,
            status: "invalid",
            error_count: 1,
            violations: [{
              severity: "error",
              rule: "API",
              message,
              path: "/",
            }],
          }
        : item,
    ));
  };

  const importFiles = (files: File[]) => {
    if (!files.length) return;
    const entries = files.map((file) => newItem(file));
    setLoadError(null);
    setItems((current) => [...entries, ...current]);
    setSelectedId((current) => current ?? entries[0]?.id ?? null);
    setProgress((current) => ({ ...current, total: current.total + files.length }));
    const batches = Math.ceil(files.length / VALIDATION_BATCH_SIZE);
    setPendingCount((current) => current + batches);
    for (let offset = 0; offset < entries.length; offset += VALIDATION_BATCH_SIZE) {
      const batch = entries.slice(offset, offset + VALIDATION_BATCH_SIZE);
      const payload = files.slice(offset, offset + VALIDATION_BATCH_SIZE);
      void queue.enqueue(() => validationApi.validate(payload, batch.map(() => null), batch.map((item) => item.displayName)))
        .then(({ results }) => updateFromResults(batch, results))
        .catch((error: unknown) => markRequestFailed(batch, error))
        .finally(() => {
          setPendingCount((current) => Math.max(0, current - 1));
          setProgress((current) => ({ ...current, completed: current.completed + batch.length }));
        });
    }
  };

  const chooseIssue = (item: ValidationItem, issue: string) => {
    setItems((current) => current.map((entry) =>
      entry.id === item.id ? { ...entry, issue, status: "checking" } : entry,
    ));
    setPendingCount((current) => current + 1);
    const file = item.file
      ? Promise.resolve(item.file)
      : item.generated
        ? wizardApi.downloadDmFile(item.generated.docId, item.generated.dmId)
        : Promise.reject(new Error(t("validation.sourceUnavailable")));
    void queue.enqueue(() => file.then((source) => validationApi.validate([source], [issue], [item.displayName])))
      .then(({ results }) => updateFromResults([item], results))
      .catch((error: unknown) => markRequestFailed([item], error))
      .finally(() => setPendingCount((current) => Math.max(0, current - 1)));
  };

  useEffect(() => {
    const generated = (location.state as GeneratedState | null)?.generated;
    if (!generated) return;
    const key = `${generated.documentId}:${generated.dmIds.join(",")}`;
    if (importedGenerated.current === key) return;
    let cancelled = false;
    let pending = pendingGenerated.current.get(key);
    if (!pending) {
      setPendingCount((current) => current + 1);
      pending = queue.enqueue(() => wizardApi.validate(generated.documentId, generated.dmIds));
      pendingGenerated.current.set(key, pending);
      const finish = () => {
        pendingGenerated.current.delete(key);
        setPendingCount((current) => Math.max(0, current - 1));
      };
      void pending.then(finish, finish);
    }
    const request = pending;

    const loadGeneratedDms = async () => {
      setLoadError(null);
      try {
        const { results } = await request;
        if (cancelled) return;
        importedGenerated.current = key;

        const entries: ValidationItem[] = results.map((result) => ({
          ...result, id: crypto.randomUUID(), file: null, displayName: result.filename,
          generated: { docId: generated.documentId, dmId: result.dm_id },
        }));
        setItems((current) => [...entries, ...current]);
        setSelectedId((current) => current ?? entries[0]?.id ?? null);
      } catch (error) {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : String(error));
      }
    };

    void loadGeneratedDms();
    return () => {
      cancelled = true;
    };
  }, [location.state]);

  const removeItem = (id: string) => {
    setItems((current) => current.filter((item) => item.id !== id));
    setSelectedId((current) => current === id ? null : current);
  };

  const validCount = items.filter((item) => item.status === "valid").length;
  const invalidCount = items.filter((item) => item.status === "invalid").length;
  const unverifiableCount = items.filter((item) => item.status === "unverifiable").length;

  return (
    <div className="validation-page">
      <header className="page-header">
        <h1>{t("validation.title")}</h1>
        <p>{t("validation.subtitle")}</p>
        {generated ? <Link to={`/migration/${generated.documentId}`}>
          {t("validation.backToConversion")}
        </Link> : null}
      </header>

      <section
        className={`validation-import${dragging ? " is-dragging" : ""}`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void collectDroppedFiles(event.dataTransfer).then(importFiles)
            .catch((error: unknown) => setLoadError(error instanceof Error ? error.message : String(error)));
        }}
      >
        <input
          ref={fileInput}
          className="validation-hidden-input"
          type="file"
          accept=".xml,application/xml,text/xml"
          multiple
          onChange={(event) => {
            importFiles(Array.from(event.currentTarget.files ?? []));
            event.currentTarget.value = "";
          }}
        />
        <input
          ref={(element) => {
            folderInput.current = element;
            element?.setAttribute("webkitdirectory", "");
          }}
          className="validation-hidden-input"
          type="file"
          accept=".xml,application/xml,text/xml"
          multiple
          onChange={(event) => {
            importFiles(Array.from(event.currentTarget.files ?? []));
            event.currentTarget.value = "";
          }}
        />

        <div className="validation-drop-copy">
          <FileUp aria-hidden="true" size={22} />
          <div>
            <strong>{t("validation.dropTitle")}</strong>
            <span className="label">{t("validation.dropHelp")}</span>
          </div>
        </div>
        <div className="validation-import-actions">
          <button type="button" className="btn primary" onClick={() => fileInput.current?.click()}>
            <FileUp aria-hidden="true" size={16} /> {t("validation.selectFiles")}
          </button>
          <button type="button" className="btn secondary" onClick={() => folderInput.current?.click()}>
            <FolderOpen aria-hidden="true" size={16} /> {t("validation.selectFolder")}
          </button>
          <button type="button" className="btn secondary" disabled title={t("validation.brexDisabledHelp")}>
            <ShieldCheck aria-hidden="true" size={16} /> {t("validation.brexDisabled")}
          </button>
        </div>
      </section>

      {loadError ? <div className="alert error">{loadError}</div> : null}
      {progress.total ? <p role="status" aria-live="polite">
        {t("validation.progress", progress)}
      </p> : null}

      <div className="validation-summary" aria-live="polite">
        <span>{t("validation.summary.documents", { count: items.length })}</span>
        <span className="badge ok">{t("validation.summary.valid", { count: validCount })}</span>
        <span className={`badge ${invalidCount ? "warn" : "info"}`}>
          {t("validation.summary.invalid", { count: invalidCount })}
        </span>
        <span className="badge info">
          {t("validation.summary.unverifiable", { count: unverifiableCount })}
        </span>
        {items.length ? (
          <label className="validation-error-filter">
            <input
              type="checkbox"
              checked={errorsOnly}
              onChange={(event) => setErrorsOnly(event.currentTarget.checked)}
            />
            <span>{t("validation.filterErrorsOnly")}</span>
          </label>
        ) : null}
        {pendingCount ? (
          <span className="validation-pending label">
            <Loader2 aria-hidden="true" className="validation-spin" size={14} />
            {t("validation.pending", { count: pendingCount })}
          </span>
        ) : null}
        {items.length ? (
          <button
            type="button"
            className="btn ghost small validation-clear"
            onClick={() => {
              setItems([]);
              setSelectedId(null);
            }}
          >
            <Trash2 aria-hidden="true" size={14} /> {t("validation.clear")}
          </button>
        ) : null}
      </div>

      <div className="validation-grid">
        <section className="card validation-list-panel">
          <h2 className="card-title">{t("validation.listTitle", { count: visibleItems.length })}</h2>
          {visibleItems.length ? (
            <div className="validation-table-scroll">
              <table className="validation-table">
                <thead>
                  <tr>
                    <th>{t("validation.columns.parsing")}</th>
                    <th>{t("validation.columns.dmc")}</th>
                    <th>{t("validation.columns.version")}</th>
                    <th>{t("validation.columns.schema")}</th>
                    <th>{t("validation.columns.errorType")}</th>
                    <th>{t("validation.columns.errorCount")}</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleItems.map((item) => (
                    <tr
                      key={item.id}
                      className={item.id === selected?.id ? "is-selected" : ""}
                      aria-selected={item.id === selected?.id}
                      tabIndex={0}
                      onClick={() => setSelectedId(item.id)}
                      onKeyDown={(event) => {
                        if (event.target !== event.currentTarget) return;
                        if (event.key !== "Enter" && event.key !== " ") return;
                        event.preventDefault();
                        setSelectedId(item.id);
                      }}
                    >
                      <td>
                        <span className={`badge ${statusClass(item.status)}`}>
                          {statusIcon(item.status)} {t(`validation.status.${item.status}`)}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="validation-row-select"
                          title={item.displayName}
                          onClick={() => setSelectedId(item.id)}
                        >
                          <strong>{item.dmc || item.displayName}</strong>
                          {item.dmc ? <small>{item.displayName}</small> : null}
                        </button>
                      </td>
                      <td>
                        {item.status === "needs_issue" ? (
                          <select
                            className="input validation-issue-select"
                            value={item.issue ?? ""}
                            aria-label={t("validation.chooseIssueFor", { filename: item.displayName })}
                            onChange={(event) => {
                              if (event.target.value) chooseIssue(item, event.target.value);
                            }}
                          >
                            <option value="">{t("validation.chooseIssue")}</option>
                            {ISSUES.map((issue) => (
                              <option value={issue} key={issue}>{issue}</option>
                            ))}
                          </select>
                        ) : item.issue ? `Issue ${item.issue}` : "—"}
                      </td>
                      <td>{item.schema || "—"}</td>
                      <td className="validation-error-type">{errorTypes(item, t)}</td>
                      <td className="validation-count-cell">
                        <span className={`badge ${item.error_count ? "warn" : "ok"}`}>
                          {item.error_count}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div
              className={`validation-empty-list${items.length === 0 ? " validation-empty-drop" : ""}${listDragging ? " is-dragging" : ""}`}
              onDragEnter={(event) => {
                if (items.length) return;
                event.preventDefault();
                setListDragging(true);
              }}
              onDragOver={(event) => {
                if (items.length) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = "copy";
              }}
              onDragLeave={(event) => {
                if (items.length || event.currentTarget.contains(event.relatedTarget as Node | null)) return;
                setListDragging(false);
              }}
              onDrop={(event) => {
                if (items.length) return;
                event.preventDefault();
                setListDragging(false);
                void collectDroppedFiles(event.dataTransfer).then(importFiles)
                  .catch((error: unknown) => setLoadError(error instanceof Error ? error.message : String(error)));
              }}
            >
              {items.length ? (
                <>
                  <CheckCircle2 aria-hidden="true" size={24} />
                  <span>{t("validation.noErrorsToShow")}</span>
                </>
              ) : (
                <>
                  <FileUp aria-hidden="true" size={24} />
                  <span>{t("validation.emptyList")}</span>
                </>
              )}
            </div>
          )}
        </section>

        <aside className="card validation-detail-panel" aria-live="polite">
          {selected ? (
            <>
              <div className="validation-detail-heading">
                <div className="validation-detail-title">
                  <span className={`badge ${statusClass(selected.status)}`}>
                    {statusIcon(selected.status)} {t(`validation.status.${selected.status}`)}
                  </span>
                  <h2 className="card-title">{selected.dmc || selected.displayName}</h2>
                  <span className="label validation-filename">{selected.displayName}</span>
                </div>
                <button
                  type="button"
                  className="btn ghost small validation-remove"
                  aria-label={t("validation.remove")}
                  title={t("validation.remove")}
                  onClick={() => removeItem(selected.id)}
                >
                  <X aria-hidden="true" size={16} />
                </button>
              </div>

              {selected.status === "checking" ? (
                <p className="validation-state-message">
                  <Loader2 aria-hidden="true" className="validation-spin" size={18} />
                  {t("validation.detail.checking")}
                </p>
              ) : null}
              {selected.status === "valid" ? (
                <p className="validation-state-message is-valid">
                  <CheckCircle2 aria-hidden="true" size={19} />
                  <span>{t("validation.detail.valid")}</span>
                </p>
              ) : null}
              {selected.status === "needs_issue" ? (
                <p className="validation-state-message">
                  <AlertCircle aria-hidden="true" size={19} />
                  <span>{selected.message || t("validation.detail.chooseIssue")}</span>
                </p>
              ) : null}
              {selected.status === "unverifiable" ? (
                <p className="validation-state-message">
                  <AlertCircle aria-hidden="true" size={19} />
                  <span>{t("validation.detail.unverifiable")}</span>
                </p>
              ) : null}

              {selected.violations.length ? (
                <div className="validation-violations">
                  <h3 className="label">
                    {t("validation.detail.violations", { count: selected.violations.length })}
                  </h3>
                  {selected.violations.map((violation, index) => (
                    <article className="validation-violation" key={`${violation.rule}-${index}`}>
                      <div className="validation-violation-meta">
                        <span className={`badge ${violation.severity === "error" ? "warn" : "info"}`}>
                          {violation.rule}
                        </span>
                        <span className="label">{locationLabel(violation, t)}</span>
                      </div>
                      <p>{violation.message}</p>
                      {violation.path && violation.path !== "/" ? (
                        <code className="validation-error-path">{violation.path}</code>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <>
              <h2 className="card-title">{t("validation.detail.panelTitle")}</h2>
              <div className="validation-empty-detail">
                <CheckCircle2 aria-hidden="true" size={24} />
                <span>{t("validation.detail.selectDm")}</span>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}