import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ChartCard } from "./ChartCard";

describe("ChartCard", () => {
  it("renders title and children", () => {
    render(
      <ChartCard title="Revenue">
        <div>chart-placeholder</div>
      </ChartCard>,
    );
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("chart-placeholder")).toBeInTheDocument();
  });

  it("renders an optional badge", () => {
    render(
      <ChartCard title="Sales" badge={{ label: "Q1", variant: "default" }}>
        <div />
      </ChartCard>,
    );
    expect(screen.getByText("Sales")).toBeInTheDocument();
    expect(screen.getByText("Q1")).toBeInTheDocument();
  });

  it("applies wide class when wide=true", () => {
    const { container } = render(
      <ChartCard title="Wide" wide>
        <div />
      </ChartCard>,
    );
    expect(container.querySelector(".col-span-full")).not.toBeNull();
  });
});
