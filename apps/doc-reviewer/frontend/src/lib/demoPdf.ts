export const DEMO_PDF_FILENAME = "DEMO_CMM_PDF_anonyme.pdf";

export async function loadDemoPdf(): Promise<File> {
  const response = await fetch(
    `${import.meta.env.BASE_URL}demo/${DEMO_PDF_FILENAME}`,
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

  return new File([content], DEMO_PDF_FILENAME, { type: "application/pdf" });
}
