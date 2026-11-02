import { afterEach, expect, it } from "vitest";
import { useMigrationStore } from "./useMigrationStore";

afterEach(() => useMigrationStore.getState().reset());
it("keeps selected files in memory and discards them when changing workspace", () => {
  const file = new File(["synthetic"], "selected.pdf");
  useMigrationStore.getState().patch({ mode: "normal", file, currentDocId: "synthetic" });
  expect(useMigrationStore.getState().file).toBe(file);
  expect(useMigrationStore.getState().currentDocId).toBe("synthetic");
  useMigrationStore.getState().reset("demo");
  expect(useMigrationStore.getState().file).toBeNull();
  expect(useMigrationStore.getState().currentDocId).toBeNull();
});
