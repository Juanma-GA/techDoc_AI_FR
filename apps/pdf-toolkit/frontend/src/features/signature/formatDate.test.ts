import { describe, expect, it } from "vitest";

import { formatSignatureDate } from "./formatDate";

describe("formatSignatureDate", () => {
  it("formats a selected date according to the interface language", () => {
    expect(formatSignatureDate("2026-10-22", "fr")).toBe("22/10/2026");
    expect(formatSignatureDate("2026-10-22", "en")).toBe("10/22/2026");
  });

  it("omits empty or invalid dates", () => {
    expect(formatSignatureDate("", "fr")).toBe("");
    expect(formatSignatureDate("2026-02-31", "fr")).toBe("");
  });
});
