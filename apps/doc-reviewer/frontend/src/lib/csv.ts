// CWE-1236 (CSV formula injection): Excel/LibreOffice/Sheets treat a cell
// starting with =, +, -, @ (or a leading tab/CR) as a formula. Any CSV built
// from user-controlled input (uploaded filenames, free-text feedback, …)
// must neutralize that before export.
const FORMULA_PREFIX = /^[=+\-@\t\r]/;

export function sanitizeCsvFormula(value: string): string {
  return FORMULA_PREFIX.test(value) ? `'${value}` : value;
}

export function escapeCsvCell(value: string): string {
  return `"${sanitizeCsvFormula(value ?? "").replace(/"/g, '""')}"`;
}

export function toCsv(rows: string[][]): string {
  return rows.map((row) => row.map(escapeCsvCell).join(";")).join("\n");
}
