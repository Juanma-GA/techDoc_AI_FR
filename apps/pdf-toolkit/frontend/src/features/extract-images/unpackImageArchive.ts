import { unzipSync } from "fflate";

export type ExtractedImage = {
  name: string;
  url: string;
  size: number;
  previewable: boolean;
  contentHash: string;
};

export type ExtractedImageGroup = {
  image: ExtractedImage;
  occurrences: number;
};

type ArchiveMessages = {
  invalidArchive: string;
  emptyArchive: string;
};

const imageTypes: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  tif: "image/tiff",
  tiff: "image/tiff",
  webp: "image/webp",
  jpx: "image/jpx",
  jbig2: "image/jbig2",
};

const previewableTypes = new Set(["image/jpeg", "image/png", "image/webp"]);

export async function unpackImageArchive(
  archive: Blob,
  messages: ArchiveMessages,
): Promise<ExtractedImage[]> {
  let entries: Record<string, Uint8Array>;
  try {
    entries = unzipSync(new Uint8Array(await archive.arrayBuffer()));
  } catch {
    throw new Error(messages.invalidArchive);
  }

  const images: ExtractedImage[] = [];
  try {
    for (const [archiveName, data] of Object.entries(entries).sort(([left], [right]) =>
      left.localeCompare(right))) {
      const name = archiveName.replace(/\\/gu, "/").split("/").pop() ?? "";
      const extension = name.split(".").pop()?.toLowerCase() ?? "";
      const mediaType = Object.prototype.hasOwnProperty.call(imageTypes, extension)
        ? imageTypes[extension]
        : undefined;
      if (!name || !mediaType) continue;
      if (data.byteLength === 0) throw new Error(messages.invalidArchive);

      const blobData = Uint8Array.from(data);
      const url = URL.createObjectURL(new Blob([blobData.buffer], { type: mediaType }));
      const digest = await crypto.subtle.digest("SHA-256", blobData.buffer);
      const contentHash = Array.from(new Uint8Array(digest), (byte) =>
        byte.toString(16).padStart(2, "0"),
      ).join("");
      images.push({
        name,
        url,
        size: data.byteLength,
        previewable: previewableTypes.has(mediaType),
        contentHash,
      });
    }
  } catch (reason: unknown) {
    images.forEach((image) => URL.revokeObjectURL(image.url));
    if (reason instanceof Error) throw reason;
    throw new Error(messages.invalidArchive);
  }

  if (images.length === 0) {
    throw new Error(messages.emptyArchive);
  }
  return images;
}

export function groupImagesByContent(images: ExtractedImage[]): ExtractedImageGroup[] {
  const groups = new Map<string, ExtractedImageGroup>();
  for (const image of images) {
    const group = groups.get(image.contentHash);
    if (group) {
      group.occurrences += 1;
    } else {
      groups.set(image.contentHash, { image, occurrences: 1 });
    }
  }
  return [...groups.values()];
}
