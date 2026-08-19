const path = require("path");
const { defineConfig, devices } = require("@playwright/test");

require("dotenv").config({ path: path.join(__dirname, ".env") });

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1";
const autoStartServer = (process.env.E2E_AUTO_START_SERVER || "true").toLowerCase() !== "false";
const slowMoMs = Number(process.env.E2E_SLOW_MO_MS || 0);
const screenshotMode = process.env.E2E_SCREENSHOT_MODE || "on";
const launchOptions = Number.isFinite(slowMoMs) && slowMoMs > 0
  ? { slowMo: Math.floor(slowMoMs) }
  : undefined;

module.exports = defineConfig({
  testDir: "./tests",
  timeout: 60 * 1000,
  expect: {
    timeout: 15 * 1000
  },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  webServer: autoStartServer
    ? {
        command: "node ./scripts/static-server.js",
        cwd: path.resolve(__dirname),
        url: baseURL,
        reuseExistingServer: true,
        timeout: 30 * 1000
      }
    : undefined,
  reporter: [
    ["list"],
    ["html", { open: "never" }],
    [
      "./reporters/self-test-report-reporter.js",
      {
        outputDir: "self-test-reports",
        reportTopic: "Web UI自动化自测"
      }
    ]
  ],
  use: {
    baseURL,
    ignoreHTTPSErrors: true,
    launchOptions,
    trace: "on-first-retry",
    screenshot: screenshotMode,
    video: "on",
    viewport: { width: 1440, height: 900 }
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
