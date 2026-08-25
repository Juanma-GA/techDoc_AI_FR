// Local account service. Pure logic over a StoragePort — no UI deps, fully
// testable with an in-memory storage. (SSO is a future extension point: a
// remote AuthService implementing the same shape could replace this.)
import type { StoragePort } from "../../ports/StoragePort";
import { hashPassword, verifyPassword } from "./passwords";
import type { User } from "./types";

const USERS_KEY = "users";

export class AuthService {
  constructor(private storage: StoragePort) {}

  async listUsers(): Promise<User[]> {
    return (await this.storage.get<User[]>(USERS_KEY)) ?? [];
  }

  async register(name: string, email: string, password: string): Promise<User> {
    const users = await this.listUsers();
    const norm = email.trim().toLowerCase();
    if (users.some((u) => u.email.toLowerCase() === norm)) {
      throw new Error("An account with this email already exists");
    }
    const user: User = {
      id: "u_" + Math.random().toString(36).slice(2, 10),
      name: name.trim(),
      email: email.trim(),
      password: await hashPassword(password),
      createdAt: Date.now(),
    };
    await this.storage.set(USERS_KEY, [...users, user]);
    return user;
  }

  async login(email: string, password: string): Promise<User | null> {
    const users = await this.listUsers();
    const norm = email.trim().toLowerCase();
    const user = users.find((u) => u.email.toLowerCase() === norm);
    if (!user) return null;
    return (await verifyPassword(password, user.password)) ? user : null;
  }
}
