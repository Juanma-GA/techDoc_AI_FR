import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Compose Tailwind class strings with conflict-aware merging.
 * Use this anywhere variants/conditional classes are concatenated.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
