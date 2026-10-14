const DEMO_FILES_BASE_URL = `${import.meta.env.BASE_URL}demo/`;

async function fetchDemoFile(filename: string, contentType: string): Promise<File> {
  const response = await fetch(`${DEMO_FILES_BASE_URL}${filename}`);
  if (!response.ok) {
    throw new Error(`${filename} (HTTP ${response.status})`);
  }
  return new File([await response.blob()], filename, { type: contentType });
}

export async function loadDemoMigrationFiles(): Promise<{
  document: File;
  dmrl: File;
  dm_header: File;
}> {
  const [document, dmrl, dmHeader] = await Promise.all([
    fetchDemoFile("WEG-WMO.pdf", "application/pdf"),
    fetchDemoFile(
      "DMRL_v2.xlsx",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    fetchDemoFile("dm_header_template.example.json", "application/json"),
  ]);
  return { document, dmrl, dm_header: dmHeader };
}
