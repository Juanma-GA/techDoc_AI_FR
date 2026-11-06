import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Ai4TechDocLogo, setAi4TechDocFavicon } from "./Ai4TechDocLogo";

let stopObservingFavicon: (() => void) | undefined;

afterEach(() => {
  stopObservingFavicon?.();
  stopObservingFavicon = undefined;
  document.head.querySelector('link[data-ai4techdoc-favicon="true"]')?.remove();
  document.documentElement.classList.remove("dark");
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Ai4TechDocLogo", () => {
  it("renders the canonical AI4TECHDOC SVG with an accessible name", () => {
    render(<Ai4TechDocLogo />);

    const logo = screen.getByRole("img", { name: "AI4TECHDOC" });
    expect(logo.getAttribute("src")).toContain("ai4techdoc.svg");
  });

  it("follows the app theme when its dark class changes", async () => {
    render(<Ai4TechDocLogo />);

    const logo = screen.getByRole("img", { name: "AI4TECHDOC" });
    expect(logo).toHaveStyle({ colorScheme: "light" });

    act(() => document.documentElement.classList.add("dark"));
    await waitFor(() => expect(logo).toHaveStyle({ colorScheme: "dark" }));

    act(() => document.documentElement.classList.remove("dark"));
    await waitFor(() => expect(logo).toHaveStyle({ colorScheme: "light" }));
  });

  it("renders and updates the favicon using the app theme", async () => {
    const imageThemes: string[] = [];
    function MockImage() {
      const image = document.createElement("img");
      Object.defineProperty(image, "src", {
        set: () => {
          imageThemes.push(image.style.colorScheme);
          queueMicrotask(() => image.onload?.());
        },
      });
      return image;
    }
    const canvasContext = { drawImage: vi.fn() } as unknown as CanvasRenderingContext2D;
    vi.stubGlobal("Image", MockImage);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(canvasContext);
    vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue(
      "data:image/png;base64,ai4techdoc",
    );

    stopObservingFavicon = setAi4TechDocFavicon();
    const favicon = document.head.querySelector<HTMLLinkElement>(
      'link[data-ai4techdoc-favicon="true"]',
    );
    expect(favicon).not.toBeNull();
    await waitFor(() => expect(favicon?.href).toBe("data:image/png;base64,ai4techdoc"));
    expect(imageThemes).toEqual(["light"]);

    act(() => document.documentElement.classList.add("dark"));
    await waitFor(() => expect(imageThemes).toEqual(["light", "dark"]));
    await waitFor(() => expect(favicon?.type).toBe("image/png"));
  });
});
