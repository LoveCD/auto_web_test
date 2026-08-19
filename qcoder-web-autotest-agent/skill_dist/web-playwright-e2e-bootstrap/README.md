# Web Playwright E2E Bootstrap

Playwright E2E 快速引导技能：为 Web 工程初始化可运行 E2E 基线，提供
**三字段极简输入 → 用例骨架生成 → HTML/DOCX 自测报告（截图嵌入）** 的固化流程，
并可选支持串口节点回读。

本包为 **QCoder SkillHub 兼容格式**（SKILL.md + README.md + _meta.json + references + scripts）。

## 核心能力

| 能力 | 说明 |
|---|---|
| 用例骨架生成 | `TEST_CASE_SPEC.md` 只填 3 个字段（测试类型/测试网址/测试内容），`npm run test:generate` 生成 `tests/generated/*.spec.js`（默认 `describe.skip` 安全增量补全） |
| DOCX 报告 | 基于 `templates/test-report-template.docx` 占位符填充；每个用例备注列自动嵌入执行截图；按 `case-plan.js` 定义业务顺序 |
| HTML 报告 | Playwright 原生 HTML 报告 |
| 节点回读 | 串口读设备节点原始值，与页面显示值比对（可选） |

## 使用

已在 `qcoder-web-autotest-agent` 工程集成，模板资产位于工程 `e2e_bootstrap/`：

```powershell
cd e2e_bootstrap
copy .env.example .env
npm install
npx playwright install chromium
npm run test:generate -- --input ./TEST_CASE_SPEC.md --name 新人快速上手
npm test
```

产物：`playwright-report/index.html`、`self-test-reports/测试报告-*.docx`、`self-test-reports/*.md`。

对新工程引导（注入模板）：运行本包 `scripts/bootstrap-web-e2e.ps1 -ProjectPath <目标工程> -InstallBrowser`。

## 详细文档

- 集成形态使用说明：工程根 `e2e_bootstrap/README.md`
- 执行序列：`references/workflow.md`
- 报告模板占位符契约：`references/report-template-placeholders.md`
- 完整技能说明：`SKILL.md`
