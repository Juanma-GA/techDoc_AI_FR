import { describe, expect, it } from "vitest";

import {
  createMaintenanceDemoFiles,
  createMaintenanceDemoReport,
  createMaintenanceDemoStyles,
  createMaintenanceDemoTemplates,
} from "./maintenanceDemo";

describe("maintenance demo files", () => {
  const files = createMaintenanceDemoFiles({
    conveyor: {
      fileName: "WO-CV-204.txt",
      fileContent: "Fictional conveyor work order.",
      output: "Conveyor report.",
    },
    pump: {
      fileName: "WO-P-118.txt",
      fileContent: "Fictional pump work order.",
      output: "Pump report.",
    },
  });

  it("provides only the synthetic source files with stable IDs", () => {
    expect(files.map((file) => file.id)).toEqual(["demo-conveyor", "demo-pump"]);
    expect(files.every((file) => file.kind === "source")).toBe(true);
    expect(files.map((file) => file.content)).toEqual([
      "Fictional conveyor work order.",
      "Fictional pump work order.",
    ]);
  });

  it("builds a local report from selected demo files without network access", () => {
    const templates = createMaintenanceDemoTemplates({
      "service-report": "Standard service report",
      "inspection-checklist": "Inspection checklist",
    });
    const report = createMaintenanceDemoReport(
      "Draft the maintenance note.",
      [files[0]!],
      (key) => key,
      templates[1],
    );

    expect(report).toContain("Draft the maintenance note.");
    expect(report).toContain("Inspection checklist");
    expect(report).toContain("demo.templates.inspection-checklist.steps");
    expect(report).toContain("Conveyor report.");
    expect(report).toContain("Fictional conveyor work order.");
    expect(report).toContain("demo.disclaimer");
    expect(report).not.toContain("Pump report.");
  });

  it("uses a fictional style document locally", () => {
    const styles = createMaintenanceDemoStyles(
      "Fictional style guide.md",
      "Use short headings and verified facts.",
    );
    const report = createMaintenanceDemoReport(
      "Draft the maintenance note.",
      [files[0]!],
      (key) => key,
      undefined,
      styles[0],
    );

    expect(styles[0]?.id).toBe("demo-style-maintenance-standard");
    expect(styles[0]?.kind).toBe("style");
    expect(report).toContain("demo.styles.applied");
    expect(report).toContain("Use short headings and verified facts.");
  });

  it("generates a report without adding an empty brief section", () => {
    const report = createMaintenanceDemoReport("", [files[0]!], (key) => key);

    expect(report).not.toContain("demo.briefLabel");
    expect(report).toContain("Conveyor report.");
  });
});
