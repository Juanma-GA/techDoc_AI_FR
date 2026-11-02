import { useEffect, useRef } from "react";
import { useDemoMode } from "@internal/ui";
import { useTranslation } from "react-i18next";

import {
  documentsApi, migrationInputsApi, resourcesApi, type ResourceKind, type S1000dIssue,
} from "../../lib/api";
import { loadDemoMigrationFiles } from "../../lib/demoMigrationFiles";
import { formatApiError } from "../../lib/migrationUtils";
import { useMigrationStore } from "./useMigrationStore";

const resourceKinds = ["dmrl", "cir", "brex_rules", "dm_header"] as const;
export function useMigrationInputs() {
  const { mode, isReady } = useDemoMode();
  const { t } = useTranslation();
  const draft = useMigrationStore();
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);
  useEffect(() => {
    if (!isReady) return;
    const current = useMigrationStore.getState();
    if (current.mode === mode && current.ready) return;
    if (current.mode !== mode) current.reset(mode);
    current.patch({ loading: true, error: null });
    let active = true;
    const load = async () => {
      try {
        if (mode === "demo") {
          const files = await loadDemoMigrationFiles();
          if (active) current.patch({
            file: files.document, resources: { dmrl: files.dmrl, dm_header: files.dm_header },
            issue: "4.1", brexId: null, ready: true,
          });
        } else {
          const mapping = await migrationInputsApi.read();
          if (active) current.patch({
            mapping, issue: mapping.issue === "5.0" ? "4.2" : mapping.issue,
            brexId: mapping.brex_id, ready: true,
          });
        }
      } catch (error) {
        if (active) current.patch({ error: formatApiError(t, error), ready: true });
      } finally {
        if (active) current.patch({ loading: false });
      }
    };
    void load();
    return () => { active = false; };
  }, [mode, isReady, t]);

  const selectDocument = (file: File | null) => draft.patch({
    file, currentDocId: null, uploaded: null,
    mapping: draft.mapping ? { ...draft.mapping, files: { ...draft.mapping.files, document: undefined } } : null,
  });
  const selectResource = (kind: ResourceKind, file: File | null) => {
    const mapping = draft.mapping ? {
      ...draft.mapping, files: { ...draft.mapping.files, [kind]: undefined },
    } : null;
    draft.patch({
      mapping, resources: { ...draft.resources, [kind]: file ?? undefined },
      removedResources: file ? draft.removedResources.filter((value) => value !== kind)
        : [...new Set([...draft.removedResources, kind])],
    });
  };
  const upload = async () => {
    const current = useMigrationStore.getState();
    const ensureActive = () => {
      if (!alive.current || useMigrationStore.getState().mode !== current.mode) {
        throw new DOMException("Conversion inputs changed.", "AbortError");
      }
    };
    ensureActive();
    const file = current.file ?? (current.mapping?.files.document
      ? await migrationInputsApi.file("document", current.mapping.files.document.filename) : null);
    if (!file) throw new Error(t("migration.upload.noFile"));
    ensureActive();
    const resources = { ...current.resources };
    for (const kind of ["dmrl", "dm_header"] as const) {
      const saved = current.mapping?.files[kind];
      if (!resources[kind] && saved && !current.removedResources.includes(kind)) {
        resources[kind] = await migrationInputsApi.file(kind, saved.filename);
        ensureActive();
      }
    }
    current.patch({ file, resources });
    const cached = current.uploaded;
    const matching = cached?.file === file && cached.issue === current.issue && cached.brexId === current.brexId;
    const document = matching
      ? { ...cached.document, reused: true }
      : await documentsApi.upload(file, current.issue, "mixed", current.brexId ?? undefined);
    ensureActive();
    let changed = false;
    for (const kind of resourceKinds) {
      ensureActive();
      if (current.removedResources.includes(kind)) {
        await resourcesApi.remove(document.id, kind);
        changed = true;
      } else {
        const resource = resources[kind];
        if (resource && (!matching || cached.resources[kind] !== resource)) {
          const result = await resourcesApi.upload(document.id, kind, resource);
          changed ||= result.reused !== true;
        }
        ensureActive();
      }
    }
    current.patch({
      uploaded: { file, issue: current.issue, brexId: current.brexId, document, resources },
      removedResources: [],
    });
    return { document, resourcesChanged: changed };
  };
  return {
    ...draft, mode, loading: draft.loading || !isReady,
    selectDocument, selectResource, upload,
    setIssue: (issue: S1000dIssue) => draft.patch({ issue }),
    setBrexId: (brexId: string | null) => draft.patch({ brexId }),
  };
}
export type MigrationInputs = ReturnType<typeof useMigrationInputs>;
