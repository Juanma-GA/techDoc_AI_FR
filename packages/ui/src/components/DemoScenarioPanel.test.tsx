import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DemoModeProvider } from "./DemoMode";
import { DemoScenarioPanel } from "./DemoScenarioPanel";
import { createDemoFile, type DemoSampleFile, type DemoScenario } from "../lib/demo";

const labels = {
  title: "Local demo",
  description: "A deterministic local example.",
  scenario: "Scenario",
  sampleFiles: "Sample files",
  run: "Run locally",
  reset: "Reset scenario",
  result: "Result",
  empty: "No scenarios",
  error: "The scenario failed.",
};

const sampleFile: DemoSampleFile = {
  id: "sample",
  name: "sample.txt",
  mediaType: "text/plain",
  content: "Generated in memory.",
};

const scenarios: DemoScenario[] = [
  {
    id: "text-summary",
    title: "Text summary",
    description: "Summarize synthetic text.",
    inputs: [{ id: "text", label: "Example text", initialValue: "Synthetic sample", multiline: true }],
    files: [sampleFile],
    run: ({ inputs, files }) => `${inputs.text}|${files[0]?.name}`,
  },
];

afterEach(() => vi.unstubAllGlobals());

describe("DemoScenarioPanel", () => {
  it("runs deterministically from predefined input and sample files without network calls", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <DemoModeProvider mode="demo" isReady>
        <DemoScenarioPanel scenarios={scenarios} labels={labels} />
      </DemoModeProvider>,
    );

    const input = screen.getByRole("textbox", { name: "Example text" });
    expect(input).toHaveValue("Synthetic sample");
    expect(screen.getByText("sample.txt")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Run locally" }));
    const firstResult = screen.getByLabelText("Result").textContent;
    expect(firstResult).toBe("Synthetic sample|sample.txt");

    fireEvent.change(input, { target: { value: "Temporary edit" } });
    fireEvent.click(screen.getByRole("button", { name: "Reset scenario" }));
    expect(input).toHaveValue("Synthetic sample");
    expect(screen.queryByLabelText("Result")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Run locally" }));
    expect(screen.getByLabelText("Result").textContent).toBe(firstResult);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps scenario data out of normal mode", () => {
    render(
      <DemoModeProvider mode="normal" isReady>
        <DemoScenarioPanel scenarios={scenarios} labels={labels} />
      </DemoModeProvider>,
    );

    expect(screen.queryByText("sample.txt")).not.toBeInTheDocument();
  });

  it("creates sample files in memory", () => {
    const file = createDemoFile(sampleFile);

    expect(file.name).toBe("sample.txt");
    expect(file.type).toBe("text/plain");
    expect(file.size).toBe("Generated in memory.".length);
  });
});