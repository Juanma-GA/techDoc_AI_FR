// ============================================================
// Platform-agnostic file IO contract. The core/UI never talk to
// Tauri or the browser directly — they depend on this port, which
// is implemented by adapters in src/adapters/*.
// ============================================================

export interface OpenedFile {
  /** Opaque handle/path used to save back to the same file. */
  uri: string;
  fileName: string;
  content: string;
}

export interface FileSystemPort {
  /** Whether saving back to the original file in place is supported. */
  readonly canSaveInPlace: boolean;

  /** Prompt the user to pick an XML/DITA file and return its contents. */
  openFile(): Promise<OpenedFile | null>;

  /**
   * Save `content` back to `uri`. Adapters that support it create a
   * `.bak` of the previous contents first. Returns the (possibly new) uri.
   */
  saveFile(uri: string | null, fileName: string, content: string): Promise<string>;

  /** Save `content` to a user-chosen location (Export / Save As). */
  saveFileAs(suggestedName: string, content: string): Promise<string | null>;

  /** Persist a temporary working copy for crash recovery (autosave). */
  saveTemp(key: string, content: string): Promise<void>;

  /** Read a previously persisted temporary working copy, if any. */
  readTemp(key: string): Promise<string | null>;

  /** Remove a temporary working copy. */
  clearTemp(key: string): Promise<void>;
}
