/** A local user account as seen by the client. The password never reaches
 * the frontend — hashing and verification happen server-side (see
 * core/auth/service.ts and the backend's /api/v1/users routes). */
export interface User {
  id: string;
  name: string;
  email: string;
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
