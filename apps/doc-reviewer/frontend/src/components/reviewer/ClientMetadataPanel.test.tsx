import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { missingDocumentContext, type Document } from "../../types/domain";

const mocks = vi.hoisted(() => ({
  useClientConfig: vi.fn(),
  usePatchDocumentMeta: vi.fn(),
  useSuggestDocumentMetadata: vi.fn(),
}));

vi.mock("../../hooks/useClientConfig", () => ({
  useClientConfig: mocks.useClientConfig,
}));
vi.mock("../../hooks/useDocuments", () => ({
  usePatchDocumentMeta: mocks.usePatchDocumentMeta,
  useSuggestDocumentMetadata: mocks.useSuggestDocumentMetadata,
}));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "fr" },
  }),
}));

import { ClientMetadataPanel } from "./ClientMetadataPanel";

const suggestions = {
  pages_scanned: 4,
  meta_cmm_number: "80-80-01",
  meta_pnr_number: ["1-900-SB"],
  meta_revision_number: "01",
  meta_revision_date: "JUL 27/26",
  meta_first_issue_date: "JUL 25/95",
};

const fields = {
  meta_cmm_number: { type: "string", required: true },
  meta_pnr_number: { type: "string_list", required: false },
  meta_revision_number: { type: "string", required: true },
  meta_revision_date: { type: "string", required: true },
  meta_first_issue_date: { type: "string", required: true },
  meta_manufacturer: {
    type: "enum",
    required: true,
    default: "Airbus",
    allowed_values: ["Airbus", "Boeing"],
  },
  document_language: {
    type: "enum",
    required: true,
    default: "en",
    allowed_values: ["fr", "en"],
  },
};

const fixtureDocument: Document = {
  id: "c1a73a2d-2425-4b42-b469-1084f4cf07dd",
  original_filename: "manual.pdf",
  sha256: "a".repeat(64),
  page_count: 4,
  target_unit_system: "auto",
  standard_version_id: null,
  status: "uploaded",
  current_version: 0,
  source_format: "pdf",
  working_format: "pdf",
  convert_engine: "pdf",
  text_coverage: 100,
  quality: "analyzable",
  client_metadata: {
    meta_cmm_number: "79-30-02",
    meta_pnr_number: ["old-pnr"],
    meta_revision_number: "02",
    meta_revision_date: "MAR 77",
    meta_first_issue_date: "JUL 1966",
    meta_manufacturer: "Boeing",
    document_language: "en",
  },
  meta_revision_date: "MAR 77",
  meta_cmm_number: "79-30-02",
  meta_first_issue_date: "JUL 1966",
  meta_last_issue_date: null,
  meta_revision_number: "02",
  meta_pnr_number: "old-pnr",
  meta_manufacturer: "Boeing",
  document_language: "en",
  created_at: "2026-01-01T00:00:00Z",
};

describe("ClientMetadataPanel metadata suggestions", () => {
  let container: HTMLDivElement;
  let root: Root;
  let save: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
      value: true,
      configurable: true,
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    save = vi.fn();
    mocks.useClientConfig.mockReturnValue({
      data: { mapping: { fields }, norm_mappings: {} },
      isLoading: false,
      isError: false,
    });
    mocks.usePatchDocumentMeta.mockReturnValue({
      mutate: save,
      isPending: false,
    });
    mocks.useSuggestDocumentMetadata.mockReturnValue({
      mutate: (_variables: unknown, options: { onSuccess?: (value: typeof suggestions) => void }) =>
        options.onSuccess?.(suggestions),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: null,
      error: null,
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  it("replaces the draft with suggestions but saves only after explicit confirmation", async () => {
    await act(async () => {
      root.render(<ClientMetadataPanel document={fixtureDocument} />);
    });

    await act(async () => {
      container.querySelector("button")?.click();
    });

    const detectButton = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("reviewer.meta.detectFromPdf"),
    );
    expect(detectButton).toBeDefined();
    await act(async () => detectButton?.click());

    expect(save).not.toHaveBeenCalled();
    expect(
      container.querySelector('input[value="80-80-01"]'),
    ).not.toBeNull();
    expect(
      [...container.querySelectorAll("textarea")].some(
        (textarea) => textarea.value === "1-900-SB",
      ),
    ).toBe(true);
    expect(
      [...container.querySelectorAll("select")].map((select) => select.value),
    ).toEqual(["Airbus", "en"]);

    const saveButton = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("reviewer.meta.save"),
    );
    expect(saveButton).toBeDefined();
    await act(async () => saveButton?.click());

    expect(save).toHaveBeenCalledWith(
      {
        client_metadata: {
          meta_cmm_number: "80-80-01",
          meta_pnr_number: ["1-900-SB"],
          meta_revision_number: "01",
          meta_revision_date: "JUL 27/26",
          meta_first_issue_date: "JUL 25/95",
          meta_manufacturer: "Airbus",
          document_language: "en",
        },
      },
      expect.objectContaining({ onError: expect.any(Function), onSuccess: expect.any(Function) }),
    );
  });

  it("uses the selected S1000D mapping to validate the first-issue year", async () => {
    const s1000dFields = {
      ...fields,
      meta_first_issue_date: {
        type: "string",
        required: true,
        max_length: 4,
        pattern: "\\d{4}",
      },
    };
    mocks.useClientConfig.mockReturnValue({
      data: {
        mapping: { fields },
        norm_mappings: { s1000d: { fields: s1000dFields } },
      },
      isLoading: false,
      isError: false,
    });
    const document = {
      ...fixtureDocument,
      client_metadata: {
        ...fixtureDocument.client_metadata,
        meta_first_issue_date: "2024",
      },
      meta_first_issue_date: "2024",
    };
    await act(async () => {
      root.render(<ClientMetadataPanel document={document} norm="s1000d" />);
    });

    await act(async () => container.querySelector("button")?.click());

    const firstIssueLabel = [...container.querySelectorAll("label")].find((label) =>
      label.textContent?.includes("meta_first_issue_date"),
    );
    expect(firstIssueLabel?.querySelector("input")?.getAttribute("aria-invalid")).not.toBe("true");
  });

  it("uses isolated mapping values without falling back to verification metadata", async () => {
    const saveMapping = vi.fn().mockResolvedValue(undefined);
    await act(async () => {
      root.render(
        <ClientMetadataPanel
          document={fixtureDocument}
          mappingValues={{ meta_cmm_number: "80-80-01" }}
          onSaveMapping={saveMapping}
          titleKey="preparation.mappingTitle"
          subtitleKey="preparation.mappingSubtitle"
        />,
      );
    });

    expect(container.querySelector('input[value="80-80-01"]')).not.toBeNull();
    expect(container.querySelector('input[value="79-30-02"]')).toBeNull();
    expect(container.querySelector('input[value="MAR 77"]')).toBeNull();
    expect(container.textContent).toContain("preparation.mappingTitle");
  });

  it("checks required context against preparation mapping without verification fallbacks", () => {
    expect(
      missingDocumentContext(fixtureDocument, ["meta_cmm_number"], {
        meta_cmm_number: "80-80-01",
      }),
    ).toEqual([]);
    expect(
      missingDocumentContext(fixtureDocument, ["meta_cmm_number"], {
        meta_cmm_number: "",
      }),
    ).toEqual(["meta_cmm_number"]);
  });
});
