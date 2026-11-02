import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageHeader } from "./PageHeader";

describe("PageHeader", () => {
  it("renders the title as the page heading with description and actions", () => {
    render(
      <PageHeader
        eyebrow="Section"
        title="Documents"
        description="All imported documents"
        actions={<button type="button">Import</button>}
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Documents" })).toBeInTheDocument();
    expect(screen.getByText("All imported documents")).toBeInTheDocument();
    expect(screen.getByText("Section")).toHaveClass("label");
    expect(screen.getByRole("button", { name: "Import" }).parentElement).toHaveClass("page-header-actions");
  });

  it("omits optional parts", () => {
    const { container } = render(<PageHeader title="Only" />);
    expect(container.querySelector(".page-header-actions")).toBeNull();
    expect(container.querySelector("p")).toBeNull();
  });
});
