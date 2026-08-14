# 基于 QCoder 的 Web 自动化测试智能体规划

## 目标定位

基于 **QCoder 智能体 + tech-test-automation 技能包**，建设一个面向宽带终端国际基线版本的 Web 自动化测试智能体。

目标是在 2026 年 9 月 30 日前，至少覆盖一个国际基线版本的 Web 核心回归测试，并体现实际提效：

```text
人工执行：约 3 人日
智能体自动化执行：缩短到 2 小时以内
```

该方案不是建设一个普通 Playwright/pytest 自动化框架，而是建设一个能够固化测试经验、自动生成和维护测试资产、自动执行和分析结果的 Web 测试智能体。

## 组成分工

| 组成 | 作用 |
|---|---|
| tech-test-automation 技能包 | 提供测试方法论、用例生成、E2E 模式、报告和覆盖矩阵思路 |
| QCoder 智能体 | 执行测试工作流：读需求、生成用例、生成脚本、运行测试、分析失败、维护用例 |
| Playwright/pytest | Web 页面自动化执行引擎 |
| YAML 用例库 | 固化领域测试资产 |
| Profile/Selector | 固化设备型号、页面元素、版本差异 |
| 报告系统 | 固化执行结果、覆盖率、失败归因、提效数据 |

## QCoder 智能体需要固化的能力

### 1. 基线版本回归执行 Agent

输入：

```text
产品型号
国际基线版本号
设备访问地址
测试套件：smoke / core-regression
```

输出：

```text
自动执行 Web 回归
生成 HTML/JSON 报告
输出准入结论
```

示例命令：

```text
qcoder run web-regression --profile intl_baseline --suite core
```

### 2. 新功能用例生成 Agent

输入需求或页面说明，例如：

```text
新增访客 Wi-Fi 页面，字段包括启用开关、SSID、密码、有效期、最大接入数。
```

QCoder 输出：

```text
P0/P1/P2 测试点
YAML 自动化用例
需要新增的 Page Object 方法
Selector profile 模板
```

### 3. 修改点影响分析 Agent

输入版本修改点，例如：

```text
本版本修改 Wi-Fi 密码校验规则，保存按钮由“保存”改为“应用”。
```

QCoder 输出：

```text
受影响用例
需要更新的 YAML
需要更新的 selector
建议新增的边界测试
建议执行的回归集
```

### 4. 失败分析 Agent

输入执行报告、截图、trace、DOM，例如：

```text
TC-WEB-WIFI-001 失败，保存按钮点击超时。
```

QCoder 输出：

```text
失败类型：selector_changed / product_bug / env_issue / script_bug
证据
修复建议
影响范围
是否建议重跑
```

### 5. 覆盖分析 Agent

输入需求清单和用例库：

```text
分析国际基线 Web 测试覆盖情况。
```

QCoder 输出：

```text
页面覆盖矩阵
P0/P1 覆盖率
未覆盖功能
下一轮补充建议
```

## 推荐落地架构

```text
qcoder-web-autotest/
  skills/
    tech-test-automation/

  agent/
    prompts/
      generate_cases.md
      update_cases_by_change.md
      select_regression.md
      analyze_failure.md
      coverage_review.md

  requirements/
    intl_baseline_web_scope.md
    wifi.md
    wan.md
    lan.md
    system.md

  cases/
    smoke/
    regression/
      login/
      status/
      wifi/
      wan/
      lan/
      system/
      upgrade/

  profiles/
    intl_baseline.yaml
    selectors/
      intl_baseline_selectors.yaml

  pages/
    login_page.py
    status_page.py
    wifi_page.py
    wan_page.py
    lan_page.py
    system_page.py

  keywords/
    web_keywords.py
    gateway_keywords.py
    assert_keywords.py

  runner/
    run_suite.py
    run_case.py
    report.py

  reports/
```

## 9 月 30 日前路线

| 时间 | 目标 | 产出 |
|---|---|---|
| 8.12-8.16 | 固定国际基线 Web 测试范围 | 页面清单、人工 3 人日基线、目标用例集 |
| 8.17-8.23 | QCoder 跑通最小闭环 | 登录、状态页、报告 |
| 8.24-9.06 | 覆盖核心页面 | 约 60-70 条 Web 自动化用例 |
| 9.07-9.15 | 固化 AI 工作流 | 用例生成、修改点更新、失败分析、覆盖分析 |
| 9.16-9.23 | 稳定执行和提速 | 核心回归 <= 2 小时 |
| 9.24-9.30 | 效果验证和汇报 | 提效报告、演示材料、覆盖矩阵 |

## MVP 范围建议

第一版只覆盖国际基线版本 Web 核心回归。

| 模块 | 建议用例数 |
|---|---:|
| 登录 | 5 |
| 状态页 | 8 |
| Wi-Fi | 20 |
| WAN | 15 |
| LAN | 8 |
| 系统维护 | 8 |
| 固件升级页 | 6 |
| 合计 | 约 70 |

目标：

```text
人工执行：约 3 人日
QCoder 智能体执行：<= 2 小时
Smoke 执行：<= 20 分钟
失败分析：自动生成初判
报告整理：自动完成
```

## QCoder 的核心价值表达

不要把它定义为“QCoder 写了 Playwright 脚本”，而要定义为：

```text
QCoder 将宽带终端 Web 测试经验固化为：
测试模型 + YAML 用例 + 页面对象 + 设备 Profile + AI 工作流。
```

它需要形成四个闭环：

```text
新功能：
需求 -> AI 生成用例 -> AI 生成脚本 -> 人工审核入库

修改点：
变更说明 -> AI 影响分析 -> 更新用例/selector -> 推荐回归集

版本回归：
版本选择 -> 自动执行 -> AI 失败归因 -> 准入报告

覆盖治理：
需求清单 -> 用例库扫描 -> 覆盖矩阵 -> 缺口补充建议
```

## 最小成功标准

到 2026 年 9 月 30 日，至少能够现场演示：

1. 输入一个版本号和 profile。
2. 一键执行国际基线 Web 核心回归。
3. 自动生成 HTML/JSON 测试报告。
4. 展示某个失败用例的截图、日志和 AI 归因。
5. 输入一个修改点，AI 推荐要更新或新增的用例。
6. 展示页面级覆盖矩阵。
7. 对比人工 3 人日与自动化 2 小时的提效结果。

## 一句话定位

基于 QCoder 的方案不是做一个普通 Web 自动化框架，而是做一个：

```text
面向宽带终端国际基线版本的 Web 测试智能体，
把测试设计、用例维护、自动执行、失败分析和报告输出固化成可重复流程。
```
