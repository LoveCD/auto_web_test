# QCoder Web API AutoTest Agent Demo

面向“国际网关基线版本 Web”的接口自动化测试智能体 Demo。

该 Demo 基于当前 `tech-test-automation` 技能包的思路，将接口自动化测试固化为：

```text
需求/修改点
  -> QCoder AI 工作流
  -> YAML/JSON 测试用例
  -> 设备 Profile
  -> 接口关键字执行
  -> 自动报告
  -> AI 失败分析和覆盖分析
```

## Demo 覆盖范围

首期以国际网关基线版本 Web 后台接口为例，覆盖：

- 登录认证
- 设备状态查询
- Wi-Fi 配置查询
- Wi-Fi SSID 修改
- WAN 状态查询
- 设备重启接口

## 目录结构

```text
qcoder-web-api-autotest-agent/
  agent/
    workflows/                 # QCoder AI 工作流模板
  cases/
    smoke/                     # 冒烟用例
    regression/                # 回归用例
  profiles/                    # 设备和接口 Profile
  mock_gateway/                # Demo Mock 国际网关 Web API
  runner/                      # 用例执行器和报告器
  requirements/                # 基线范围和接口说明
  reports/                     # 执行报告输出目录
```

## 快速运行

启动 Mock 网关接口：

```powershell
python .\qcoder-web-api-autotest-agent\mock_gateway\server.py
```

新开一个终端执行 smoke：

```powershell
python .\qcoder-web-api-autotest-agent\runner\run_suite.py --suite smoke --profile intl_baseline
```

执行核心回归：

```powershell
python .\qcoder-web-api-autotest-agent\runner\run_suite.py --suite regression --profile intl_baseline
```

## QCoder 智能体能力

本 Demo 固化 5 个 QCoder 工作流：

1. `generate_cases.md`：根据需求/接口说明生成测试用例。
2. `update_cases_by_change.md`：根据修改点更新用例。
3. `select_regression.md`：根据版本变更推荐回归集。
4. `analyze_failure.md`：根据执行报告和 HTTP 日志分析失败。
5. `coverage_review.md`：根据需求和用例库生成覆盖矩阵。

## 技能化入口（补丁 0ced2d5）

工程已升级为完整 Skill 形态（基线 801d3c6 → 0ced2d5，详见 `UPGRADE_README.txt`）：

- `SKILL.md`：Qoder AI 知识入口（触发词、MCP 工具层说明、8 条 NEVER 规则、Selector 策略）。
- `agent_cli.py`：CLI 后端，9 个子命令：
  - `run-suite` / `run-web-suite`：执行 API / Web UI 套件
  - `generate-cases` / `generate-web-cases`：生成用例建议
  - `update-cases`：变更影响分析（内置 10 条 CHANGE_RULES）
  - `select-regression`：回归集选择（含 flaky 治理规则）
  - `analyze-failure` / `analyze-web-failure`：失败分类与建议
  - `coverage-review`：覆盖矩阵与缺口
- `keywords/web_keywords.py`：Web 关键字分发器（13 个 `web.*` action，`web.login` 显式 `expect: true/false`）。
- `agent/workflows/`：4 个工作流对齐业界主流（BVA 三点法、CRUD write-read-verify、tags 受控词表、嵌入式家庭网关专项规则）。

CLI 使用（Python ≥3.9，需 PyYAML）：

```powershell
python agent_cli.py run-suite --suite smoke --profile intl_baseline
python agent_cli.py coverage-review
python agent_cli.py update-cases --change changes/v1.0.1_wifi_change.md
```

## 价值说明

该 Demo 不只是一个接口测试框架，而是一个可扩展的智能体骨架：

- 测试人员维护 YAML 用例，不直接写底层请求代码。
- 设备差异通过 profile 隔离。
- QCoder 负责辅助生成用例、修改用例、选择回归、分析失败、输出覆盖缺口。
- 执行器负责稳定运行和生成结构化报告。

