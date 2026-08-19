---
name: web-playwright-e2e-bootstrap
description: Initialize Playwright E2E automation for a web project with a reusable e2e template, environment bootstrap, self-check execution, HTML report, and DOCX self-test report (screenshots embedded in each test item's remarks). Includes a solidified 3-field test input format and optional serial node-readback support.
---

# Web Playwright E2E Bootstrap

Use this skill to create a runnable Playwright E2E baseline in a web project.

## Trigger

Use this skill when the user asks to:

- initialize/bootstrap Playwright E2E
- create a fresh `e2e/` structure
- generate HTML + DOCX self-test reports
- standardize case-input format for quick onboarding

## Flow

1. Validate runtime prerequisites (`node`, `npm`).
2. Create target `e2e/` and inject template files (only under `e2e/`).
3. Auto-fill missing `.env` keys from the skill template `.env.example` source, not from a possibly stale local copy.
4. Verify required template files:
   - `playwright.config.js`
   - `scripts/static-server.js`
   - `reporters/self-test-report-reporter.js`
   - `templates/test-report-template.docx`
   - `tests/demo.spec.js`
5. Verify solidified onboarding format files:
   - `TEST_CASE_SPEC.md`
   - `scripts/generate-case-from-spec.js`
6. Verify optional serial-readback files:
   - `scripts/serial-node-readback.ps1`
7. Install dependencies and validate:
   - `@playwright/test`
   - `jszip`
   - `dotenv`
8. Run self-check:
   - `npm test -- --list`
   - `npm test`
9. Verify report outputs:
   - HTML: `e2e/playwright-report/index.html`
   - DOCX: `e2e/self-test-reports/*.docx`
10. Confirm DOCX behavior:
    - screenshots are embedded as images in each test item's remarks.

## Update Policy For Existing e2e Directories

When rerunning this skill against an existing `e2e/` folder, treat the following as template-managed critical files and sync them to the latest template version even without `-Force`:

- `.env.example`
- `README.md`
- `package.json`
- `playwright.config.js`
- `TEST_CASE_SPEC.md`
- `reporters/self-test-report-reporter.js`
- `scripts/generate-case-from-spec.js`
- `scripts/serial-node-readback.ps1`
- `scripts/static-server.js`
- `templates/test-report-template.docx`

Why this matters:

- stale `playwright.config.js` can lock `screenshot` to `only-on-failure`, so passed cases produce no screenshot attachments
- stale `reporters/self-test-report-reporter.js` can drop structured case-plan fields and screenshot embedding logic
- stale local `.env.example` can prevent new report-related keys from being appended into `.env`

Preserve user-authored business test files by default; only sync template-managed infrastructure automatically.

## Solidified Input Format

This skill standardizes onboarding input via:

- `e2e/TEST_CASE_SPEC.md`

Only 3 fields are required:

1. `测试类型`
2. `测试网址`
3. `测试内容`

Generate skeleton tests:

```powershell
npm run test:generate -- --input ./TEST_CASE_SPEC.md --name 新人快速上手
```

Generated output:

- `e2e/tests/generated/*.spec.js`

Skeletons are `describe.skip` by default for safe incremental completion.

## Optional Serial Node Readback

Run with `.env`:

```powershell
npm run serial:node-readback
```

Key `.env` fields:

- `E2E_SERIAL_PORT`, `E2E_SERIAL_BAUD`
- `E2E_SERIAL_LEVEL1_USER`, `E2E_SERIAL_LEVEL1_PASS`
- `E2E_SERIAL_LEVEL2_USER`, `E2E_SERIAL_LEVEL2_PASS`
- `E2E_SERIAL_ENTER_CMD_1`, `E2E_SERIAL_ENTER_CMD_2`
- `E2E_SERIAL_NODE_READ_CMD`, `E2E_SERIAL_NODE_READBACK_CMD`

## Node Readback Workflow

For pages that display values derived from device nodes, prefer this workflow:

1. Read the page source and identify:
   - raw node paths requested by the page
   - fields that are direct node echoes
   - fields that are transformed in the UI (status mapping, uptime formatting, percent calculation, DNS splitting, routed/bridged localization)
2. In E2E, read the page-visible values first.
3. Use serial shell readback to fetch the corresponding node values.
4. Reapply the page's own formatting/mapping logic in test code before comparing with UI text.
5. Attach three artifacts for report readability:
   - raw serial JSON or text
   - human-readable comparison `.txt`
   - overlay screenshot showing `field / node / UI value / expected value / match result`

This keeps node validation explainable in the report and visible in the execution video.

## Case Plan Ordering

DOCX/Markdown report ordering must follow `e2e/tests/case-plan.js`, not file name order or runtime execution order.

Use this when a project needs a business-defined order such as:

- login cases first
- menu browsing cases next
- page node confirmation cases after browsing

If a case exists in `case-plan.js`, its report position should follow that plan.

## Execute

本技能已在 `qcoder-web-autotest-agent` 工程内集成：模板资产位于工程 `e2e_bootstrap/`
（项目根下），无需再执行 bootstrap 脚本。直接使用：

```powershell
# 1. 首次初始化（在工程根）
cd e2e_bootstrap
copy .env.example .env      # 或 cp .env.example .env
npm install
npx playwright install chromium

# 2. 三字段输入生成用例骨架（tests/generated/*.spec.js）
npm run test:generate -- --input ./TEST_CASE_SPEC.md --name 新人快速上手

# 3. 执行并生成 HTML + DOCX 报告（截图嵌入用例备注）
npm test

# 4. 用例文档 / 执行报告（同一模板）：
#    ① 单套件设计文档（结果/结论=待执行）
node scripts/gen-case-doc.js ../operators/cm/cases/login.json --topic "CM登录界面验证用例" --out ../reports
#    ② 批量设计文档（operators 下全部套件，排除 generated/）
node scripts/gen-case-doc.js --all --out ../reports
#    ③ 执行报告（读取 run_suite.py 的 result.json，自动填充结果/结论并嵌入截图）
node scripts/gen-case-doc.js --result ../reports/<run_id>/result.json --out ../reports
```

对**其他新工程**引导时，若需重新注入模板，可使用本技能自带脚本（脚本位于本技能目录
`scripts/bootstrap-web-e2e.ps1`，从技能根定位）：

```powershell
powershell -ExecutionPolicy Bypass -File <本技能目录>\scripts\bootstrap-web-e2e.ps1 -ProjectPath <目标工程> -InstallBrowser
```

Overwrite template-managed files when required:

```powershell
powershell -ExecutionPolicy Bypass -File <本技能目录>\scripts\bootstrap-web-e2e.ps1 -ProjectPath <目标工程> -Force
```

## Rules

1. In this project, template files live under `e2e_bootstrap/`; do not create a separate `e2e/`.
2. Keep baseline test minimal (`tests/demo.spec.js`) for new projects.
3. Keep DOCX template placeholders unchanged unless reporter logic is updated together.
4. Do not write files outside project root (except generated test reports).
5. 用例设计文档一律用 `scripts/gen-case-doc.js` 生成（复用同一 DOCX 模板），不要另写文档格式。
6. `reporters/self-test-report-reporter.js` 末尾附带的工具函数导出（`renderTemplateDocx` 等）供 gen-case-doc 复用；修改渲染逻辑时两者需同步验证（`npm test` 回归）。

## References

- Read [workflow.md](references/workflow.md) for execution sequence.
- Read [report-template-placeholders.md](references/report-template-placeholders.md) before changing DOCX/report logic.
- Integrated template usage: `e2e_bootstrap/README.md`（工程根）。
