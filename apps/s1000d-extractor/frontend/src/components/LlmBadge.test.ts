import { describe, expect, it } from "vitest";

import { llmBadgeLabelKey, llmBadgeVariant } from "./LlmBadge";
import { humanizeStatus } from "../routes/Versioning";

describe("LLM badge", () => {
  it("maps health states to safe UI variants and translation keys", () => {
    expect(llmBadgeVariant("ok")).toBe("success");
    expect(llmBadgeVariant("disabled")).toBe("danger");
    expect(llmBadgeVariant("untested")).toBe("warning");
    expect(llmBadgeLabelKey("not_configured")).toBe("llm.noKey");
  });
});

describe("version labels", () => {
  it("humanizes machine status tokens", () => {
    expect(humanizeStatus("in_review")).toBe("In Review");
  });
});