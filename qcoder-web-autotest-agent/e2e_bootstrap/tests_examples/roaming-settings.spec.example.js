const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");
const { test, expect } = require("@playwright/test");
const casePlan = require("./case-plan");

const PAGE_URL = pathToFileURL(path.resolve(__dirname, "..", "..", "roaming-settings.html")).href;
const STEP_DELAY_MS = 120;
const TYPE_DELAY_MS = 50;

const SELECTORS = {
  openEnableOn: 'input[name="X_FH_Capwap.APGroup.2P4GOpenRoamingThresholdEnable"][value="1"]',
  openEnableOff: 'input[name="X_FH_Capwap.APGroup.2P4GOpenRoamingThresholdEnable"][value="0"]',
  forceEnableOn: 'input[name="X_FH_Capwap.APGroup.2P4GForceOfflineThresholdEnable"][value="1"]',
  forceEnableOff: 'input[name="X_FH_Capwap.APGroup.2P4GForceOfflineThresholdEnable"][value="0"]',
  openRows: "#openThresholdRows",
  forceRows: "#forceThresholdRows",
  saveButton: 'button[type="submit"]'
};

const BASELINE = {
  open24: "-60",
  open5g: "-60",
  force24: "-65",
  force5g: "-65"
};

function getCaseByName(caseName) {
  const found = casePlan.find((one) => one.testCase === caseName);
  if (!found) {
    throw new Error(`case-plan.js missing case: ${caseName}`);
  }
  return found;
}

const toggleCase = getCaseByName("切换启动和禁用测试");
const inputCase = getCaseByName("参数输入测试");

test.describe.configure({ timeout: 120000 });
test.use({ launchOptions: { slowMo: 40 } });

async function pause(page, ms = STEP_DELAY_MS) {
  await page.waitForTimeout(ms);
}

async function openCleanPage(page) {
  await page.goto(PAGE_URL, { waitUntil: "domcontentloaded" });
  await pause(page);
  await page.evaluate(() => localStorage.removeItem("roamingSettingsPayload"));
  await page.reload({ waitUntil: "domcontentloaded" });
  await pause(page);
}

async function slowCheck(page, selector) {
  await page.check(selector);
  await pause(page);
}

async function slowFill(page, selector, value) {
  await page.fill(selector, value);
  await pause(page);
}

async function slowClick(page, selector) {
  await page.click(selector);
  await pause(page);
}

async function setAllBaseline(page) {
  await slowFill(page, "#open24", BASELINE.open24);
  await slowFill(page, "#open5g", BASELINE.open5g);
  await slowFill(page, "#force24", BASELINE.force24);
  await slowFill(page, "#force5g", BASELINE.force5g);
}

async function ensureAllEnabled(page) {
  await slowCheck(page, SELECTORS.openEnableOn);
  await slowCheck(page, SELECTORS.forceEnableOn);
  await expect(page.locator(SELECTORS.openRows)).toBeVisible();
  await expect(page.locator(SELECTORS.forceRows)).toBeVisible();
  await pause(page);
}

async function typeInvalidText(page, selector, value) {
  await page.fill(selector, "");
  await pause(page, 80);
  await page.click(selector);
  await pause(page, 60);
  await page.keyboard.type(value, { delay: TYPE_DELAY_MS });
  await pause(page, 100);
}

async function assertError(page, selector, expectedMode) {
  if (expectedMode === "range") {
    await expect(page.locator(selector)).toContainText("范围");
    return;
  }
  await expect(page.locator(selector)).toContainText("必须是整数");
}

test(toggleCase.testCase, async ({ page }) => {
  await openCleanPage(page);

  await expect(page.locator(SELECTORS.openRows)).toBeVisible();
  await expect(page.locator(SELECTORS.forceRows)).toBeVisible();
  await pause(page);

  await slowCheck(page, SELECTORS.openEnableOff);
  await expect(page.locator(SELECTORS.openRows)).toBeHidden();
  await pause(page);

  await slowCheck(page, SELECTORS.openEnableOn);
  await expect(page.locator(SELECTORS.openRows)).toBeVisible();
  await pause(page);

  await slowCheck(page, SELECTORS.forceEnableOff);
  await expect(page.locator(SELECTORS.forceRows)).toBeHidden();
  await pause(page);

  await slowCheck(page, SELECTORS.forceEnableOn);
  await expect(page.locator(SELECTORS.forceRows)).toBeVisible();
  await pause(page);
});

test(inputCase.testCase, async ({ page, browserName }) => {
  test.skip(
    !inputCase.multiTerminal && browserName !== "chromium",
    "该测试用例配置为多端测试=否，仅在 Chromium 执行"
  );

  await openCleanPage(page);
  await ensureAllEnabled(page);

  const fieldMatrix = [
    {
      input: "#open24",
      error: "#open24Error",
      invalid: [
        { value: "-96", mode: "range" },
        { value: "-39", mode: "range" },
        { value: "-60.5", mode: "nonRange" },
        { value: "abc", mode: "nonRange", typeMode: true },
        { value: "@", mode: "nonRange", typeMode: true },
        { value: "", mode: "nonRange" }
      ],
      valid: ["-95", "-40"]
    },
    {
      input: "#open5g",
      error: "#open5gError",
      invalid: [
        { value: "-96", mode: "range" },
        { value: "-39", mode: "range" },
        { value: "-60.25", mode: "nonRange" },
        { value: "abc", mode: "nonRange", typeMode: true },
        { value: "#", mode: "nonRange", typeMode: true },
        { value: "", mode: "nonRange" }
      ],
      valid: ["-95", "-40"]
    },
    {
      input: "#force24",
      error: "#force24Error",
      invalid: [
        { value: "-101", mode: "range" },
        { value: "-44", mode: "range" },
        { value: "-65.5", mode: "nonRange" },
        { value: "abc", mode: "nonRange", typeMode: true },
        { value: "$", mode: "nonRange", typeMode: true },
        { value: "", mode: "nonRange" }
      ],
      valid: ["-100", "-45"]
    },
    {
      input: "#force5g",
      error: "#force5gError",
      invalid: [
        { value: "-101", mode: "range" },
        { value: "-44", mode: "range" },
        { value: "-70.2", mode: "nonRange" },
        { value: "abc", mode: "nonRange", typeMode: true },
        { value: "%", mode: "nonRange", typeMode: true },
        { value: "", mode: "nonRange" }
      ],
      valid: ["-100", "-45"]
    }
  ];

  const executedInvalids = [];
  const expectedInvalidCount = fieldMatrix.reduce((sum, one) => sum + one.invalid.length, 0);

  for (const field of fieldMatrix) {
    await setAllBaseline(page);

    for (const bad of field.invalid) {
      executedInvalids.push(`${field.input}=${bad.value === "" ? "<empty>" : bad.value}`);
      if (bad.typeMode) {
        await typeInvalidText(page, field.input, bad.value);
      } else {
        await slowFill(page, field.input, bad.value);
      }
      await slowClick(page, SELECTORS.saveButton);
      await assertError(page, field.error, bad.mode);
      await pause(page, 80);
    }

    for (const good of field.valid) {
      await slowFill(page, field.input, good);
      await slowClick(page, SELECTORS.saveButton);
      await expect(page.locator(field.error)).toHaveText("");
      await expect.poll(async () => {
        const raw = await page.evaluate(() => localStorage.getItem("roamingSettingsPayload"));
        return raw ? raw.length : 0;
      }).toBeGreaterThan(0);
      await pause(page, 80);
    }
  }

  expect(executedInvalids.length).toBe(expectedInvalidCount);
  expect(executedInvalids.some((item) => item.includes(".5") || item.includes(".25") || item.includes(".2"))).toBeTruthy();
  expect(executedInvalids.some((item) => item.includes("abc"))).toBeTruthy();
  expect(executedInvalids.some((item) => item.includes("@") || item.includes("#") || item.includes("$") || item.includes("%"))).toBeTruthy();
  expect(executedInvalids.some((item) => item.includes("<empty>"))).toBeTruthy();

  const coverageText = [
    `测试用例: ${inputCase.testCase}`,
    "错误参数覆盖清单:",
    ...executedInvalids.map((item, idx) => `${idx + 1}. ${item}`)
  ].join("\n");
  const coveragePath = test.info().outputPath("invalid-coverage.txt");
  fs.writeFileSync(coveragePath, coverageText, "utf8");
  await test.info().attach("invalid-coverage", {
    path: coveragePath,
    contentType: "text/plain"
  });
});
