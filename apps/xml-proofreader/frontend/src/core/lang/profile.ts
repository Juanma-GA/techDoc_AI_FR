// Language profile abstraction. The positional XML parser stays generic; each
// supported structured-content language plugs in a profile that detects its
// documents and builds the presentation model. This is what lets the app
// support DITA 1.3 and S1000D (and degrade with a named error otherwise).
import type { PosNode } from "../model/types";
import type { RenderedDoc } from "../render/model";

export interface Detection {
  /** Human language name, e.g. "DITA" or "S1000D". */
  language: string;
  /** Version / issue, e.g. "1.3" or "4.1" ("" if not applicable). */
  version: string;
  /** Profile id, e.g. "dita-1.3" or "s1000d-4.1". */
  profileId: string;
}

export type RefKind =
  | "href"        // @href — standard hyperlink / topic reference
  | "conref"      // DITA @conref
  | "keyref"      // DITA @keyref
  | "conkeyref"   // DITA @conkeyref
  | "s1000d-internal" // S1000D internalRef/@internalRefId
  | "s1000d-dm"   // S1000D dmRef (resolved from dmCode child)
  | "s1000d-pm";  // S1000D pmRef (resolved from pmCode child)

export interface RefAttrDef {
  kind: RefKind;
  /** Attribute name carrying the reference value; empty string if the
   *  reference is resolved from child elements (e.g. dmCode). */
  attr: string;
}

/** Exposes which element/attribute combinations are references in a language. */
export interface LinkPolicy {
  refAttrsFor(gi: string): RefAttrDef[];
}

export interface LanguageProfile {
  readonly id: string;
  readonly language: string;
  /**
   * If this profile recognizes the document, return its Detection (which may
   * refine the version from the document); otherwise return null.
   */
  detect(root: PosNode, buffer: string): Detection | null;
  /** Build the WYSIWYG presentation model. */
  buildRendered(tree: PosNode, buffer: string): RenderedDoc;
  /** Optional link policy; present when the language supports cross-references. */
  linkPolicy?: LinkPolicy;
}

/** Thrown / surfaced when no profile recognizes the document. */
export class UnsupportedLanguageError extends Error {
  constructor(public detectedName: string, public detail: string) {
    super(`Unsupported document language: ${detectedName}`);
    this.name = "UnsupportedLanguageError";
  }
}
