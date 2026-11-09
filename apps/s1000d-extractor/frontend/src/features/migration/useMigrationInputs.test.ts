import { afterEach, expect, it, vi } from "vitest";

import { ApiRequestError, migrationInputsApi, type MigrationInputMapping } from "../../lib/api";
import { loadDemoMigrationFiles } from "../../lib/demoMigrationFiles";
import { cacheLastMigrationInputs } from "./useMigrationInputs";
import { useMigrationStore } from "./useMigrationStore";

vi.mock("../../lib/demoMigrationFiles", () => ({
  loadDemoMigrationFiles: vi.fn(),
}));

afterEach(() => {
  useMigrationStore.getState().reset();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

it("keeps the latest saved source and resources in memory without document paths", async () => {
  const mapping: MigrationInputMapping = {
    issue: "4.1",
    context_hint: "mixed",
    brex_id: null,
    files: {
      document: { filename: "latest.pdf" },
      dmrl: { filename: "latest-dmrl.xlsx" },
    },
  };
  const source = new File(["source"], "latest.pdf");
  const dmrl = new File(["dmrl"], "latest-dmrl.xlsx");
  vi.spyOn(migrationInputsApi, "read").mockResolvedValue(mapping);
  const fileSpy = vi.spyOn(migrationInputsApi, "file").mockImplementation(
    async (kind) => kind === "document" ? source : dmrl,
  );

  await cacheLastMigrationInputs("normal");

  const state = useMigrationStore.getState();
  expect(state.file).toBe(source);
  expect(state.resources.dmrl).toBe(dmrl);
  expect(state.mapping?.files).toEqual({});
  expect(state.issue).toBe("4.1");
  expect(fileSpy).toHaveBeenCalledTimes(2);
});

it("keeps selected in-memory files instead of restoring old mappings", async () => {
  const mapping: MigrationInputMapping = {
    issue: "4.2",
    context_hint: "mixed",
    brex_id: null,
    files: { document: { filename: "old.pdf" }, dmrl: { filename: "old-dmrl.xlsx" } },
  };
  const selected = new File(["new source"], "new.pdf");
  useMigrationStore.getState().patch({
    mode: "normal",
    ready: true,
    file: selected,
    mapping,
    removedResources: ["dmrl"],
  });
  const fileSpy = vi.spyOn(migrationInputsApi, "file");

  await cacheLastMigrationInputs("normal");

  expect(useMigrationStore.getState().file).toBe(selected);
  expect(useMigrationStore.getState().resources.dmrl).toBeUndefined();
  expect(useMigrationStore.getState().mapping?.files).toEqual({});
  expect(fileSpy).not.toHaveBeenCalled();
});

it("drops stale saved filenames when their files no longer exist", async () => {
  const mapping: MigrationInputMapping = {
    issue: "4.2",
    context_hint: "mixed",
    brex_id: null,
    files: { document: { filename: "deleted.pdf" } },
  };
  useMigrationStore.getState().patch({ mode: "normal", ready: true, mapping });
  vi.spyOn(migrationInputsApi, "file").mockRejectedValue(
    new ApiRequestError(404, "SAVED_INPUT_NOT_FOUND", "Saved input not found."),
  );

  await cacheLastMigrationInputs("normal");

  expect(useMigrationStore.getState().file).toBeNull();
  expect(useMigrationStore.getState().mapping?.files).toEqual({});
});

it("does not restore demo defaults after the selected source has been cleared", async () => {
  useMigrationStore.getState().patch({
    mode: "demo",
    ready: true,
    file: null,
    resources: {},
    removedResources: ["dmrl", "dm_header"],
  });

  await cacheLastMigrationInputs("demo");

  expect(loadDemoMigrationFiles).not.toHaveBeenCalled();
  expect(useMigrationStore.getState().file).toBeNull();
  expect(useMigrationStore.getState().resources).toEqual({});
});
