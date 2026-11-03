export function createConfirmToken(): string {
  return crypto.randomUUID();
}
