import DiffMatchPatch from "diff-match-patch";

export type DiffSegment = { op: -1 | 0 | 1; text: string };

const dmp = new DiffMatchPatch();

export function inlineDiff(original: string, proposed: string): DiffSegment[] {
  const raw = dmp.diff_main(original, proposed);
  dmp.diff_cleanupSemantic(raw);
  return raw.map(([op, text]) => ({ op: op as -1 | 0 | 1, text }));
}
