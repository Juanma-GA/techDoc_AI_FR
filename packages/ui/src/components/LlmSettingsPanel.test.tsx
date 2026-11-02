import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LlmSettingsPanel, type LlmSettingsValue } from "./LlmSettingsPanel";

const labels = {
  title: "Mistral configuration",
  configured: "CONFIGURED",
  notConfigured: "NOT CONFIGURED",
  disabled: "OFF",
  enabled: "LLM enabled",
  enabledHint: "Disabling skips AI tasks.",
  apiKey: "API key",
  apiKeyKeep: "Leave empty to keep the saved key.",
  apiKeyUnreadable: "The saved key cannot be read.",
  baseUrl: "Base URL",
  models: { chat: "Chat model", embed: "Embeddings model", vision: "Vision model" },
  optionalModel: "Optional.",
  modelsHint: "Run the connection test to list models.",
  save: "Save",
  test: "Test connection",
  loading: "Loading",
};

const configured: LlmSettingsValue = {
  llmEnabled: true,
  apiKeySet: true,
  apiKeyPreview: "sk-...a1b2",
  baseUrl: "https://api.mistral.ai",
  models: { chat: "mistral-medium-latest", embed: "" },
};

function setup(overrides: Partial<Parameters<typeof LlmSettingsPanel>[0]> = {}) {
  const props = {
    value: configured,
    labels,
    onSave: vi.fn(),
    onTest: vi.fn(),
    onToggleEnabled: vi.fn(),
    ...overrides,
  };
  render(<LlmSettingsPanel {...props} />);
  return props;
}

const toggle = () => screen.getByRole("button", { name: /Mistral configuration/ });

describe("LlmSettingsPanel", () => {
  it("is collapsed once a key is configured and keeps the LLM switch visible", () => {
    setup();
    expect(toggle()).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("CONFIGURED")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "LLM enabled" })).toHaveAttribute("aria-checked", "true");
  });

  it("is open when no key is configured", () => {
    setup({ value: { ...configured, apiKeySet: false } });
    expect(toggle()).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("NOT CONFIGURED")).toBeInTheDocument();
  });

  it("shows the disabled badge and forwards the switch", async () => {
    const props = setup({ value: { ...configured, llmEnabled: false } });
    expect(screen.getByText("OFF")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("switch", { name: "LLM enabled" }));
    expect(props.onToggleEnabled).toHaveBeenCalledWith(true);
  });

  it("saves the draft, sends the key only when typed and clears it on success", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    setup({ onSave, defaultOpen: true });
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenLastCalledWith({
      baseUrl: "https://api.mistral.ai",
      models: { chat: "mistral-medium-latest", embed: "" },
    });

    const key = screen.getByLabelText("API key");
    await userEvent.type(key, "sk-new");
    await userEvent.clear(screen.getByLabelText("Chat model"));
    await userEvent.type(screen.getByLabelText("Chat model"), "mistral-small-latest");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenLastCalledWith({
      apiKey: "sk-new",
      baseUrl: "https://api.mistral.ai",
      models: { chat: "mistral-small-latest", embed: "" },
    });
    await waitFor(() => expect(key).toHaveValue(""));
  });

  it("offers provider models as suggestions and renders configured model fields", () => {
    setup({
      defaultOpen: true,
      modelFields: ["chat", "vision"],
      availableModels: ["mistral-medium-latest", "pixtral-large-latest"],
    });
    const chat = screen.getByLabelText("Chat model");
    const listId = chat.getAttribute("list");
    expect(listId).toBeTruthy();
    const options = document.getElementById(listId ?? "")?.querySelectorAll("option");
    expect(options).toHaveLength(2);
    expect(screen.getByLabelText("Vision model")).toBeInTheDocument();
    expect(screen.queryByLabelText("Embeddings model")).toBeNull();
    expect(screen.queryByText("Run the connection test to list models.")).toBeNull();
  });

  it("runs the test, shows feedback, app-specific children and the unreadable-key warning", async () => {
    const props = setup({
      defaultOpen: true,
      value: { ...configured, apiKeyUnreadable: true },
      feedback: { kind: "success", message: "Models checked." },
      children: <p>App-specific option</p>,
    });
    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));
    expect(props.onTest).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Models checked.")).toBeInTheDocument();
    expect(screen.getByText("App-specific option")).toBeInTheDocument();
    expect(screen.getByText("The saved key cannot be read.")).toBeInTheDocument();
    expect(screen.getByText("Run the connection test to list models.")).toBeInTheDocument();
  });

  it("shows a loading state without value", () => {
    setup({ value: undefined, defaultOpen: true });
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(screen.getByRole("switch", { name: "LLM enabled" })).toBeDisabled();
  });
});
