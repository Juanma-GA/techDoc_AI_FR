import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { PageHeader } from "@internal/ui";

import {
  validationApi,
  wizardApi,
  type DmValidationResult,
} from "../lib/api";
import { formatApiError } from "../lib/migrationUtils";
import { ValidationQueue, VALIDATION_BATCH_SIZE } from "../lib/validationQueue";
import { ValidationImport } from "../components/ValidationImport";
import { ValidationResults, type ValidationItem } from "../components/ValidationResults";

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

export function Validation() {
  const { t } = useTranslation();
  const location = useLocation();
  const importedGenerated = useRef<string | null>(null);
  const pendingGenerated = useRef(new Map<string, ReturnType<typeof wizardApi.validate>>());
  const [items, setItems] = useState<ValidationItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [queue] = useState(() => new ValidationQueue(2));
  const [progress, setProgress] = useState({ completed: 0, total: 0 });
  const generated = (location.state as GeneratedState | null)?.generated;

  const visibleItems = errorsOnly ? items.filter((item) => item.error_count > 0) : items;
  const selected = visibleItems.find((item) => item.id === selectedId) ?? visibleItems[0] ?? null;
  const reportLoadError = useCallback(
    (error: unknown) => setLoadError(formatApiError(t, error)),
    [t],
  );

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
    const message = formatApiError(t, error);
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
      void queue.enqueue(() =>
        validationApi.validate(payload, batch.map(() => null), batch.map((item) => item.displayName)),
      )
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
    void queue.enqueue(() =>
      file.then((source) => validationApi.validate([source], [issue], [item.displayName])),
    )
      .then(({ results }) => updateFromResults([item], results))
      .catch((error: unknown) => markRequestFailed([item], error))
      .finally(() => setPendingCount((current) => Math.max(0, current - 1)));
  };

  useEffect(() => {
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
          ...result,
          id: crypto.randomUUID(),
          file: null,
          displayName: result.filename,
          generated: { docId: generated.documentId, dmId: result.dm_id },
        }));
        setItems((current) => [...entries, ...current]);
        setSelectedId((current) => current ?? entries[0]?.id ?? null);
      } catch (error) {
        if (!cancelled) reportLoadError(error);
      }
    };

    void loadGeneratedDms();
    return () => {
      cancelled = true;
    };
  }, [generated, queue, reportLoadError]);

  const removeItem = (id: string) => {
    setItems((current) => current.filter((item) => item.id !== id));
    setSelectedId((current) => current === id ? null : current);
  };

  const validCount = items.filter((item) => item.status === "valid").length;
  const invalidCount = items.filter((item) => item.status === "invalid").length;
  const unverifiableCount = items.filter((item) => item.status === "unverifiable").length;

  return (
    <div className="s1k-validation-page flex flex-col gap-3">
      <PageHeader
        title={t("validation.title")}
        description={t("validation.subtitle")}
        actions={generated ? (
          <Link className="text-brand-text underline" to={`/migration/${generated.documentId}`}>
            {t("validation.backToConversion")}
          </Link>
        ) : undefined}
      />
      <ValidationImport
        loadError={loadError}
        onImport={importFiles}
        onError={reportLoadError}
      />
      <ValidationResults
        items={items}
        visibleItems={visibleItems}
        selected={selected}
        errorsOnly={errorsOnly}
        pendingCount={pendingCount}
        progress={progress}
        validCount={validCount}
        invalidCount={invalidCount}
        unverifiableCount={unverifiableCount}
        onErrorsOnlyChange={setErrorsOnly}
        onSelectItem={setSelectedId}
        onClear={() => {
          setItems([]);
          setSelectedId(null);
        }}
        onChooseIssue={chooseIssue}
        onRemove={removeItem}
        onImport={importFiles}
        onError={reportLoadError}
      />
    </div>
  );
}
