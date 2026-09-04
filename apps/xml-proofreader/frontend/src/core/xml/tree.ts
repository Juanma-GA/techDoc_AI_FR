// ============================================================
// Helpers over the positional tree produced by parseXml.
// ============================================================

import type { PosNode } from "../model/types";

/**
 * Reconstruct the exact source of a node purely from recorded offsets,
 * walking the structure (start-tag + children + end-tag). Used by the
 * fidelity tests: for a correctly-parsed buffer, serializeTree(doc) must
 * equal the original buffer byte for byte.
 */
export function serializeTree(node: PosNode, buffer: string): string {
  if (node.kind === "document") {
    return (node.children ?? []).map((c) => serializeTree(c, buffer)).join("");
  }
  if (node.kind !== "element") {
    return buffer.slice(node.start, node.end);
  }
  const children = node.children ?? [];
  const innerStart = node.innerStart ?? node.end;
  const innerEnd = node.innerEnd ?? node.end;
  const startTag = buffer.slice(node.start, innerStart);
  const endTag = buffer.slice(innerEnd, node.end);
  const inner = children.map((c) => serializeTree(c, buffer)).join("");
  return startTag + inner + endTag;
}

/** Depth-first walk over all nodes (document root included). */
export function walk(node: PosNode, visit: (n: PosNode) => void): void {
  visit(node);
  for (const c of node.children ?? []) walk(c, visit);
}

/** The single root element of a document (first element child). */
export function rootElement(doc: PosNode): PosNode | null {
  return (doc.children ?? []).find((c) => c.kind === "element") ?? null;
}

/** Path of child indices from the document root down to `target`. */
export function pathOf(target: PosNode): number[] {
  const path: number[] = [];
  let node: PosNode | undefined = target;
  while (node && node.parent) {
    const idx = node.parent.children!.indexOf(node);
    path.unshift(idx);
    node = node.parent;
  }
  return path;
}

/** Resolve a child-index path (from pathOf) back to a node. */
export function nodeAtPath(doc: PosNode, path: number[]): PosNode | null {
  let node: PosNode = doc;
  for (const idx of path) {
    const child = node.children?.[idx];
    if (!child) return null;
    node = child;
  }
  return node;
}

/**
 * Concatenated text content of an element, *excluding* processing
 * instructions and comments but including descendant element text. This is
 * the coordinate space annotation offsets live in (matching Oxygen, whose
 * inline comment PIs sit between text runs).
 */
export function elementText(node: PosNode, buffer: string): string {
  let out = "";
  for (const c of node.children ?? []) {
    if (c.kind === "text" || c.kind === "cdata") {
      out += c.kind === "cdata" ? cdataText(buffer.slice(c.start, c.end)) : buffer.slice(c.start, c.end);
    } else if (c.kind === "element") {
      out += elementText(c, buffer);
    }
    // pi / comment / doctype contribute no visible text
  }
  return out;
}

function cdataText(raw: string): string {
  // strip the <![CDATA[ ... ]]> wrapper
  return raw.replace(/^<!\[CDATA\[/, "").replace(/\]\]>$/, "");
}

/** Find the first descendant element whose name matches. */
export function firstByName(node: PosNode, name: string): PosNode | null {
  let found: PosNode | null = null;
  walk(node, (n) => {
    if (!found && n.kind === "element" && n.name === name) found = n;
  });
  return found;
}
