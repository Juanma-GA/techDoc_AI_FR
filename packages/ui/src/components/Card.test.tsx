import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Card, CardContent, CardHeader, CardTitle } from "./Card";

describe("Card", () => {
  it("composes header / title / content", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Anomalies</CardTitle>
        </CardHeader>
        <CardContent>3 ouvertes</CardContent>
      </Card>,
    );

    expect(screen.getByRole("heading", { name: "Anomalies" })).toBeInTheDocument();
    expect(screen.getByText("3 ouvertes")).toBeInTheDocument();
  });

  it("forwards className on the root", () => {
    const { container } = render(<Card className="custom" />);
    expect(container.firstChild).toHaveClass("custom");
  });
});
