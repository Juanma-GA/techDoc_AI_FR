import type { NodeRef } from "../lib/api";

// Libelle + variante de badge (classe .badge du preview-skin) pour une zone.
const ZONE_LABEL: Record<string, string> = {
  header: "entête",
  footer: "pied",
  chapter: "chapitre",
  cover: "page de garde",
  toc: "sommaire",
};

/**
 * Humanize raw machine tokens (snake_case, enum keys) to Title Case.
 * E.g., "zone_unknown_type" → "Zone Unknown Type"
 * Complies with HR21: never render raw machine tokens.
 */
function humanizeToken(token: string): string {
  return token
    .split("_")
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function ZoneFlag({ zone }: { zone?: string }) {
  if (!zone || zone === "body") return null;
  const variant = zone === "chapter" ? "info" : "danger";
  const label = ZONE_LABEL[zone] ?? humanizeToken(zone);
  return <span className={`badge ${variant}`} title="Zone probablement à vérifier">{label}</span>;
}

export function ReviewFlag({ zone }: { zone?: string }) {
  if (!zone || zone === "body" || zone === "chapter") return null;
  return <span className="badge danger" title="Ce contenu peut être du bruit de mise en page">à vérifier</span>;
}

export function PageFlag({ page }: { page?: number | null }) {
  if (page == null) return null;
  return <span className="badge">p.{page}</span>;
}

export function RefFlag({ refs }: { refs?: NodeRef[] | null }) {
  if (!refs || refs.length === 0) return null;
  return <span className="badge info">lien</span>;
}

export function TableFlag({ kind }: { kind: string }) {
  if (kind !== "table") return null;
  return <span className="badge warn">tableau</span>;
}
