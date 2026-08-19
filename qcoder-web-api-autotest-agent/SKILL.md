---
name: qcoder-web-autotest-agent
model: standard
category: testing
description: >-
  面向宽带终端国际基线版本的 Web 自动化测试智能体。覆盖 Web API 接口测试和 Web UI 页面测试，
  支持用例生成、回归执行、失败归因、覆盖矩阵和变更影响分析。基于 Playwright + pytest + YAML 用例库，
  通过 Page Object 和 Selector Profile 隔离设备差异，固化测试资产为可重复执行的 AI 工作流。
  通过 MCP Server 提供 6 个结构化工具供 Qoder AI 直接调用。
version: 2.0.0
keywords:
  - web testing
  - playwright
  - automation
  - regression
  - smoke test
  - page object
  - yaml cases
  - failure analysis
  - coverage matrix
  - gateway
  - mcp
---

# QCoder Web Autotest Agent

> 面向宽带终端国际基线版本的 Web 测试智能体 —— 把测试设计、用例维护、自动执行、失败分析和报告输出固化成可重复流程。

## WHAT This Skill Does

这是一个完整的 Web 自动化测试智能体，通过 **MCP Server + Skill + Skillset** 三层集成与 Qoder 交互：

- **MCP 工具层**：6 个结构化工具，Qoder AI 直接调用，参数有 schema 约束
- **Skill 知识层**：本 SKILL.md，告诉 AI 什么时候用哪个工具、怎么分析结果
- **执行后端**：agent_cli.py + Playwright + Page Object，被 MCP Server 调用

## WHEN To Use

- **执行版本回归**：用户说"跑一下 Web 回归"或"执行 smoke 测试"
- **生成测试用例**：用户给出需求描述，需要生成 YAML/JSON 用例
- **分析失败原因**：用户说"看看为什么失败了"或"分析最新报告"
- **变更影响分析**：用户给出版本修改点，需要知道哪些用例受影响
- **覆盖矩阵审查**：用户说"看看测试覆盖情况"或"哪些功能没覆盖到"
- **读取报告**：用户说"看看上次测试结果"

---

## MCP Tools — AI 直接调用的结构化工具

本 Skill 通过 MCP Server (`mcps/web-autotest/server.py`) 提供 6 个工具。
**优先使用 MCP 工具，不要用 Bash 调 CLI。**

### 工具 1：`run_test_suite` — 执行测试

```
参数:
  suite_type: "smoke" | "regression"    (必填)
  test_layer: "web" | "api"             (必填)
  profile: string                        (可选, 默认 intl_baseline_web 或 intl_baseline)
  start_mock: boolean                    (可选, 默认 true)

返回:
  {
    "status": "pass" | "fail",
    "summary": { "total": 3, "passed": 3, "failed": 0, "duration": 1.79 },
    "report_path": "reports/20260818_145418_web_smoke"
  }
```

AI 行为：调用后向用户展示通过/失败数和耗时。如果有失败，自动调用 `analyze_failure`。

### 工具 2：`get_test_report` — 读取报告

```
参数:
  run_id: string     (可选, 默认最新)
  format: "md" | "json"  (可选, 默认 md)

返回:
  { "status": "ok", "run_id": "...", "content": "# Web UI AutoTest Report..." }
```

AI 行为：读取后向用户展示报告摘要，包括每条用例的通过/失败状态和失败原因。

### 工具 3：`analyze_failure` — 失败分析

```
参数:
  run_id: string          (可选, 默认最新)
  test_layer: "web" | "api"  (可选, 默认 web)

返回:
  { "status": "ok", "analysis": "失败分类、证据、修复建议..." }
```

AI 行为：读取分析结果后，按失败分类给出修复建议：
- `selector_changed` → 建议更新 selector profile
- `page_load_timeout` → 建议检查网络/服务状态
- `product_bug` → 建议提交 bug 工单
- `script_bug` → 建议修正测试脚本

### 工具 4：`get_coverage_matrix` — 覆盖矩阵

```
参数:
  scope_file: string  (可选, 默认 requirements/intl_baseline_web_scope.md)

返回:
  { "status": "ok", "matrix": "| Module | Total | API | Web |..." }
```

AI 行为：展示覆盖矩阵表格，指出未覆盖的缺口，建议补测方向。

### 工具 5：`generate_test_cases` — 生成用例

```
参数:
  module: "Login" | "Status" | "WiFi" | "WAN" | "System"  (必填)
  test_layer: "web" | "api"                                (必填)
  requirement_file: string                                 (可选)

返回:
  { "status": "ok", "module": "WiFi", "output": "YAML 用例内容..." }
```

AI 行为：生成后展示用例预览，提示用户审核后入库到 `cases/` 目录。

### 工具 6：`update_cases_by_change` — 变更影响分析

```
参数:
  change_file: string  (必填, 如 "changes/v1.0.1_wifi_change.md")

返回:
  { "status": "ok", "analysis": "受影响用例、建议更新、推荐回归集..." }
```

AI 行为：展示受影响用例列表，建议新增/更新的用例，推荐执行的回归集。

---

## Architecture (三层集成)

```text
┌──────────────────────────────────────────────────────────────────┐
│  Qoder AI Agent (内置, 不可替换)                                   │
│                                                                    │
│  ① 读取 SKILL.md → 知道有哪些工具、什么时候用                       │
│  ② 调用 MCP 工具 → 直接执行，获得结构化结果                         │
│  ③ 读取 workflow .md → 获取详细分析逻辑                             │
├──────────────────────────────────────────────────────────────────┤
│  MCP Server 层 (mcps/web-autotest/server.py)                      │
│                                                                    │
│  6 个结构化工具:                                                    │
│  ├─ run_test_suite(suite, layer) → 执行测试, 返回 JSON 结果         │
│  ├─ get_test_report(run_id) → 读取报告, 返回 Markdown/JSON         │
│  ├─ analyze_failure(run_id) → 失败分析, 返回分类+建议              │
│  ├─ get_coverage_matrix() → 覆盖矩阵, 返回表格+缺口                │
│  ├─ generate_test_cases(module) → 生成用例, 返回 YAML              │
│  └─ update_cases_by_change(file) → 影响分析, 返回受影响列表        │
├──────────────────────────────────────────────────────────────────┤
│  CLI 后端层 (agent_cli.py)                                         │
│  被 MCP Server 调用, 也可独立运行:                                  │
│  run-web-suite / generate-web-cases / analyze-web-failure          │
│  run-suite / generate-cases / analyze-failure / coverage-review    │
├──────────────────────────────────────────────────────────────────┤
│  执行引擎层                                                        │
│  ├─ run_suite.py → API 执行 (requests)                            │
│  ├─ run_web_suite.py → Web UI 执行 (Playwright + Page Object)     │
│  └─ report.py → JSON + Markdown 报告 + 失败截图                    │
├──────────────────────────────────────────────────────────────────┤
│  测试资产层                                                        │
│  ├─ cases/*.yaml / *.json → 用例库                                 │
│  ├─ profiles/*.yaml → Selector Profile                            │
│  ├─ pages/*.py → Page Object (BasePage + 5 页面)                   │
│  └─ keywords/web_keywords.py → 12 个 web.* action                  │
└──────────────────────────────────────────────────────────────────┘
```

## File Structure

```text
qcoder-web-api-autotest-agent/
├── SKILL.md                      # Qoder AI 知识入口
├── _meta.json                    # Qoder 元数据
├── mcps/web-autotest/            # MCP Server (工具层)
│   ├── SERVER_METADATA.json
│   ├── server.py                 # MCP stdio 实现
│   └── tools/                    # 6 个工具 schema
├── agent_cli.py                  # CLI 后端 (MCP 调用它)
├── agent/workflows/              # AI 工作流 prompt 模板
├── cases/                        # 测试用例资产
├── pages/                        # Page Object
├── keywords/                     # Web 关键字
├── profiles/                     # 设备/Selector Profile
├── runner/                       # 执行引擎
├── mock_gateway/                 # Mock 服务
├── requirements/                 # 需求文档
├── changes/                      # 变更说明
├── reports/                      # 执行报告
└── ai_outputs/                   # AI 工作流输出
```

---

## Lifecycle Orchestration — 完整测试闭环

当用户说"执行版本回归"时，AI 应按以下顺序串联 MCP 工具：

```text
Step 1: generate_test_cases(module="ALL", test_layer="web")
  → 确认用例库覆盖完整（如有缺口先补生成）
  ↓
Step 2: run_test_suite(suite_type="smoke", test_layer="web")
  → 先跑 smoke，确认基本功能正常
  ↓
Step 3: run_test_suite(suite_type="regression", test_layer="web")
  → 跑全量回归
  ↓
Step 4: get_test_report(format="md")
  → 读取报告，展示通过/失败
  ↓
Step 5: analyze_failure(test_layer="web")
  → 如果有失败，自动分析失败原因和分类
  ↓
Step 6: get_coverage_matrix()
  → 展示覆盖矩阵，指出缺口
  ↓
Step 7: update_cases_by_change(change_file="changes/xxx.md")
  → 如果有版本变更，分析影响范围
  ↓
输出: 准入结论 + 覆盖矩阵 + 失败分析 + 补测建议
```

### 变更驱动闭环

当用户说"这个版本改了 Wi-Fi 密码规则"时：

```text
Step 1: update_cases_by_change(change_file="changes/v1.0.1_wifi_change.md")
  → 分析受影响用例
  ↓
Step 2: generate_test_cases(module="WiFi", test_layer="web")
  → 补生成缺失的边界用例
  ↓
Step 3: run_test_suite(suite_type="regression", test_layer="web")
  → 执行回归
  ↓
Step 4: analyze_failure(test_layer="web")
  → 分析失败（如有）
  ↓
输出: 受影响用例 + 新增用例 + 回归结果 + 失败分析
```

---

## YAML 用例格式参考

```yaml
suite_id: SMOKE-INTL-WEB-UI
title: "国际网关基线 Web UI 冒烟测试"
cases:
  - id: TC-WEB-LOGIN-001
    title: "Admin login succeeds with valid credentials"
    module: Login
    priority: P0
    tags: [smoke, login, positive]
    steps:
      - action: web.navigate
        params: { page: login }
      - action: web.login
        params: { username: admin, password: admin123 }
        expect: true
      - action: web.assert_visible
        params: { selector_key: dashboard_container, page: status }
        expect: true
```

## Web Action 关键字表

| Action | 说明 | 必需参数 |
|---|---|---|
| web.navigate | 导航到页面 | page |
| web.login | 登录 | username, password |
| web.click | 点击元素 | selector_key |
| web.fill | 填写输入框 | selector_key, value |
| web.check | 勾选复选框 | selector_key, checked |
| web.assert_text | 断言文本 | selector_key, expected |
| web.assert_visible | 断言元素可见 | selector_key |
| web.get_text | 获取文本 | selector_key |
| web.screenshot | 截图 | path |
| web.wait | 等待 | ms |
| web.save_wifi | 保存 Wi-Fi 配置 | ssid, password |
| web.reboot | 执行重启 | - |

---

## MCP Server 注册

在 Qoder 项目设置中添加 MCP Server：

```json
{
  "name": "web-autotest",
  "command": "python",
  "args": ["c:/web_auto_test/tech-test-automation/qcoder-web-api-autotest-agent/mcps/web-autotest/server.py"]
}
```

注册后 Qoder AI 自动发现 6 个工具。

## CLI 后端（备用）

MCP Server 不可用时，可降级为 CLI 调用：

```bash
python agent_cli.py run-web-suite --suite smoke --profile intl_baseline_web
python agent_cli.py generate-web-cases --requirement requirements/intl_baseline_web_scope.md --module WiFi
python agent_cli.py analyze-web-failure --latest
python agent_cli.py coverage-review
python agent_cli.py update-cases --change changes/v1.0.1_wifi_change.md
```

---

## Extension Guide

### 新增页面

1. Mock 网关加页面：`mock_gateway/web/<page>.html`
2. Selector Profile 加定义：`profiles/intl_baseline_web.yaml` → `selectors.<page>` 组
3. 新增 Page Object：`pages/<page>_page.py`（继承 BasePage）
4. 写 YAML 用例：`cases/regression/web/<page>_web.yaml`
5. 更新需求文档：`requirements/intl_baseline_web_scope.md`

### 新增 Web Action

1. `keywords/web_keywords.py` 的 `_dispatch` 表加映射
2. 实现 `_action_xxx` 方法
3. 更新本 SKILL.md 的 Action 关键字表

### 新增 MCP 工具

1. `mcps/web-autotest/tools/<tool_name>.json` — 工具 schema
2. `mcps/web-autotest/server.py` — 实现 `tool_<tool_name>()` 函数并注册到 `TOOLS` 字典
3. 更新 `SERVER_METADATA.json` 的 `toolCount`

### 接入真实设备

1. 先运行扫描脚本自动发现页面元素：
```bash
python scripts/scan_selectors.py http://192.168.1.1 --auth admin:password
```
2. 根据扫描结果确认 Profile selector（name 属性优先）
3. 修改 `profiles/intl_gateway_web.yaml`：
```yaml
base_url: "http://192.168.1.1"
auth:
  username: <real_username>
  password: <real_password>
```

### Selector 策略（v0.3.0+）

不改前端代码，按优先级选择 selector。
注意：国际版本 UI 文本随语言切换变化，文本型 selector 一律不作为首选：
| 优先级 | 策略 | 适用 |
|---|---|---|
| 1 | `input[name='xxx']` | 表单输入框（name 属性最稳定） |
| 2 | `button[type='submit']` | 提交按钮 |
| 3 | `input[type='checkbox']` | 复选框 |
| 4 | `#id` | 展示型 td 元素（兜底，前端可能改 id） |
| 5 | `button:has-text('XX')` | 按钮兜底（i18n 文本会变，降级使用） |
| 6 | `.class` | 提示信息元素（兜底，前端可能改 class） |

---

## NEVER Do

1. **NEVER 在用例中硬编码真实密码到报告中** — 使用 profile 中的 auth 配置
2. **NEVER 在 YAML 用例中使用未在 selector profile 中定义的 selector_key**
3. **NEVER 跳过 web.navigate 步骤** — 每个用例必须以 navigate 建立页面上下文
4. **NEVER 依赖上一次执行的残留状态** — 每条用例必须可独立重复执行；配置修改类用例必须以恢复基线配置结尾
5. **NEVER 直接用 CSS class 作为首选 selector** — 优先级：`input[name]` > `[type]` > `#id` > `button:has-text()` > `.class`（i18n 产品文本会变，text 型降级）
6. **NEVER 优先用 CLI 而不用 MCP 工具** — MCP 是 Qoder AI 的首选调用方式
7. **NEVER 让框架隐式推断登录预期** — `web.login` 必须显式声明 `expect: true/false`
8. **NEVER 只生成越界拒绝用例** — 每个边界约束必须同时生成上点（有效值通过）与离点（越界拒绝）用例
