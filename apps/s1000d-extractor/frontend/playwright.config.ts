import { defineConfig, devices } from "@playwright/test";

const e2ePort = Number(process.env.E2E_PORT ?? 5173);

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  retries: 0,
  use: {
    channel: process.env.E2E_BROWSER_CHANNEL,
    baseURL: `http://127.0.0.1:${e2ePort}`,
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "node scripts/e2e-dev.mjs",
    url: `http://127.0.0.1:${e2ePort}`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
