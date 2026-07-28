import type { AnomalyOut } from "./types";

/**
 * Filtre « Catégorie » de la Vue Rédacteur.
 *
 * En mode checklist-only le `type` d'une anomalie vaut toujours
 * `personnalisee` : la seule dimension métier exploitable est la `category`,
 * qui reprend le « Sujet » de la règle checklist saisi librement dans l'Excel.
 * Les options ne peuvent donc pas venir d'une liste figée ni de clés i18n :
 * elles se déduisent des anomalies réellement présentes.
 */

/**
 * Valeur sentinelle des anomalies sans sujet. Un caractère NUL ne peut pas
 * provenir d'une cellule Excel : aucune collision possible avec un Sujet saisi
 * par l'utilisateur.
 */
export const NO_CATEGORY = "\u0000";

/** Sujet normalisé d'une anomalie ("" si absent ou blanc). */
function categoryOf(a: AnomalyOut): string {
  return a.category?.trim() ?? "";
}

/**
 * Options du filtre, triées alphabétiquement selon `locale`. L'entrée « sans
 * sujet » (libellé `noCategoryLabel`) n'est ajoutée que si au moins une anomalie
 * n'a pas de catégorie. À calculer sur les anomalies NON filtrées, pour que le
 * menu ne rétrécisse pas au fil des sélections.
 */
export function categoryOptions(
  anomalies: AnomalyOut[],
  locale: string,
  noCategoryLabel: string,
): Array<readonly [string, string]> {
  const seen = new Set<string>();
  let hasUncategorised = false;
  for (const a of anomalies) {
    const c = categoryOf(a);
    if (c) seen.add(c);
    else hasUncategorised = true;
  }
  const opts: Array<readonly [string, string]> = [...seen]
    .sort((x, y) => x.localeCompare(y, locale))
    .map((c) => [c, c] as const);
  if (hasUncategorised) opts.push([NO_CATEGORY, noCategoryLabel] as const);
  return opts;
}

/** `selected` vide = pas de filtre. `NO_CATEGORY` = anomalies sans sujet. */
export function matchesCategory(a: AnomalyOut, selected: string): boolean {
  if (!selected) return true;
  const c = categoryOf(a);
  return selected === NO_CATEGORY ? !c : c === selected;
}
