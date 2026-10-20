import type { DemoSampleFile } from "@internal/ui";

// Inputs industriels FACTICES (chariot telescopique TELEMAX TH-3500), embarques dans le bundle
// via `?b64` (base64, plugin vite.config.ts) : aucun fetch, aucune donnee utilisateur.
import hsePdf from "./files/HSE-07_consignes_securite_hydraulique.pdf?b64";
import procedureDocx from "./files/PR-HYD-014_procedure_diagnostic_hydraulique.docx?b64";
import rexPptx from "./files/REX_pannes_hydrauliques_TH3500.pptx?b64";
import maintenanceXlsx from "./files/TH3500_donnees_maintenance_hydraulique.xlsx?b64";
import startStepsXlsx from "./files/TH3500_etapes_non_demarrage_moteur.xlsx?b64";

const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation";

function decodeBase64(base64: string): Uint8Array<ArrayBuffer> {
  const binary = atob(base64);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function sample(id: string, name: string, mediaType: string, base64: string): DemoSampleFile {
  return { id, name, mediaType, content: decodeBase64(base64) };
}

export const HYDRAULIC_FILES: readonly DemoSampleFile[] = [
  sample("procedure", "PR-HYD-014_procedure_diagnostic_hydraulique.docx", DOCX, procedureDocx),
  sample("maintenance", "TH3500_donnees_maintenance_hydraulique.xlsx", XLSX, maintenanceXlsx),
  sample("hse", "HSE-07_consignes_securite_hydraulique.pdf", "application/pdf", hsePdf),
  sample("rex", "REX_pannes_hydrauliques_TH3500.pptx", PPTX, rexPptx),
];

export const ENGINE_START_FILES: readonly DemoSampleFile[] = [
  sample("start-steps", "TH3500_etapes_non_demarrage_moteur.xlsx", XLSX, startStepsXlsx),
];

export function sampleSize(file: DemoSampleFile): number {
  return file.content instanceof Uint8Array ? file.content.byteLength : 0;
}
