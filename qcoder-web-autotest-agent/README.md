# QCoder Web AutoTest Agent

面向**网关真实 Web UI** 的端到端（E2E）自动化测试智能体：一句话中文需求 → 自动生成可执行用例 → 真机/离线 Mock 双环境执行 → 结构化报告（含截图）。

基于 `tech-test-automation` 技能包（superpowers-tdd / test-case-generator / test-patterns /
e2e-testing-patterns / api-test-automation / afrexai-qa-test-plan）的方法论构建，
已封装为 **qcoder-web-autotest** 技能（适配 WorkBuddy 与 QCoder 双平台），
并内置 **web-playwright-e2e-bootstrap** 技能（Node 端用例骨架生成 + DOCX 自测报告）。

```text
需求/修改点 / 一句中文自然语言
  -> 扫描真实 UI 源码 + 索引（setItemId -> fhId_*）
  -> 自动生成可执行 JSON 用例（含需求差距检测）
  -> 设备 Profile + Selector（运营商目录隔离，敏感信息经 .env 注入）
  -> Playwright 真机执行 / 离线 Mock 执行
  -> 自动报告（JSON/MD/HTML + 截图 + 覆盖矩阵）
  -> AI 失败分析和覆盖分析
```

## 核心能力

- **双运营商**：`--operator cm`（中国移动）/ `--operator intl`（国际），目录化扩展
- **双环境**：`--env real`（真机 Playwright 测试 + 截图）/ `--env mock`（离线 Mock，无设备也能跑，可接入 CI）
- **自然语言生成用例**：如"测试wan连接页面vlan绑定功能"、"测试wifi基础设置功能支持320MHZ频段设置"
- **需求差距检测**：需求值（如 320MHz）不在 UI 源码选项时生成验证用例，真机失败即证明需求未实现
- **全菜单遍历截图**：navigation 套件自动展开 L1→L2→L3 菜单逐页截图（98 页实测）
- **Node E2E 基线（e2e_bootstrap/）**：三字段极简输入生成用例骨架，HTML/DOCX 自测报告（截图嵌入用例备注）

## 环境准备

需要 Python 3.8+ 与 Node.js 16+（e2e_bootstrap 可选）。

```bash
# 1. Python 依赖
pip install -r requirements.txt
playwright install chromium

# 2. 敏感配置注入（复制模板并填写，.env 已被 gitignore，不会上传）
cp .env.example .env
# 编辑 .env：QCT_CM_BASE_URL / QCT_CM_ADMIN_USER / QCT_CM_ADMIN_PASS / QCT_CM_USER_USER / QCT_CM_USER_PASS
```

> 安全设计：真机地址与账号**不写入代码与 profile.json**，全部经 `.env` / 环境变量注入
> （`operators/cm/profile.json` 中以 `${QCT_*}` 占位符引用，运行时由 `core/config.py` 解析），
> 因此本仓库可安全公开发布。CI 场景可将这些变量配置为 GitHub Secrets。

## 快速开始

```bash
# 自然语言生成用例（无需设备，走内置索引缓存）
python -m generator.generate_case --operator cm --query "测试wan连接页面vlan绑定功能"

# 真机冒烟/回归/全菜单遍历（配置好 .env 且设备可达时）
python runner/run_suite.py --operator cm --env real --suite smoke
python runner/run_suite.py --operator cm --env real --suite regression
python runner/run_suite.py --operator cm --env real --suite navigation

# 离线 Mock（无设备 / CI）
python mock_web_ui/server.py          # 或由执行器自动拉起
python runner/run_suite.py --operator intl --env mock --suite smoke

# 生成 Word 测试报告（读取 reports/ 最新结果）
pip install python-docx
python tools/gen_word_report.py
```

可选参数：`--headed`（有头调试）/ `--browser firefox` / `--url http://x.x.x.x`
`--admin-user xxx --admin-pass xxx`（临时覆盖账号）。
退出码：`0` 全部通过，`1` 存在失败（可接入 CI 门禁）。

## e2e_bootstrap（Node 端 E2E 基线）

集成自 **web-playwright-e2e-bootstrap** 技能（`assets/e2e-template/templates` 报告模板为核心），
与 Python 主链路互补，适合快速引导新工程或输出带截图的 DOCX 自测报告：

```bash
cd e2e_bootstrap
cp .env.example .env
npm install
npx playwright install chromium
npm run test:generate -- --input ./TEST_CASE_SPEC.md --name 新人快速上手   # 生成用例骨架
npm test                                                                 # 执行 + HTML/DOCX 报告
```

产物：`e2e_bootstrap/playwright-report/index.html`、`e2e_bootstrap/self-test-reports/*.docx`（截图嵌入）。
详见 [e2e_bootstrap/README.md](e2e_bootstrap/README.md)。

## 目录结构

```text
qcoder-web-autotest-agent/
├── .workbuddy/skills/                    # WorkBuddy 项目级技能（qcoder-web-autotest + web-playwright-e2e-bootstrap）
├── skill_dist/                           # QCoder SkillHub 技能包（*.zip 双技能）
├── core/config.py                        # 统一配置：.env 加载 + ${VAR} 占位符解析
├── operators/
│   ├── cm/                               # 中国移动：profile/selectors/cases（敏感值经 .env 注入）
│   └── intl/                             # 国际（同构目录）
├── keywords/                             # 真机关键字层（real_keywords.py）+ 断言引擎
├── runner/run_suite.py                   # 用例执行器 + 报告器
├── generator/                            # NL 用例生成器（page_index + generate_case + index_cache）
├── mock_web_ui/                          # 离线 Mock 网关（纯标准库）
├── e2e_bootstrap/                        # Node 端 Playwright E2E 基线（用例骨架生成 + DOCX 报告模板）
├── agent/workflows/                      # QCoder AI 工作流模板
├── cases/  profiles/  pages/             # 早期基线版本遗留（INTL mock）
├── reports/                              # 执行报告（自动生成，gitignore）
└── docs/                                 # 使用方法 + 部署方法 + 实现效果
```

## Skill 安装（双端）

- **WorkBuddy**：项目级技能已就位（`.workbuddy/skills/`），对话直接触发
- **QCoder**：导入 `skill_dist/qcoder-web-autotest.zip` 与 `skill_dist/web-playwright-e2e-bootstrap.zip`（SkillHub 兼容格式）

触发示例："测试wifi基础设置功能支持320MHZ频段设置" / "运行 CM 真机回归套件" / "跑全菜单遍历截图"
/ "用 e2e_bootstrap 生成用例和报告"

## 详细文档

- 使用方法：`docs/USAGE.md`（命令矩阵 / NL 生成器 / 用例规范 / .env 配置 / Skill 安装）
- 一页式说明：`docs/开发使用说明与工作流简介.docx`（项目定位 / 工作流全景 / 开发使用 / 测试报告生成，可用 `python tools/gen_usage_doc.py` 重新生成）
- 部署方法：`docs/DEPLOYMENT.md`
- 实现效果：`docs/IMPLEMENTATION_EFFECTS.md`（执行结果、覆盖矩阵、修复记录）

## License

[MIT](LICENSE)
