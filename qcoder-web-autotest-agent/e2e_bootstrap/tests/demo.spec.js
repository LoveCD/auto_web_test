const { test, expect } = require("@playwright/test");

const DEMO_PATH = process.env.E2E_DEMO_PATH || "/";
const READY_SELECTOR = (process.env.E2E_DEMO_READY_SELECTOR || "").trim();

// Demo flow: verify target page is reachable and basic content is rendered.
test("demo page smoke: should open target page and render content", async ({ page }) => {
  const response = await page.goto(DEMO_PATH, { waitUntil: "domcontentloaded" });

  expect(response).not.toBeNull();
  if (response) {
    expect(response.status()).toBeLessThan(400);
  }

  if (READY_SELECTOR) {
    await expect(page.locator(READY_SELECTOR).first()).toBeVisible();
  } else {
    await expect(page.locator("body")).toBeVisible();
  }
});
