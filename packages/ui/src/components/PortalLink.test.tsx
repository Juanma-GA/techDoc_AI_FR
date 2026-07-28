import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PortalLink, portalHref } from "./PortalLink";

describe("portalHref", () => {
  it("derives the parent path of a nested deploy base", () => {
    expect(portalHref("/app/atexispocs-cd/corpus-agent/")).toBe("/app/atexispocs-cd/");
  });

  it("returns the site root when the app is one level deep", () => {
    expect(portalHref("/corpus-agent/")).toBe("/");
  });

  it("returns null at the site root (local dev)", () => {
    expect(portalHref("/")).toBeNull();
    expect(portalHref("")).toBeNull();
  });

  it("tolerates a missing trailing slash", () => {
    expect(portalHref("/a/b")).toBe("/a/");
  });
});

describe("PortalLink", () => {
  it("renders an anchor to the parent path when deployed under a portal", () => {
    render(<PortalLink label="Portail" base="/app/atexispocs-cd/corpus-agent/" />);
    const link = screen.getByRole("link", { name: /portail/i });
    expect(link).toHaveAttribute("href", "/app/atexispocs-cd/");
  });

  it("renders nothing in local dev (base = root)", () => {
    const { container } = render(<PortalLink label="Portail" base="/" />);
    expect(container).toBeEmptyDOMElement();
  });
});
