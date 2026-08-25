// @vitest-environment node
import { describe, it, expect, beforeEach } from "vitest";
import { hashPassword, verifyPassword } from "../../src/core/auth/passwords";
import { AuthService } from "../../src/core/auth/service";
import type { StoragePort } from "../../src/ports/StoragePort";

class MemStorage implements StoragePort {
  private m = new Map<string, string>();
  async get<T>(k: string): Promise<T | null> {
    const v = this.m.get(k);
    return v ? (JSON.parse(v) as T) : null;
  }
  async set<T>(k: string, v: T): Promise<void> { this.m.set(k, JSON.stringify(v)); }
  async remove(k: string): Promise<void> { this.m.delete(k); }
}

describe("B1 — password hashing", () => {
  it("hashes and verifies; rejects wrong password", async () => {
    const h = await hashPassword("S3cret!");
    expect(h.hashHex).toMatch(/^[0-9a-f]{64}$/);
    expect(h.saltHex).toMatch(/^[0-9a-f]{32}$/);
    expect(await verifyPassword("S3cret!", h)).toBe(true);
    expect(await verifyPassword("wrong", h)).toBe(false);
  });
  it("uses a random salt (distinct hashes for same password)", async () => {
    const a = await hashPassword("same");
    const b = await hashPassword("same");
    expect(a.hashHex).not.toBe(b.hashHex);
  });
});

describe("B1 — local account service", () => {
  let svc: AuthService;
  let store: MemStorage;
  beforeEach(() => { store = new MemStorage(); svc = new AuthService(store); });

  it("registers a user without storing plaintext password", async () => {
    const u = await svc.register("Maria Ruiz", "maria@atexis.com", "pw12345");
    expect(u.name).toBe("Maria Ruiz");
    const raw = JSON.stringify(await svc.listUsers());
    expect(raw).not.toContain("pw12345");
  });

  it("logs in with correct credentials, rejects bad ones", async () => {
    await svc.register("Jon", "jon@atexis.com", "hunter2");
    expect(await svc.login("jon@atexis.com", "hunter2")).not.toBeNull();
    expect(await svc.login("JON@atexis.com", "hunter2")).not.toBeNull(); // case-insensitive email
    expect(await svc.login("jon@atexis.com", "nope")).toBeNull();
    expect(await svc.login("ghost@atexis.com", "x")).toBeNull();
  });

  it("rejects duplicate email", async () => {
    await svc.register("A", "dup@atexis.com", "x");
    await expect(svc.register("B", "dup@atexis.com", "y")).rejects.toThrow(/already exists/);
  });

  it("persists across service instances (same storage)", async () => {
    await svc.register("Persist", "p@atexis.com", "secret");
    const svc2 = new AuthService(store);
    expect(await svc2.login("p@atexis.com", "secret")).not.toBeNull();
  });
});
