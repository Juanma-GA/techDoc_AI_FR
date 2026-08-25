// Password hashing with PBKDF2 (Web Crypto, available in browser and Node 20+).
// Pure logic, no UI/OS deps. Never stores plaintext passwords.

const ITERATIONS = 120_000;

function toHex(buf: ArrayBuffer | Uint8Array): string {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}
function fromHex(hex: string): Uint8Array {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export interface PasswordHash {
  saltHex: string;
  hashHex: string;
}

async function derive(password: string, salt: Uint8Array): Promise<string> {
  const enc = new TextEncoder().encode(password);
  const key = await crypto.subtle.importKey("raw", enc, "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt: salt as unknown as BufferSource, iterations: ITERATIONS, hash: "SHA-256" },
    key,
    256
  );
  return toHex(bits);
}

export async function hashPassword(password: string): Promise<PasswordHash> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return { saltHex: toHex(salt), hashHex: await derive(password, salt) };
}

export async function verifyPassword(password: string, stored: PasswordHash): Promise<boolean> {
  const hashHex = await derive(password, fromHex(stored.saltHex));
  // constant-time-ish comparison
  if (hashHex.length !== stored.hashHex.length) return false;
  let diff = 0;
  for (let i = 0; i < hashHex.length; i++) diff |= hashHex.charCodeAt(i) ^ stored.hashHex.charCodeAt(i);
  return diff === 0;
}
