import { create } from "zustand";
import type { DocumentOut, MigrationInputMapping, ResourceKind, S1000dIssue } from "../../lib/api";

type Uploaded = {
  file: File; issue: S1000dIssue; brexId: string | null; document: DocumentOut;
  resources: Partial<Record<ResourceKind, File>>;
};
type Draft = {
  mode: "normal" | "demo" | null;
  ready: boolean;
  loading: boolean;
  error: string | null;
  file: File | null;
  issue: S1000dIssue;
  brexId: string | null;
  resources: Partial<Record<ResourceKind, File>>;
  mapping: MigrationInputMapping | null;
  removedResources: ResourceKind[];
  currentDocId: string | null;
  uploaded: Uploaded | null;
};
const initial = (): Draft => ({
  mode: null, ready: false, loading: false, error: null, file: null, issue: "4.2",
  brexId: null, resources: {}, mapping: null, removedResources: [],
  currentDocId: null, uploaded: null,
});
export const useMigrationStore = create<Draft & {
  patch: (values: Partial<Draft>) => void;
  reset: (mode?: Draft["mode"]) => void;
}>((set) => ({
  ...initial(),
  patch: (values) => set(values),
  reset: (mode = null) => set({ ...initial(), mode }),
}));
