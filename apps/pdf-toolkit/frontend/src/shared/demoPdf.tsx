import { createContext, useContext, type ReactNode } from "react";

export const DEMO_PDF_FILE_NAME = "DEMO_CMM_PDF_anonyme.pdf";

const DemoPdfFileContext = createContext<File | null>(null);

type DemoPdfFileProviderProps = {
  file: File | null;
  children: ReactNode;
};

export function DemoPdfFileProvider({ file, children }: DemoPdfFileProviderProps) {
  return <DemoPdfFileContext.Provider value={file}>{children}</DemoPdfFileContext.Provider>;
}

export function useDemoPdfFile(): File | null {
  return useContext(DemoPdfFileContext);
}

export async function loadDemoPdf(): Promise<File> {
  const baseUrl = import.meta.env.BASE_URL.replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/demo/${DEMO_PDF_FILE_NAME}`);
  if (!response.ok) {
    throw new Error(`Demo PDF request failed with HTTP ${response.status}`);
  }

  const blob = await response.blob();
  if (blob.size === 0) {
    throw new Error("The demo PDF is empty");
  }

  return new File([blob], DEMO_PDF_FILE_NAME, { type: "application/pdf" });
}
