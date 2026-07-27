// Palette de couleurs cyclique pour les categories (« Sujet ») de la checklist,
// utilisee par le graphe temporel empile. Les categories sont dynamiques
// (saisies par l'utilisateur) -> la couleur est assignee par position dans la
// liste (triee par volume), pas par un mapping fige.
export const CATEGORY_COLORS: string[] = [
  "var(--accent-orange, orange)",
  "var(--accent-teal, var(--info, deepskyblue))",
  "var(--accent-purple, mediumpurple)",
  "var(--success, lightgreen)",
  "var(--accent-pink, hotpink)",
  "var(--accent-yellow, gold)",
  "var(--info, steelblue)",
  "var(--warning, goldenrod)",
];
