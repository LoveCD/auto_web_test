# qcoder-web-autotest-agent · e2e_bootstrap

本目录是集成自 **web-playwright-e2e-bootstrap** 技能的 Node.js Playwright E2E 基线，
与工程主链路（Python + Playwright，见工程根 README）互补：

- 主链路（Python）：运营商 Profile 驱动的真机/Mock 用例执行、NL 用例生成、全菜单遍历截图
- 本基线（Node）：快速引导新项目 E2E（三字段输入 → 用例骨架）、HTML/DOCX 自测报告
  （截图自动嵌入每个用例备注）、可选串口节点回读

核心资产（来自技能 `assets/e2e-template/`）：

| 资产 | 说明 |
|---|---|
| `templates/test-report-template.docx` | DOCX 报告模板（占位符 `{{...}}` 填充，`{{测试用例2名称}}` 块克隆生成测试项 3+） |
| `reporters/self-test-report-reporter.js` | Playwright reporter：按 case-plan 排序、嵌入截图（`[[E2E_CASE_SCREEN_n]]` → 真实图片） |
| `scripts/generate-case-from-spec.js` | 三字段极简输入（测试类型/测试网址/测试内容）→ 生成 `tests/generated/*.spec.js` 骨架 |
| `scripts/gen-case-doc.js` | 用例文档/执行报告生成：单套件设计文档、`--all` 批量、`--result` 执行报告（与执行报告同一 DOCX 模板，自动填充结果/结论并嵌入截图） |
| `scripts/static-server.js` | 本地静态服务器（无真实页面也可自测） |
| `tests/case-plan.js` | 结构化测试计划（决定报告用例顺序） |
| `TEST_CASE_SPEC.md` | 新人极简输入模板 |

## 快速开始

```bash
cd e2e_bootstrap
cp .env.example .env        # 按需修改 E2E_BASE_URL / E2E_DEMO_PATH
npm install
npx playwright install chromium
npm test -- --list          # 仅列出用例
npm test                    # 执行并生成报告
```

产物：

- HTML 报告：`playwright-report/index.html`
- DOCX 报告：`self-test-reports/测试报告-*.docx`（每个用例备注列内嵌截图）
- Markdown 摘要：`self-test-reports/*.md`

## 三字段输入生成用例

编辑 `TEST_CASE_SPEC.md`，只填 3 个字段：

```markdown
- 测试类型：功能测试,兼容性测试,布局测试,节点回读测试
- 测试网址：/
- 测试内容：
  - 功能测试：页面展示正常；保存按钮可点击
  ...
```

生成骨架（默认 `describe.skip`，补齐断言后移除 `.skip`）：

```bash
npm run test:generate -- --input ./TEST_CASE_SPEC.md --name 新人快速上手
```

输出：`tests/generated/新人快速上手.spec.js`

## 结构化测试计划（可选）

编辑 `tests/case-plan.js`，字段：`testCase`（测试用例）/ `testType`（测试类型）/
`testPage`（测试页面）/ `testContent`（测试内容，填充到报告"测试目的"）/ `multiTerminal`（多端测试）。
报告排序跟随 case-plan 而非文件顺序。

## 用例文档 / 执行报告生成（推荐）

所有用例文档与测试报告统一按 e2e-bootstrap 模板生成（同一 DOCX 模板、同一版式）。
将 qcoder-web-autotest 套件 JSON（`../operators/*/cases/*.json`）转换为 Word 文档，
三种模式：

**① 单套件设计文档**（结果/结论列填"待执行"）：

```bash
node scripts/gen-case-doc.js <suite.json> [--topic 主题] [--project-code 代号] [--out 目录]
# 示例：生成 CM 登录界面验证用例文档
node scripts/gen-case-doc.js ../operators/cm/cases/login.json \
  --topic "CM登录界面验证用例" --project-code CM-REAL-LOGIN --out ../reports
```

**② 批量设计文档**（扫描 operators 下各运营商 cases 目录全部套件，排除 generated/）：

```bash
node scripts/gen-case-doc.js --all --out ../reports
```

**③ 执行报告**（读取 `run_suite.py` 输出的 `result.json`，自动匹配套件 JSON 合并渲染；
结果/结论/失败原因自动填充，截图嵌入各用例备注，汇总区自动统计）：

```bash
node scripts/gen-case-doc.js --result <result.json> --out ../reports
# 示例：为最近一次真机执行生成测试报告
node scripts/gen-case-doc.js --result ../reports/20260819_100314_519990_cm_real_regression/result.json \
  --out ../reports
```

输出：`<out>/用例文档-<主题>-<时间戳>.docx` 或 `<out>/测试报告-<主题>-<时间戳>.docx`
（每条用例一页测试项表格：测试类型/目的/预置条件/测试浏览器/环境/步骤/期望/结果/结论/备注）。

支持 `--template`（自定义模板路径）、`--base-url`（目标地址）、`--preconditions`（预置条件，分号分隔）、
`--qcoder-root`（工程根目录，默认自动定位）、`--operator`/`--suite`（报告模式指定匹配套件）。

## 业务示例

原模板附带的漫游设置业务示例（`roaming-settings.spec.js`）与本工程无关，
已移出 testDir 至 `tests_examples/roaming-settings.spec.example.js` 作为参考，
不会参与测试运行。新增自己的用例请直接在 `tests/` 下编写。

## 维护说明

本目录的模板基础设施（playwright.config.js、reporter、脚本、模板 docx）来源于
`web-playwright-e2e-bootstrap` 技能。技能升级后可按其 Update Policy 同步：
仅同步模板托管的基础设施文件，不动业务用例。

## 可选：串口节点回读

```bash
npm run serial:node-readback
```

在 `.env` 中配置 `E2E_SERIAL_PORT` / `E2E_SERIAL_BAUD` / 各层账号 / 读取与回读命令等。
回读工作流：先读页面可见值 → 串口读设备节点原始值 → 在测试代码中套用页面格式化逻辑
比较 → 报告附原始 JSON、对比 txt 与叠加截图。
