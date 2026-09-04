import { generateBREX301 } from "./generateBREX301.js";
import { brexToSchematron } from "./brexToSchematron.js";
import { checkWellFormed } from "./generateBREX.js";

// Genera Schematron (S1000D 3.0.1) en dos pasos deterministas:
// 1) genera el BREX 3.0.1 reutilizando generateBREX301 (LLM + finalización determinista)
// 2) convierte ese BREX a ISO Schematron con brexToSchematron (sin LLM, sin error de XPath)
export async function generateBREXSch(brdps, projectConfig, options = {}) {
  const brexResult = await generateBREX301(brdps, projectConfig, options);
  if (!brexResult || !brexResult.xml) {
    throw new Error("No se pudo generar el BREX base para el Schematron.");
  }

  let sch;
  try {
    sch = brexToSchematron(brexResult.xml, { preserveBrdpId: true, carryComments: true });
  } catch (err) {
    throw new Error(`Conversión BREX -> Schematron fallida: ${err.message}`);
  }

  const { valid, error } = checkWellFormed(sch);
  return { xml: sch, valid, error, brdpCount: brexResult.brdpCount };
}
