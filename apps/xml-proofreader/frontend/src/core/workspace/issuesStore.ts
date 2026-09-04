// F7 (ADR-0027): persist open issues per (user, document) so they survive a
// page reload or app restart. Issues are re-anchored by quote on restore so
// stale source offsets never cause problems. Issues that cannot be re-located
// in the current buffer are silently discarded (the document changed too much).
//
// Key strategy (F-Q3):
//   - uri present  → use it as-is (stable across reloads for the same file).
//   - uri absent   → djb2 hash of the first 4 KB of buffer content (browser/mem).
import type { StoragePort } from "../../ports/StoragePort";
import type { Issue } from "../issues/types";
import { anchorByQuote } from "../issues/anchor";

// djb2 — fast, no external deps, good enough as a storage key fingerprint.
function djb2(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = (((h << 5) + h) ^ s.charCodeAt(i)) >>> 0;
  return h.toString(36);
}

/**
 * Stable document key for the (user, document) namespace.
 * Uses the adapter URI when available; falls back to a content hash.
 */
export function issueDocKey(uri: string | null, buffer: string): string {
  return uri ?? "hash:" + djb2(buffer.slice(0, 4096));
}

const storageKey = (userId: string, docKey: string): string =>
  `issues:${userId}:${docKey}`;

/**
 * Persist the current open issues for (user, document).
 * Callers should pass only the non-ignored issues (i.e. the current store array).
 */
export async function persistIssues(
  storage: StoragePort,
  userId: string,
  docKey: string,
  issues: Issue[]
): Promise<void> {
  await storage.set(storageKey(userId, docKey), issues);
}

/**
 * Load and re-anchor saved issues for (user, document).
 *
 * - Issues with a quote are re-anchored via `anchorByQuote`; those that cannot
 *   be located in `buffer` are discarded (document changed too much).
 * - Issues without a quote are kept as-is (they have no anchor to re-validate).
 * - Returns an empty array when nothing was stored.
 */
export async function restoreIssues(
  storage: StoragePort,
  userId: string,
  docKey: string,
  buffer: string
): Promise<Issue[]> {
  const stored = await storage.get<Issue[]>(storageKey(userId, docKey));
  if (!stored?.length) return [];
  return stored
    .map((issue): Issue | null => {
      if (!issue.quote) return issue;
      const anchor = anchorByQuote(buffer, issue.quote);
      if (!anchor) return null;
      return { ...issue, anchor };
    })
    .filter((x): x is Issue => x !== null);
}
