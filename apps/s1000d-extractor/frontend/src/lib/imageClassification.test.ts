import { describe, expect, it } from "vitest";

import { splitImageNames } from "./imageClassification";

describe("splitImageNames", () => {
  it("separates pictograms from illustrations by their extracted filename prefix", () => {
    expect(splitImageNames([
      "figure-1-overview.jpg",
      "picto_chapitre_1.jpg",
      "PICTO_chapitre_2.png",
    ])).toEqual({
      illustrations: ["figure-1-overview.jpg"],
      pictograms: ["picto_chapitre_1.jpg", "PICTO_chapitre_2.png"],
    });
  });
});
