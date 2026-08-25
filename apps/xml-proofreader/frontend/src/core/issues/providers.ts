// Local IssueProvider implementations: language-support check and minimal
// schema validation. These run synchronously against the buffer (no network,
// no Tauri). External providers (Oxygen MCP, AI Proofreader) are in later chunks.

import type { IssueProvider, Issue } from "./types";
import { parseXml } from "../xml/parse";
import { detectLanguage } from "../lang/registry";
import { rootElement } from "../xml/tree";

// DITA topic root element names that require an @id attribute.
const DITA_TOPIC_ROOTS = new Set(["topic", "task", "concept", "reference"]);

let _idSeq = 0;
function nextId(prefix: string): string {
  return `${prefix}-${++_idSeq}`;
}

/**
 * Checks whether the document language is supported (DITA or S1000D).
 * Returns no issues: the store's `languageError` state already surfaces this
 * in the Viewer overlay and the Issues tab header, so emitting a duplicate
 * "support" issue would cause redundant UI noise (ADR decision: single source
 * of truth for unsupported-language error is `languageError` in the store).
 * The provider still exists so it can be registered, queried and eventually
 * extended (e.g. project-level language-mismatch checks in a future chunk).
 */
export class SupportProvider implements IssueProvider {
  readonly id = "support" as const;
  readonly label = "Language support";
  isAvailable() { return true; }

  async run(_buffer: string): Promise<Issue[]> {
    return [];
  }
}

/**
 * Minimal schema checks that can be done locally without an XSD/DTD:
 * - DITA topic/task/concept/reference must have @id
 * - S1000D dmodule must contain <identAndStatusSection>
 */
export class SchemaProvider implements IssueProvider {
  readonly id = "schema" as const;
  readonly label = "Schema (minimal)";
  isAvailable() { return true; }

  async run(buffer: string): Promise<Issue[]> {
    let detection: ReturnType<typeof detectLanguage>;
    let tree: ReturnType<typeof parseXml>;
    try {
      tree = parseXml(buffer);
      detection = detectLanguage(tree, buffer);
    } catch {
      return []; // Unsupported languages surface via store.languageError, not as issues
    }

    const root = rootElement(tree);
    if (!root) return [];

    const lang = detection.detection.language;
    const issues: Issue[] = [];

    if (lang === "DITA") {
      if (DITA_TOPIC_ROOTS.has(root.name ?? "") && !root.attrs?.["id"]) {
        issues.push({
          id: nextId("schema"),
          source: "schema",
          severity: "warning",
          message: `Root element <${root.name}> is missing the required @id attribute (DITA 1.3 §2.1.3).`,
        });
      }
    } else if (lang === "S1000D") {
      // identAndStatusSection is required in every S1000D data module (at any depth
      // under the root dmodule, typically inside dmDoc).
      let found = false;
      const check = (nodes: typeof root.children) => {
        for (const c of nodes ?? []) {
          if (c.kind === "element" && c.name === "identAndStatusSection") { found = true; return; }
          if (!found) check(c.children);
        }
      };
      check(root.children);
      if (!found) {
        issues.push({
          id: nextId("schema"),
          source: "schema",
          severity: "warning",
          message: "S1000D data module is missing the required <identAndStatusSection> element.",
        });
      }
    }

    return issues;
  }
}

export function createLocalProviders(): IssueProvider[] {
  return [new SupportProvider(), new SchemaProvider()];
}
