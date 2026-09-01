import { defineConfig } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const skipWebServer = process.env.PLAYWRIGHT_SKIP_WEBSERVER === "true";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  webServer: skipWebServer ? undefined : {
    command: "npm run dev -- --host 127.0.0.1",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "mobile-375",
      use: { browserName: "chromium", isMobile: true, viewport: { width: 375, height: 812 } },
    },
    {
      name: "mobile-390",
      use: { browserName: "chromium", isMobile: true, viewport: { width: 390, height: 844 } },
    },
    {
      name: "mobile-430",
      use: { browserName: "chromium", isMobile: true, viewport: { width: 430, height: 932 } },
    },
  ],
});
