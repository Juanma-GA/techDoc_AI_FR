import { describe, expect, it } from "vitest";

import { escapeCsvCell, sanitizeCsvFormula, toCsv } from "./csv";

describe("sanitizeCsvFormula", () => {
  it.each(["=HYPERLINK(\"http://evil\")", "+1+1", "-1-1", "@SUM(1,1)", "\tcmd", "\rcmd"])(
    "prefixes a leading-formula payload %s with a single quote",
    (payload) => {
      expect(sanitizeCsvFormula(payload)).toBe(`'${payload}`);
    },
  );

  it("leaves ordinary text untouched", () => {
    expect(sanitizeCsvFormula("manual-rev3.pdf")).toBe("manual-rev3.pdf");
  });
});

describe("escapeCsvCell", () => {
  it("quotes and neutralizes a formula-injection payload in a user-controlled cell", () => {
    expect(escapeCsvCell('=cmd|"/c calc"!A1')).toBe('"\'=cmd|""/c calc""!A1"');
  });

  it("quotes ordinary text without altering it", () => {
    expect(escapeCsvCell("STE_PASSIVE_VOICE")).toBe('"STE_PASSIVE_VOICE"');
  });
});

describe("toCsv", () => {
  it("builds a semicolon-separated, formula-safe CSV from uploaded filenames and free-text feedback", () => {
    const csv = toCsv([
      ["fichier", "motif"],
      ["=1+1.pdf", "@import evil"],
    ]);

    expect(csv).toBe('"fichier";"motif"\n"\'=1+1.pdf";"\'@import evil"');
  });
});
