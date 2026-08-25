// ============================================================
// Non-destructive buffer editing.
//
// All document mutations are expressed as a set of edits against the original
// XML buffer: insertions at an offset and deletions of an offset range.
// Edits are applied from the highest offset to the lowest so earlier offsets
// stay valid. Everything outside the touched ranges is preserved byte for
// byte — the cornerstone of Oxygen round-trip fidelity.
// ============================================================

export interface InsertEdit {
  type: "insert";
  /** Offset in the original buffer at which to insert. */
  at: number;
  text: string;
}

export interface DeleteEdit {
  type: "delete";
  start: number;
  end: number;
}

export type Edit = InsertEdit | DeleteEdit;

function editLow(e: Edit): number {
  return e.type === "insert" ? e.at : e.start;
}

/**
 * Apply edits to `buffer`. Edits must not overlap (deletions may not cover the
 * same span; an insertion may sit at a deletion boundary). Applied right-to-left.
 */
export function applyEdits(buffer: string, edits: Edit[]): string {
  // Sort by descending position. For equal positions, deletions before
  // insertions so an insert-at-boundary lands outside a removed range.
  const sorted = [...edits].sort((a, b) => {
    const d = editLow(b) - editLow(a);
    if (d !== 0) return d;
    if (a.type === b.type) return 0;
    return a.type === "delete" ? -1 : 1;
  });

  let out = buffer;
  for (const e of sorted) {
    if (e.type === "insert") {
      out = out.slice(0, e.at) + e.text + out.slice(e.at);
    } else {
      out = out.slice(0, e.start) + out.slice(e.end);
    }
  }
  return out;
}

/** Convenience: insert several strings, each at its own offset. */
export function insertAll(buffer: string, inserts: Array<{ at: number; text: string }>): string {
  return applyEdits(
    buffer,
    inserts.map((i) => ({ type: "insert", at: i.at, text: i.text }) as InsertEdit)
  );
}
