// Language detection registry. Tries each profile; refines the S1000D issue
// from the document; throws UnsupportedLanguageError (naming the language) when
// nothing matches.
import type { PosNode } from "../model/types";
import { rootElement } from "../xml/tree";
import { ditaProfile } from "./dita";
import { s1000dProfile, detectIssue } from "./s1000d";
import { UnsupportedLanguageError, type Detection, type LanguageProfile } from "./profile";

const PROFILES: LanguageProfile[] = [ditaProfile, s1000dProfile];

export interface Detected {
  detection: Detection;
  profile: LanguageProfile;
}

function friendlyName(root: PosNode): string {
  const ns = root.attrs?.["xmlns"] ?? "";
  const gi = root.name ?? "unknown";
  if (/docbook/i.test(ns) || gi === "book" || gi === "article") return "DocBook";
  if (/tei-c\.org/i.test(ns)) return "TEI";
  if (ns) return `${gi} (namespace ${ns})`;
  return gi;
}

export function detectLanguage(tree: PosNode, buffer: string): Detected {
  const root = rootElement(tree);
  if (!root) throw new UnsupportedLanguageError("unknown", "No root element found");

  for (const profile of PROFILES) {
    const d = profile.detect(root, buffer);
    if (!d) continue;
    if (profile.id === "s1000d") {
      const v = detectIssue(root, buffer);
      d.version = v;
      d.profileId = v ? `s1000d-${v}` : "s1000d";
    }
    return { detection: d, profile };
  }

  throw new UnsupportedLanguageError(friendlyName(root), `Root <${root.name ?? "?"}>`);
}

export { UnsupportedLanguageError };
