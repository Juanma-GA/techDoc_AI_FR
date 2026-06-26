// Helpers de formatage partagés (dates, tailles, mapping sévérité/confiance).

export function fmtDate(iso: string | null | undefined, lang = "fr"): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(lang === "en" ? "en-GB" : "fr-FR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtBytes(n: number | null | undefined): string {
  const bytes = typeof n === "number" ? n : 0;
  if (bytes < 1024) return `${bytes} o`;
  const units = ["Ko", "Mo", "Go", "To"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

export function severityClass(sev: string): string {
  if (sev === "high") return "danger";
  if (sev === "medium") return "warn";
  return "ok";
}
