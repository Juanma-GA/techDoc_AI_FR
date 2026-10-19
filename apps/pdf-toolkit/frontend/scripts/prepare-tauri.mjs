import { fileURLToPath } from "node:url";
import { run } from "../../../../scripts/lib/frontend-build.mjs";

run(process.execPath, [fileURLToPath(new URL("../../../../scripts/build_pdf_toolkit.mjs", import.meta.url))],
  fileURLToPath(new URL("../../../../", import.meta.url)));
