import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FileDropzone } from "./FileDropzone";

describe("FileDropzone", () => {
  it("renders the label and description", () => {
    render(<FileDropzone onFiles={() => {}} label="Glissez ici" description="PDF, DOCX" />);
    expect(screen.getByText("Glissez ici")).toBeInTheDocument();
    expect(screen.getByText("PDF, DOCX")).toBeInTheDocument();
  });

  it("calls onFiles when files are selected via the input", async () => {
    const onFiles = vi.fn();
    const { container } = render(<FileDropzone onFiles={onFiles} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["hello"], "test.txt", { type: "text/plain" });
    await userEvent.upload(input, file);
    expect(onFiles).toHaveBeenCalledTimes(1);
    expect(onFiles.mock.calls[0][0][0].name).toBe("test.txt");
  });
});
