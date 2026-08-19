const fs = require("fs");
const path = require("path");

function readArg(name, fallback) {
  const idx = process.argv.indexOf(name);
  return idx > -1 && process.argv[idx + 1] ? process.argv[idx + 1] : fallback;
}

function splitList(text) {
  return String(text || "")
    .split(/[;,，、]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function slugify(text) {
  const cleaned = String(text || "")
    .normalize("NFKC")
    .replace(/[\\/:*?"<>|]/g, "")
    .trim()
    .replace(/\s+/g, "-");
  return cleaned || `case-${Date.now()}`;
}

function pickValue(line) {
  const m = String(line || "").match(/[:：]\s*(.*)\s*$/);
  return m ? m[1] : "";
}

function parseSpec(content) {
  const lines = String(content || "").split(/\r?\n/);
  const result = { types: [], url: "/", details: {} };

  for (const line of lines) {
    if (/^\s*-\s*测试类型/.test(line)) {
      result.types = splitList(pickValue(line));
      continue;
    }
    if (/^\s*-\s*测试网址/.test(line)) {
      result.url = pickValue(line) || "/";
      continue;
    }
    const detail = line.match(/^\s*-\s*([^\s：:]+测试)\s*[：:]\s*(.*)\s*$/);
    if (detail) {
      result.details[detail[1]] = detail[2];
    }
  }

  return result;
}

function hasType(types, keyword) {
  return types.some((t) => t.includes(keyword));
}

function makeTestBlocks(spec) {
  const blocks = [];

  if (hasType(spec.types, "功能")) {
    blocks.push(`  test("功能测试", async ({ page }) => {
    await page.goto(DEMO_PATH, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
    // 输入内容: ${spec.details["功能测试"] || "TODO"}
    // TODO: 补充按钮、输入、API断言
  });`);
  }

  if (hasType(spec.types, "兼容")) {
    blocks.push(`  test("兼容性测试", async ({ page, browserName }) => {
    await page.goto(DEMO_PATH, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
    // 输入内容: ${spec.details["兼容性测试"] || "TODO"}
    await expect(browserName).toBeTruthy();
  });`);
  }

  if (hasType(spec.types, "布局")) {
    blocks.push(`  test("布局测试", async ({ page }) => {
    await page.goto(DEMO_PATH, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
    // 输入内容: ${spec.details["布局测试"] || "TODO"}
    // TODO: 补充布局/颜色/字体断言
  });`);
  }

  if (hasType(spec.types, "节点")) {
    blocks.push(`  test("节点回读测试", async ({ page }) => {
    await page.goto(DEMO_PATH, { waitUntil: "domcontentloaded" });
    // 输入内容: ${spec.details["节点回读测试"] || "TODO"}
    // TODO: 写节点回读断言，例如 locator(...).toBeAttached()
  });`);
  }

  if (!blocks.length) {
    blocks.push(`  test("通用测试", async ({ page }) => {
    await page.goto(DEMO_PATH, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
  });`);
  }

  return blocks.join("\n\n");
}

function buildContent(spec, caseName) {
  return `const { test, expect } = require("@playwright/test");

const DEMO_PATH = process.env.E2E_DEMO_PATH || ${JSON.stringify(spec.url || "/")};

// 自动生成骨架：补齐断言后移除 .skip
test.describe.skip(${JSON.stringify(`${caseName} - 自动生成`)}, () => {
${makeTestBlocks(spec)}
});
`;
}

function main() {
  const input = readArg("--input", "TEST_CASE_SPEC.md");
  const outputDir = readArg("--outputDir", "tests/generated");
  const caseName = readArg("--name", "quick-case");

  const cwd = process.cwd();
  const inputPath = path.resolve(cwd, input);
  if (!fs.existsSync(inputPath)) {
    throw new Error(`Spec file not found: ${inputPath}`);
  }

  const spec = parseSpec(fs.readFileSync(inputPath, "utf8"));
  const fileName = `${slugify(caseName)}.spec.js`;
  const outDir = path.resolve(cwd, outputDir);
  const outPath = path.join(outDir, fileName);

  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(outPath, buildContent(spec, caseName), "utf8");
  process.stdout.write(`[test-generate] created: ${path.relative(cwd, outPath)}\n`);
}

main();
