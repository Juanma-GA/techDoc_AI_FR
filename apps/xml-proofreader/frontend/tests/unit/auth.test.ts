// @vitest-environment node
//
// AuthService now talks to the backend's /api/v1/users routes instead of
// browser localStorage (H-NEW-04: password hashes must not live in
// client-accessible storage). These tests exercise AuthService's HTTP layer
// against a tiny in-memory fake of that backend, mirroring the real
// validation rules (duplicate email -> 409, wrong credentials -> 401,
// case-insensitive email) so the client-side contract stays covered without
// spinning up the real FastAPI server.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { AuthService } from "../../src/core/auth/service";

interface FakeUser {
  id: string;
  name: string;
  email: string;
  password: string;
  created_at: number;
}

let db: FakeUser[];
let nextId: number;

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function toPublic(u: FakeUser) {
  return { id: u.id, name: u.name, email: u.email, created_at: u.created_at };
}

async function fakeBackend(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = String(input);
  const method = (init?.method ?? "GET").toUpperCase();
  const body = init?.body ? JSON.parse(String(init.body)) : undefined;

  if (url === "/api/v1/users" && method === "GET") {
    return jsonResponse(200, db.map(toPublic));
  }

  if (url === "/api/v1/users/register" && method === "POST") {
    const email = String(body.email).trim().toLowerCase();
    if (db.some((u) => u.email === email)) {
      return jsonResponse(409, { code: "EMAIL_EXISTS", message: "An account with this email already exists" });
    }
    const user: FakeUser = {
      id: `u_${nextId++}`,
      name: String(body.name).trim(),
      email,
      password: String(body.password),
      created_at: Date.now(),
    };
    db.push(user);
    return jsonResponse(201, toPublic(user));
  }

  if (url === "/api/v1/users/login" && method === "POST") {
    const email = String(body.email).trim().toLowerCase();
    const user = db.find((u) => u.email === email);
    if (!user || user.password !== body.password) {
      return jsonResponse(401, { code: "INVALID_CREDENTIALS", message: "Invalid email or password" });
    }
    return jsonResponse(200, toPublic(user));
  }

  const patchMatch = url.match(/^\/api\/v1\/users\/(.+)$/);
  if (patchMatch && method === "PATCH") {
    const user = db.find((u) => u.id === decodeURIComponent(patchMatch[1]));
    if (!user) return jsonResponse(404, { code: "USER_NOT_FOUND", message: "User not found" });
    user.name = String(body.name).trim();
    user.email = String(body.email).trim().toLowerCase();
    return jsonResponse(200, toPublic(user));
  }

  return jsonResponse(404, { code: "NOT_FOUND", message: "unhandled fake route: " + url });
}

describe("AuthService — backend-backed local accounts (H-NEW-04)", () => {
  let svc: AuthService;

  beforeEach(() => {
    db = [];
    nextId = 1;
    vi.stubGlobal("fetch", vi.fn(fakeBackend));
    svc = new AuthService();
  });

  it("registers a user; the response never carries the password", async () => {
    const u = await svc.register("Maria Ruiz", "maria@atexis.com", "pw12345");
    expect(u.name).toBe("Maria Ruiz");
    expect(JSON.stringify(u)).not.toContain("pw12345");
    expect(JSON.stringify(u)).not.toContain("password");
  });

  it("logs in with correct credentials, rejects bad ones", async () => {
    await svc.register("Jon", "jon@atexis.com", "hunter2");
    expect(await svc.login("jon@atexis.com", "hunter2")).not.toBeNull();
    expect(await svc.login("JON@atexis.com", "hunter2")).not.toBeNull(); // case-insensitive email
    expect(await svc.login("jon@atexis.com", "nope")).toBeNull();
    expect(await svc.login("ghost@atexis.com", "x")).toBeNull();
  });

  it("rejects duplicate email on register", async () => {
    await svc.register("A", "dup@atexis.com", "x");
    await expect(svc.register("B", "dup@atexis.com", "y")).rejects.toThrow(/already exists/);
  });

  it("lists registered users", async () => {
    await svc.register("Persist", "p@atexis.com", "secret");
    const users = await svc.listUsers();
    expect(users.map((u) => u.email)).toContain("p@atexis.com");
  });

  it("updates a profile via PATCH and reflects the new name/email", async () => {
    const created = await svc.register("Old Name", "old@atexis.com", "pw");
    const updated = await svc.updateProfile(created.id, "New Name", "new@atexis.com");
    expect(updated.name).toBe("New Name");
    expect(updated.email).toBe("new@atexis.com");
  });
});
