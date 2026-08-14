# 自动化测试专家包 (tech-test-automation)

从 TDD 方法论到 E2E/API 测试自动化、QA 测试计划的完整自动化测试工作流。
支持 Python(pytest)、JavaScript(Jest/Vitest/Mocha)、Go 等多语言。

## 目录结构

```
.
├── manifest.json                          # 专家包清单
├── qcoder-web-autotest-agent-plan.md      # QCoder Web 自动化测试智能体规划
├── skills/                                # 6 个独立技能 (zip)
│   ├── superpowers-tdd.zip                # TDD 方法论 (红-绿-重构)
│   ├── test-case-generator.zip            # 测试用例自动生成
│   ├── test-patterns.zip                  # 跨语言测试编写与运行
│   ├── e2e-testing-patterns.zip           # E2E 测试编排 (Playwright/Cypress)
│   ├── api-test-automation.zip            # API 测试自动化 (REST/GraphQL)
│   └── afrexai-qa-test-plan.zip           # QA 测试计划与覆盖率矩阵
├── skillsets/
│   └── tech-test-automation.md            # 技能编排定义 (meta-skill)
└── qcoder-web-api-autotest-agent/         # QCoder Demo 项目
    ├── agent/workflows/                   # 5 个 AI 工作流模板
    ├── cases/                             # 测试用例 (smoke + regression)
    ├── changes/                           # 版本变更说明
    ├── mock_gateway/                      # Mock 国际网关 API
    ├── profiles/                          # 设备 Profile
    ├── requirements/                      # 基线测试范围
    ├── reports/                           # 执行报告 (gitignored)
    └── runner/                            # 用例执行器和报告器
```

## 技能编排流程

```
步骤 1  TDD 方法论与测试策略    -> superpowers-tdd
步骤 2  自动生成测试用例        -> test-case-generator
步骤 3  跨语言测试编写与运行    -> test-patterns
步骤 4  E2E 测试编排与执行      -> e2e-testing-patterns
步骤 5  API 接口测试自动化      -> api-test-automation
步骤 6  QA 测试计划与报告       -> afrexai-qa-test-plan
```

## Demo 项目快速运行

```bash
# 启动 Mock 网关
python qcoder-web-api-autotest-agent/mock_gateway/server.py

# 执行 smoke 套件
python qcoder-web-api-autotest-agent/runner/run_suite.py --suite smoke --profile intl_baseline

# 执行回归套件
python qcoder-web-api-autotest-agent/runner/run_suite.py --suite regression --profile intl_baseline
```

## QCoder AI 工作流

| 工作流 | 文件 | 作用 |
|--------|------|------|
| 用例生成 | agent/workflows/generate_cases.md | 根据需求/接口说明生成测试用例 |
| 变更更新 | agent/workflows/update_cases_by_change.md | 根据修改点更新用例 |
| 回归选择 | agent/workflows/select_regression.md | 根据版本变更推荐回归集 |
| 失败分析 | agent/workflows/analyze_failure.md | 根据报告和日志分析失败原因 |
| 覆盖分析 | agent/workflows/coverage_review.md | 生成覆盖矩阵和缺口建议 |
