import type { DocumentDto } from "./api";

export type MaintenanceDemoFile = DocumentDto & {
  demoKey: "conveyor" | "pump";
  content: string;
  report: string;
};

export type MaintenanceDemoCopy = {
  fileName: string;
  fileContent: string;
  output: string;
};

export type MaintenanceDemoTemplateKey = "service-report" | "inspection-checklist";

export type MaintenanceDemoTemplate = DocumentDto & {
  demoTemplateKey: MaintenanceDemoTemplateKey;
};

export type MaintenanceDemoStyle = DocumentDto & {
  demoStyleKey: "maintenance-standard";
  content: string;
};

export function createMaintenanceDemoFiles(
  copy: Record<MaintenanceDemoFile["demoKey"], MaintenanceDemoCopy>,
): MaintenanceDemoFile[] {
  return (["conveyor", "pump"] as const).map((demoKey) => {
    const sample = copy[demoKey];
    const content = sample.fileContent;

    return {
      id: `demo-${demoKey}`,
      filename: sample.fileName,
      mime_type: "text/plain",
      size: new Blob([content]).size,
      sha256: `demo-${demoKey}`,
      chunk_count: 1,
      index_error: null,
      kind: "source",
      uploaded_at: "2026-01-01T00:00:00Z",
      demoKey,
      content,
      report: sample.output,
    };
  });
}

export function createMaintenanceDemoTemplates(
  names: Record<MaintenanceDemoTemplateKey, string>,
): MaintenanceDemoTemplate[] {
  return (["service-report", "inspection-checklist"] as const).map(
    (demoTemplateKey) => ({
      id: `demo-template-${demoTemplateKey}`,
      filename: names[demoTemplateKey],
      mime_type: "application/x-demo-template",
      size: 0,
      sha256: `demo-template-${demoTemplateKey}`,
      chunk_count: 0,
      index_error: null,
      kind: "template",
      uploaded_at: "2026-01-01T00:00:00Z",
      demoTemplateKey,
    }),
  );
}

export function createMaintenanceDemoStyles(
  name: string,
  content: string,
): MaintenanceDemoStyle[] {
  return [
    {
      id: "demo-style-maintenance-standard",
      filename: name,
      mime_type: "text/markdown",
      size: new Blob([content]).size,
      sha256: "demo-style-maintenance-standard",
      chunk_count: 0,
      index_error: null,
      kind: "style",
      uploaded_at: "2026-01-01T00:00:00Z",
      demoStyleKey: "maintenance-standard",
      content,
    },
  ];
}

export function createMaintenanceDemoReport(
  brief: string,
  documents: readonly MaintenanceDemoFile[],
  t: (key: string) => string,
  template?: MaintenanceDemoTemplate,
  style?: MaintenanceDemoStyle,
): string {
  const report = [
    ...(brief.trim()
      ? [`${t("demo.briefLabel")}:`, brief.trim(), ""]
      : []),
    ...documents.flatMap((document) => [
      `${document.filename}`,
      document.report,
      "",
      `${t("demo.sourceDocument")}:`,
      document.content,
      "",
    ]),
    ...(style
      ? [`${t("demo.styles.applied")}:`, style.content, ""]
      : []),
    t("demo.disclaimer"),
  ].join("\n");

  if (template?.demoTemplateKey === "inspection-checklist") {
    return [
      template.filename,
      "",
      t("demo.templates.inspection-checklist.steps"),
      "- " + t("demo.templates.inspection-checklist.stepIsolation"),
      "- " + t("demo.templates.inspection-checklist.stepInspection"),
      "- " + t("demo.templates.inspection-checklist.stepApproval"),
      "",
      report,
    ].join("\n");
  }

  if (template?.demoTemplateKey === "service-report") {
    return [`${template.filename}`, "", report].join("\n");
  }

  return report;
}
