// Local account service. Talks to the backend's /api/v1/users routes so that
// emails and password hashes live only in the server's SQLite database, never
// in browser-accessible storage (localStorage was readable via devtools —
// see H-NEW-04 in the hardening checklist). No session/cookie layer: the
// frontend only keeps a non-sensitive "currently selected user id" locally
// (see sessionStore.ts) and re-fetches the account list from the backend.
import type { User } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const BASE = `${API_BASE}/users`;

interface UserApiShape {
  id: string;
  name: string;
  email: string;
  created_at: number;
}

function toUser(raw: UserApiShape): User {
  return { id: raw.id, name: raw.name, email: raw.email, createdAt: raw.created_at };
}

async function parseOrThrow(res: Response): Promise<unknown> {
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const message = (body as { message?: string } | null)?.message ?? `Request failed (${res.status})`;
    throw new Error(message);
  }
  return body;
}

export class AuthService {
  async listUsers(): Promise<User[]> {
    const res = await fetch(BASE);
    const body = (await parseOrThrow(res)) as UserApiShape[];
    return body.map(toUser);
  }

  async register(name: string, email: string, password: string): Promise<User> {
    const res = await fetch(`${BASE}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    return toUser((await parseOrThrow(res)) as UserApiShape);
  }

  async login(email: string, password: string): Promise<User | null> {
    const res = await fetch(`${BASE}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (res.status === 401) return null;
    return toUser((await parseOrThrow(res)) as UserApiShape);
  }

  async updateProfile(userId: string, name: string, email: string): Promise<User> {
    const res = await fetch(`${BASE}/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email }),
    });
    return toUser((await parseOrThrow(res)) as UserApiShape);
  }
}
