import type { NodeRef } from "../lib/api";

// Libelle + variante de badge (classe .badge du preview-skin) pour une zone.
const ZONE_LABEL: Record<string, string> = {
  header: "entête",
  footer: "pied",
  chapter: "chapitre",
};

export function ZoneFlag({ zone }: { zone?: string }) {
  if (!zone || zone === "body") return null;
  const variant = zone === "chapter" ? "info" : "off";
  return <span className={`badge ${variant}`}>{ZONE_LABEL[zone] ?? zone}</span>;
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
