import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Tooltip } from "./Tooltip";

describe("Tooltip", () => {
  it("renders the tooltip content when open", async () => {
    render(
      <Tooltip content="Export as PDF" open>
        <button type="button" aria-label="Export">
          E
        </button>
      </Tooltip>,
    );
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Export as PDF");
  });

  it("renders only the trigger when closed", () => {
    render(
      <Tooltip content="Hidden">
        <button type="button">Trigger</button>
      </Tooltip>,
    );
    expect(screen.getByRole("button", { name: "Trigger" })).toBeInTheDocument();
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});
