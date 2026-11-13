import { defineConfig, devices } from "@playwright/test";

/**
 * Config Playwright pour le front web Revizio.
 * Lance le serveur Vite (port 5173) et teste les parcours critiques.
 * Les appels API sont mockés via page.route (pas besoin de backend).
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // VITE_API_URL absolu pour que les mocks page.route (http://localhost:8000)
    // correspondent aux appels de l'app (sinon API_BASE="" -> URLs relatives).
    command: "VITE_API_URL=http://localhost:8000 pnpm dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
