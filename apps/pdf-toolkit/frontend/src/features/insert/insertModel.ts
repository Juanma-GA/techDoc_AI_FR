import { parsePageSelection } from "../split/splitModel";

export type InsertPosition = "start" | "after" | "end";

/** Empty selection means every source page; otherwise typed order is kept. */
export function resolveSourcePages(selection: string, sourceCount: number): number[] | null {
  if (sourceCount < 1) return null;
  if (!selection.trim()) return Array.from({ length: sourceCount }, (_, index) => index + 1);
  return parsePageSelection(selection, sourceCount);
}

/** Returns the number of target pages kept before the inserted pages. */
export function resolveInsertAfter(
  position: InsertPosition,
  afterPage: string,
  targetCount: number,
): number | null {
  if (targetCount < 1) return null;
  if (position === "start") return 0;
  if (position === "end") return targetCount;
  const trimmed = afterPage.trim();
  if (!/^\d+$/u.test(trimmed)) return null;
  const page = Number(trimmed);
  return page >= 1 && page <= targetCount ? page : null;
}
