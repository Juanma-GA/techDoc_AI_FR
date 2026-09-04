import { describe, it, expect } from "vitest";
import { ResourceResolver, candidatePaths } from "../../src/core/resources/resolver";
import type { ResourcePort } from "../../src/ports/ResourcePort";

class FakePort implements ResourcePort {
  reads = 0;
  constructor(private files: Record<string, Uint8Array>) {}
  async readBytes(_base: string | null, rel: string): Promise<Uint8Array | null> {
    this.reads++;
    return this.files[rel] ?? null;
  }
}
const bytes = (s: string) => new TextEncoder().encode(s);

describe("B5 — image candidate paths", () => {
  it("uses the path as-is when it has an extension", () => {
    expect(candidatePaths("img/diagram.png")).toEqual(["img/diagram.png"]);
  });
  it("probes graphic extensions for an ICN (no extension)", () => {
    const c = candidatePaths("ICN-FLIRT-A-320000-001-01");
    expect(c[0]).toBe("ICN-FLIRT-A-320000-001-01.svg");
    expect(c).toContain("ICN-FLIRT-A-320000-001-01.png");
    expect(c).toContain("ICN-FLIRT-A-320000-001-01.cgm");
  });
});

describe("B5 — ResourceResolver", () => {
  it("passes data: and http(s) URIs straight through", async () => {
    const r = new ResourceResolver(new FakePort({}));
    expect(await r.resolveImage("data:image/png;base64,AAAA", null)).toBe("data:image/png;base64,AAAA");
    expect(await r.resolveImage("https://x/y.png", null)).toBe("https://x/y.png");
  });

  it("inlines an SVG file as a utf8 data URI", async () => {
    const port = new FakePort({ "fig.svg": bytes("<svg/>") });
    const url = await new ResourceResolver(port).resolveImage("fig.svg", "/doc.dita");
    expect(url).toBe("data:image/svg+xml;utf8," + encodeURIComponent("<svg/>"));
  });

  it("inlines a PNG as base64 and resolves an ICN by probing", async () => {
    const port = new FakePort({ "ICN-1.png": new Uint8Array([1, 2, 3]) });
    const url = await new ResourceResolver(port).resolveImage("ICN-1", "/dm.xml");
    expect(url).toMatch(/^data:image\/png;base64,/);
  });

  it("returns null when nothing resolves", async () => {
    expect(await new ResourceResolver(new FakePort({})).resolveImage("missing.png", null)).toBeNull();
  });

  it("caches results (no repeated reads)", async () => {
    const port = new FakePort({ "a.png": new Uint8Array([9]) });
    const r = new ResourceResolver(port);
    await r.resolveImage("a.png", "/d");
    await r.resolveImage("a.png", "/d");
    expect(port.reads).toBe(1);
  });
});
