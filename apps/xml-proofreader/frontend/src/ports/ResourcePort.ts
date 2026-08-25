// Reads binary resources (images) relative to the open document. Browser can
// only return embedded/absolute resources; Tauri reads sibling files from disk.
export interface ResourcePort {
  /**
   * Read the bytes of `relPath` resolved against the document's `baseUri`.
   * Returns null when the resource can't be accessed in this runtime.
   */
  readBytes(baseUri: string | null, relPath: string): Promise<Uint8Array | null>;
}
