export const DEMO_PDF_FILENAME = "DEMO_CMM_PDF_anonyme.pdf";
export const DEMO_REVISION_PDF_FILENAME = "DEMO_CMM_PDF_revision_anonyme.pdf";

export async function loadDemoPdf(
  filename: typeof DEMO_PDF_FILENAME | typeof DEMO_REVISION_PDF_FILENAME = DEMO_PDF_FILENAME,
): Promise<File> {
  const response = await fetch(
    `${import.meta.env.BASE_URL}demo/${filename}`,
  );
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const contentType = response.headers
    .get("content-type")
    ?.split(";", 1)[0]
    ?.trim()
    .toLowerCase();
  if (contentType !== "application/pdf") {
    throw new Error(`Expected application/pdf, received ${contentType ?? "no content type"}`);
  }

  const content = new Uint8Array(await response.arrayBuffer());
  if (content.byteLength === 0) {
    throw new Error("The PDF is empty");
  }

  return new File([content], filename, { type: "application/pdf" });
}

export async function loadDemoComparisonPdfs(): Promise<File[]> {
  return Promise.all([loadDemoPdf(), loadDemoPdf(DEMO_REVISION_PDF_FILENAME)]);
}
