function isDirectory(entry: FileSystemEntry): entry is FileSystemDirectoryEntry {
  return entry.isDirectory;
}
function isFile(entry: FileSystemEntry): entry is FileSystemFileEntry {
  return entry.isFile;
}
async function collect(entry: FileSystemEntry): Promise<File[]> {
  if (isFile(entry)) {
    const file = await new Promise<File>((resolve, reject) => entry.file(resolve, reject));
    const copy = new File([file], file.name, { type: file.type, lastModified: file.lastModified });
    Object.defineProperty(copy, "webkitRelativePath", { value: entry.fullPath.replace(/^\/+/, "") });
    return [copy];
  }
  if (!isDirectory(entry)) return [];
  const reader = entry.createReader();
  const files: File[] = [];
  for (;;) {
    const entries = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
    if (!entries.length) return files;
    for (const child of entries) files.push(...await collect(child));
  }
}
export async function collectDroppedFiles(transfer: DataTransfer): Promise<File[]> {
  const fallback = Array.from(transfer.files);
  const entries = Array.from(transfer.items ?? []).map((item) =>
    typeof item.webkitGetAsEntry === "function" ? item.webkitGetAsEntry() : null,
  ).filter((entry): entry is FileSystemEntry => entry !== null);
  if (!entries.length) return fallback;
  const files: File[] = [];
  for (const entry of entries) files.push(...await collect(entry));
  return files;
}
