import { zipSync } from "fflate";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { groupImagesByContent, unpackImageArchive } from "./unpackImageArchive";

const originalCreateObjectURL = URL.createObjectURL;
const originalRevokeObjectURL = URL.revokeObjectURL;
let nextObjectUrl = 0;
const createObjectURL = vi.fn(() => `blob:extracted-${++nextObjectUrl}`);
const revokeObjectURL = vi.fn();

const messages = {
  invalidArchive: "Invalid archive",
  emptyArchive: "No images",
};

beforeEach(() => {
  nextObjectUrl = 0;
  createObjectURL.mockClear();
  revokeObjectURL.mockClear();
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
});

afterEach(() => {
  restoreURLMethod("createObjectURL", originalCreateObjectURL);
  restoreURLMethod("revokeObjectURL", originalRevokeObjectURL);
});

describe("unpackImageArchive", () => {
  it("extracts supported image entries and marks browser previews", async () => {
    const bytes = zipSync({
      "page-0001-image-0001.png": new Uint8Array([137, 80, 78, 71]),
      "page-0001-image-0002.jbig2": new Uint8Array([1, 2, 3]),
    });

    const images = await unpackImageArchive(
      new Blob([bytes], { type: "application/zip" }),
      messages,
    );

    expect(images).toEqual([
      {
        name: "page-0001-image-0001.png",
        url: "blob:extracted-1",
        size: 4,
        previewable: true,
        contentHash: expect.stringMatching(/^[0-9a-f]{64}$/u),
      },
      {
        name: "page-0001-image-0002.jbig2",
        url: "blob:extracted-2",
        size: 3,
        previewable: false,
        contentHash: expect.stringMatching(/^[0-9a-f]{64}$/u),
      },
    ]);
    expect(images[0]?.contentHash).not.toBe(images[1]?.contentHash);
  });

  it("groups byte-identical image entries and keeps different images separate", async () => {
    const bytes = zipSync({
      "page-0001-logo.png": new Uint8Array([1, 2, 3]),
      "page-0002-logo.png": new Uint8Array([1, 2, 3]),
      "page-0002-photo.png": new Uint8Array([3, 2, 1]),
    });

    const images = await unpackImageArchive(
      new Blob([bytes], { type: "application/zip" }),
      messages,
    );

    expect(
      groupImagesByContent(images).map(({ image, occurrences }) => ({
        name: image.name,
        occurrences,
      })),
    ).toEqual([
      { name: "page-0001-logo.png", occurrences: 2 },
      { name: "page-0002-photo.png", occurrences: 1 },
    ]);
  });

  it("reports invalid archives", async () => {
    await expect(unpackImageArchive(new Blob(["not a zip"]), messages)).rejects.toThrow(
      messages.invalidArchive,
    );
  });

  it("reports archives without images", async () => {
    const bytes = zipSync({ "readme.txt": new Uint8Array([1]) });
    await expect(
      unpackImageArchive(new Blob([bytes], { type: "application/zip" }), messages),
    ).rejects.toThrow(messages.emptyArchive);
  });

  it("releases object URLs if an archive contains an empty image", async () => {
    const bytes = zipSync({
      "a.png": new Uint8Array([1]),
      "z-empty.png": new Uint8Array(),
    });
    await expect(
      unpackImageArchive(new Blob([bytes], { type: "application/zip" }), messages),
    ).rejects.toThrow(messages.invalidArchive);
    expect(revokeObjectURL).toHaveBeenCalledOnce();
  });
});

function restoreURLMethod(
  name: "createObjectURL" | "revokeObjectURL",
  original: typeof URL.createObjectURL | typeof URL.revokeObjectURL | undefined,
): void {
  if (original) {
    Object.defineProperty(URL, name, { configurable: true, value: original });
  } else {
    Reflect.deleteProperty(URL, name);
  }
}
