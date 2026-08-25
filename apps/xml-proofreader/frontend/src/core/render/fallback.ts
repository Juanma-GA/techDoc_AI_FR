// ============================================================
// Base-type resolution and inline/block classification.
// ============================================================

import type { PosNode } from "../model/types";
import { GI_TO_BASE, INLINE_BASE, INLINE_GI } from "./classMap";

/**
 * Resolve the DITA base type of an element.
 * Priority: @class specialization ancestry → GI lookup → null (unknown).
 *
 * @class looks like "- topic/p task/cmd " (general → specific). The base type
 * is the FIRST token, which is the most general ancestor and the one we render.
 */
export function resolveBaseType(node: PosNode): string | null {
  if (node.kind !== "element") return null;
  if (node.classAttr) {
    const tokens = node.classAttr.trim().replace(/^[-+]\s*/, "").split(/\s+/).filter(Boolean);
    if (tokens.length && tokens[0].includes("/")) return tokens[0];
  }
  return GI_TO_BASE[node.name ?? ""] ?? null;
}

/** Whether an element should be rendered inline (vs. as a block). */
export function isInline(node: PosNode): boolean {
  if (node.kind !== "element") return false;
  const base = resolveBaseType(node);
  if (base && INLINE_BASE.has(base)) return true;
  if (base && !INLINE_BASE.has(base)) {
    // Known block base type → not inline.
    return false;
  }
  // Unknown base: fall back to GI, then to a heuristic (no block children).
  if (INLINE_GI.has(node.name ?? "")) return true;
  return !(node.children ?? []).some((c) => c.kind === "element" && !isInline(c));
}
