// 6 familles métier couvrant les 17 types d'anomalies (mapping + couleurs
// identiques au preview.html::renderOverTimeChart). dmc_missing n'y figure pas
// (carte « Couverture » dédiée).
export type Series = { keys: string[]; labelKey: string; color: string };

export const OVER_TIME_SERIES: Series[] = [
  { keys: ["script", "granule"], labelKey: "manager.fam.scriptGranule", color: "var(--accent-orange, var(--warning, orange))" },
  { keys: ["texte", "orthographe", "entete"], labelKey: "manager.fam.texte", color: "var(--accent-yellow, gold)" },
  { keys: ["ordre_taches", "tache_induite", "preliminaire", "securite", "complementaire"], labelKey: "manager.fam.taches", color: "var(--success, lightgreen)" },
  { keys: ["rechange", "outillage", "infrastructure"], labelKey: "manager.fam.logistique", color: "var(--accent-pink, hotpink)" },
  { keys: ["valeur_numerique", "serrage"], labelKey: "manager.fam.valeurs", color: "var(--accent-purple, mediumpurple)" },
  { keys: ["illustration", "personnalisee"], labelKey: "manager.fam.illustration", color: "var(--accent-teal, var(--info, deepskyblue))" },
];
