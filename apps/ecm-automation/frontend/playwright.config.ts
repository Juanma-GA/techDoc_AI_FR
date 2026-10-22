import { defineConfig, devices } from "@playwright/test";

const baseURL = `http://127.0.0.1:${process.env.ECM_AUTOMATION_E2E_PORT ?? "5173"}`;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "pnpm dev",
    url: baseURL,
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
