import type { PasswordHash } from "./passwords";

/** A local user account. Passwords are stored only as PBKDF2 hashes. */
export interface User {
  id: string;
  name: string;
  email: string;
  password: PasswordHash;
  createdAt: number;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}
