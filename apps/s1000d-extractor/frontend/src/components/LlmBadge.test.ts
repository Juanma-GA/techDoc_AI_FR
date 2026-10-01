import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { LlmStatus } from "@internal/ui";
import { humanizeStatus } from "../routes/Versioning";

describe("LLM badge", () => {
  it("renders the disabled state with the shared neutral style", () => {
    const markup = renderToStaticMarkup(
      createElement(LlmStatus, {
        status: "disabled",
        labels: {
          label: "LLM",
          title: "LLM status",
          on: "ON",
          off: "OFF",
          untested: "UNTESTED",
          noKey: "NO KEY",
        },
      }),
    );

    expect(markup).toContain('data-status="disabled"');
    expect(markup).toContain(">OFF</span>");
  });
});

describe("version labels", () => {
  it("humanizes machine status tokens", () => {
    expect(humanizeStatus("in_review")).toBe("In Review");
  });
});