import type { Issue } from "./types";

/**
 * Merge `incoming` issues into `existing` strictly additively (G3, ADR-0030).
 *
 * All `existing` issues are preserved regardless of source.  Each issue in
 * `incoming` is appended only if it is not already present by the dedup key
 * (source, message, quote, anchor.startOffset).  Duplicates within `incoming`
 * are also discarded.  Running the Proofreader (or any provider) N times
 * therefore accumulates new findings and never erases prior ones.
 */
export function mergeIssuesAdditive(existing: Issue[], incoming: Issue[]): Issue[] {
  if (incoming.length === 0) return existing;
  const seen = new Set<string>(existing.map(issueKey));
  const toAdd: Issue[] = [];
  for (const x of incoming) {
    const k = issueKey(x);
    if (!seen.has(k)) {
      seen.add(k);
      toAdd.push(x);
    }
  }
  return toAdd.length === 0 ? existing : [...existing, ...toAdd];
}

function issueKey(x: Issue): string {
  const offset = x.anchor?.startOffset ?? "";
  return `${x.source}\0${x.message}\0${x.quote ?? ""}\0${offset}`;
}
