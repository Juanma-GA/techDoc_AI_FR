import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarkdownView } from "./MarkdownView";

describe("MarkdownView", () => {
  it("renders a heading and a paragraph", () => {
    render(<MarkdownView content={"# Titre\n\nUn paragraphe."} />);
    expect(screen.getByRole("heading", { level: 1, name: "Titre" })).toBeInTheDocument();
    expect(screen.getByText("Un paragraphe.")).toBeInTheDocument();
  });

  it("renders an inline code span", () => {
    const { container } = render(<MarkdownView content={"Voir `foo` ici."} />);
    expect(container.querySelector("code")).toHaveTextContent("foo");
  });
});
