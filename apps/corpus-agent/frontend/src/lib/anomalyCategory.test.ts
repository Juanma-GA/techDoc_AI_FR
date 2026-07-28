import { describe, expect, it } from "vitest";

import { NO_CATEGORY, categoryOptions, matchesCategory } from "./anomalyCategory";
import type { AnomalyOut } from "./types";

/** Anomalie minimale : seul le `category` compte pour ces helpers. */
function anomaly(category?: string): AnomalyOut {
  return {
    id: "a",
    project_id: "p",
    file_version_id: null,
    type: "personnalisee",
    category,
    severity: "medium",
    confidence: "moyenne",
    message: "",
    suggestion: "",
    status: "open",
  } as AnomalyOut;
}

describe("categoryOptions", () => {
  it("dedoublonne et trie les Sujets presents", () => {
    const opts = categoryOptions(
      [anomaly("Unites"), anomaly("Acronymes"), anomaly("Unites")],
      "fr",
      "Sans sujet",
    );
    expect(opts).toEqual([
      ["Acronymes", "Acronymes"],
      ["Unites", "Unites"],
    ]);
  });

  it("trie en tenant compte des accents (locale FR)", () => {
    const opts = categoryOptions([anomaly("Zone"), anomaly("Éléments")], "fr", "Sans sujet");
    expect(opts.map(([v]) => v)).toEqual(["Éléments", "Zone"]);
  });

  it("n'ajoute l'entree « sans sujet » que si une anomalie n'a pas de categorie", () => {
    expect(categoryOptions([anomaly("Titre")], "fr", "Sans sujet")).toEqual([["Titre", "Titre"]]);

    const withEmpty = categoryOptions([anomaly("Titre"), anomaly(undefined)], "fr", "Sans sujet");
    expect(withEmpty).toEqual([
      ["Titre", "Titre"],
      [NO_CATEGORY, "Sans sujet"],
    ]);
  });

  it("traite une categorie blanche comme absente", () => {
    expect(categoryOptions([anomaly("   ")], "fr", "Sans sujet")).toEqual([
      [NO_CATEGORY, "Sans sujet"],
    ]);
  });

  it("renvoie une liste vide sans anomalie", () => {
    expect(categoryOptions([], "fr", "Sans sujet")).toEqual([]);
  });
});

describe("matchesCategory", () => {
  it("laisse tout passer quand aucun filtre n'est selectionne", () => {
    expect(matchesCategory(anomaly("Titre"), "")).toBe(true);
    expect(matchesCategory(anomaly(undefined), "")).toBe(true);
  });

  it("filtre sur le Sujet exact", () => {
    expect(matchesCategory(anomaly("Titre"), "Titre")).toBe(true);
    expect(matchesCategory(anomaly("Unites"), "Titre")).toBe(false);
  });

  it("ignore les espaces autour du Sujet", () => {
    expect(matchesCategory(anomaly("  Titre  "), "Titre")).toBe(true);
  });

  it("NO_CATEGORY ne retient que les anomalies sans sujet", () => {
    expect(matchesCategory(anomaly(undefined), NO_CATEGORY)).toBe(true);
    expect(matchesCategory(anomaly("   "), NO_CATEGORY)).toBe(true);
    expect(matchesCategory(anomaly("Titre"), NO_CATEGORY)).toBe(false);
  });
});
