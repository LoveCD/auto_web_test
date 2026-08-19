# 使用方法（Usage）

QCoder Web AutoTest Agent —— 面向烽火网关真实 UI 的自动化测试工具，支持：

- **运营商区分**：`--operator cm`（中国移动）/ `--operator intl`（国际通用），可扩展
- **双环境**：`--env real`（真机 Playwright 测试 + 截图）/ `--env mock`（离线 Mock，无设备也能跑）
- **自然语言生成用例**：输入一句中文需求，基于真实 UI 源码自动生成可执行用例
- **双端 Skill 封装**：同时适配 WorkBuddy（项目级 skill）与 QCoder（SkillHub zip 包）

## 0. Skill 安装与调用（WorkBuddy / QCoder 双端）

本工具已封装为 **qcoder-web-autotest** 技能，两个平台均可用同一套命令。

### 0.1 WorkBuddy 安装

项目级 skill 已就位（随项目同步），无需额外安装：

```text
qcoder-web-autotest-agent/.workbuddy/skills/qcoder-web-autotest/SKILL.md
```

在 WorkBuddy 中打开本项目的会话后，直接以自然语言触发即可：

```text
"测试wan连接页面vlan绑定功能"
"运行 CM 真机回归套件"
"用自然语言生成 wifi 320MHz 频段测试用例并跑真机验证"
"跑一遍全菜单遍历截图"
```

### 0.2 QCoder 安装

QCoder 使用 SkillHub 兼容的 zip 格式：

```bash
# 方式 A：导入 zip（推荐）
#   将 skill_dist/qcoder-web-autotest.zip 导入 QCoder 技能中心
# 方式 B：解压目录
#   解压 skill_dist/qcoder-web-autotest/ 到 QCoder skills/ 目录
```

安装后，QCoder 中同样以自然语言触发（同 0.1 示例）。

### 0.3 Skill 触发词

| 意图 | 触发示例 |
|---|---|
| 自然语言生成用例 | 测试XX页面XX功能 / 生成用例 |
| 运行套件 | 运行 smoke / regression / navigation |
| 真机验证 | 真机测试 / 连设备跑 / 截图 |
| 离线验证 | mock 测试 / 离线跑 / CI |
| 查看说明 | 怎么用 / 使用说明 / 封装说明 |

### 0.4 Skill 内容结构

| 平台 | 位置 | 说明 |
|---|---|---|
| WorkBuddy | `.workbuddy/skills/qcoder-web-autotest/` | 项目级 skill，随仓库分发 |
| QCoder | `skill_dist/qcoder-web-autotest.zip` | SkillHub zip（SKILL.md + README.md + _meta.json） |
| 源码目录 | `skill_dist/qcoder-web-autotest/` | zip 的未压缩版本，便于审查/修改 |

## 1. 环境准备

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | >= 3.8 | 运行执行器与 Mock 服务器 |
| Playwright | >= 1.44 | E2E 浏览器自动化引擎 |
| Chromium | 随 Playwright | 真机测试默认浏览器 |

```bash
cd qcoder-web-autotest-agent
pip install -r requirements.txt
playwright install chromium
```

## 2. 命令速查

所有命令在项目根目录执行：

```bash
# ============ 自然语言生成用例（无需设备）============
python -m generator.generate_case --operator cm --query "测试wan连接页面vlan绑定功能"
python -m generator.generate_case --operator cm --query "测试wifi基础设置功能支持320MHZ频段设置"

# ============ 真机测试（设备可达时）============
python runner/run_suite.py --operator cm  --env real --suite smoke        # CM 冒烟（11 条）
python runner/run_suite.py --operator cm  --env real --suite regression  # CM 回归（8 条）
python runner/run_suite.py --operator cm  --env real --suite navigation  # CM 全菜单遍历截图
python runner/run_suite.py --operator cm  --env real --suite generated/gen_wifi_320mhz  # 运行生成的用例

# ============ Mock 测试（离线/CI）============
python runner/run_suite.py --operator intl --env mock --suite smoke       # INTL 冒烟
python runner/run_suite.py --operator cm  --env mock --suite mock_smoke  # CM 冒烟（Mock 版）

# 可选参数
#   --headed                有头模式（调试观察）
#   --browser firefox       切换浏览器
#   --url http://x.x.x.x    临时覆盖 base_url
```

退出码：`0` 全部通过，`1` 存在失败（可直接接入 CI 门禁）。

## 3. 自然语言生成用例（核心能力）

### 3.1 基本用法

```bash
python -m generator.generate_case --operator cm --query "测试wan连接页面vlan绑定功能"
```

生成器工作流程：

1. **扫描真实 UI 源码**（`web/web/UI/CM/fiberweb/html/src/content/pages/*.js`），
   索引每个页面的 component 名、菜单路由、页面标题、表单元素
   （`setItemId('x')` → 运行时 id `fhId_x`）、下拉选项、数值校验规则
2. **分词并匹配目标页面**（component 驼峰切分 + 中英同义词 + 标题/元素打分）
3. **匹配页面内功能元素**（label 命中即生成元素断言）
4. **跨页元素搜索**：目标功能不在最高分页面时自动定位真实所在页
   （如 "320MHz 频段" 的信道宽度元素在 `wifiAdvanced_5g` 而非 `wifiBasic`）
5. **需求差距检测（gap）**：需求值（如 320MHz）不在源码选项中时，
   生成"验证选项存在"用例 —— 真机执行失败即证明需求未实现
6. 输出到 `operators/cm/cases/generated/{name}.json` + 生成报告

### 3.2 实际效果示例

```
$ python -m generator.generate_case --operator cm --query "测试wifi基础设置功能支持320MHZ频段设置"
[GEN] case         : TC-CM-GEN-001  wifiBasic  (5 steps)
[GEN] case         : TC-CM-GEN-002  wifiAdvanced - OperatingChannelBandwidth  (7 steps)
[GEN] case         : TC-CM-GEN-003  wifiAdvanced_5g - OperatingChannelBandwidth  (7 steps)
[GEN] ⚠ 需求差距（UI 源码中未实现，已生成验证用例，真机执行将失败）:
       - wifiAdvanced_5g/OperatingChannelBandwidth(信道宽度管理) 需求 320MHz，
         现有选项 ['20MHz', '40MHz', '20MHz/40MHz/80MHz', '80MHz',
                   '20MHz/40MHz/80MHz/160MHz', '160MHz']
[GEN] run command  : python runner/run_suite.py --operator cm --env real --suite generated/gen_wifi_320mhz
```

### 3.3 生成后执行

```bash
python runner/run_suite.py --operator cm --env real --suite generated/gen_wifi_320mhz
```

生成报告（含 token、匹配页面、差距明细）见
`operators/cm/cases/generated/{name}_report.json`。

> UI 源码更新后加 `--refresh` 重建索引缓存。

## 4. 真机测试（--env real）

真机地址与账号**不写入代码/配置**，通过工程根 `.env` 注入（复制 `.env.example` 为 `.env` 并填写）：

```dotenv
# .env（已被 .gitignore 排除）
QCT_CM_BASE_URL=http://192.168.1.1
QCT_CM_ADMIN_USER=<管理员账号>
QCT_CM_ADMIN_PASS=<管理员密码>
QCT_CM_USER_USER=<普通用户账号>
QCT_CM_USER_PASS=<普通用户密码>
```

`operators/cm/profile.json` 中通过 `${VAR}` 占位符引用环境变量，运行时自动解析：

```json
"env": {
  "real": {
    "base_url": "${QCT_CM_BASE_URL:-http://192.168.1.1}",
    "auth": {
      "admin": {"username": "${QCT_CM_ADMIN_USER}", "password": "${QCT_CM_ADMIN_PASS}"},
      "user":  {"username": "${QCT_CM_USER_USER}",  "password": "${QCT_CM_USER_PASS}"}
    }
  }
}
```

也可用命令行临时覆盖：`--url http://x.x.x.x --admin-user xxx --admin-pass xxx`。

- 登录自适应 CM/AP 两种登录容器（`#user_name` / `#loginpp`）
- SPA 智能导航：优先逐级点击菜单（`fhId_{title}_L{level}`）展开，回退 hash 直达
- **navigation 套件**：登录后自动展开全部 L1→L2→L3 菜单并逐一截图，
  无需手写用例即可覆盖全部页面
- 每步失败自动截图（`FAIL_TC-*.png`），通过用例按步骤命名截图
  （`reports/{run_id}/screenshots/`）

⚠️ 真机注意事项：
- 连续 3 次密码错误会锁定 1 分钟（负向登录用例已做间隔处理）
- 涉及配置修改的用例（WiFi、VLAN 等）只做**只读断言**，不点击"保存设置"

## 5. Mock 测试（--env mock）

Mock 服务仿真网关管理页面，支持 Cookie 会话鉴权与真实设备一致的业务校验，
适合离线开发与 CI 无设备场景：

```bash
# 终端 1：启动 Mock 服务（默认 127.0.0.1:8899）
python mock_web_ui/server.py

# 终端 2：运行 Mock 套件
python runner/run_suite.py --operator intl --env mock --suite smoke
python runner/run_suite.py --operator cm  --env mock --suite mock_smoke
```

## 6. 报告与截图

每次运行生成 `reports/{时间戳}_{operator}_{env}_{suite}/`：

| 文件 | 说明 |
|---|---|
| `result.json` | 用例/步骤级结果（含失败原因） |
| `report.json` / `report.html` | 人读报告 |
| `screenshots/*.png` | 全部截图（PASS 按步骤命名，FAIL 前缀标红） |

## 7. e2e_bootstrap（Node 端用例生成 + DOCX 报告）

工程内集成了 **web-playwright-e2e-bootstrap** 技能（模板资产位于 `e2e_bootstrap/`，
核心为 `templates/test-report-template.docx` 报告模板 + 三字段用例生成器）：

```bash
cd e2e_bootstrap
cp .env.example .env          # 配置 E2E_BASE_URL / E2E_DEMO_PATH
npm install
npx playwright install chromium
npm run test:generate -- --input ./TEST_CASE_SPEC.md --name 新人快速上手
npm test
```

- 三字段输入（`TEST_CASE_SPEC.md`）：`测试类型` / `测试网址` / `测试内容` → 生成 `tests/generated/*.spec.js`
- 报告：`playwright-report/index.html` + `self-test-reports/*.docx`（每条用例备注内嵌截图）
- 报告顺序跟随 `tests/case-plan.js`（结构化测试计划）
- 业务示例见 `tests_examples/roaming-settings.spec.example.js`（不参与运行）

## 8. 用例编写规范（real 模式）

用例 JSON 位于 `operators/{operator}/cases/*.json`：

```json
{
  "id": "TC-CM-WIFI-001",
  "module": "Network",
  "priority": "P0",
  "title": "WiFi 基本设置页加载",
  "steps": [
    {"action": "real.login", "params": {"role": "admin"}},
    {"action": "real.navigate_spa", "params": {"route": "/network/wifiSettings/wifiBasic"}},
    {"action": "real.assert_page", "params": {"component": "wifiBasic"},
     "expect": {"visible": "page.container"}},
    {"action": "real.assert_element", "params": {"selector": "#fhId_SSID"}},
    {"action": "real.select_option", "params": {"selector": "#fhId_OperatingChannelBandwidth", "option_text": "160MHz"}},
    {"action": "real.screenshot", "params": {"name": "wifi_basic"}}
  ]
}
```

常用 `real.*` 动作：

| 动作 | 参数 | 说明 |
|---|---|---|
| `real.login` | `role: admin/user` | 登录（自适应登录容器） |
| `real.logout` | - | 退出登录 |
| `real.navigate_spa` | `route` | 智能导航到 SPA 路由 |
| `real.click_menu` | `level, title` | 点击 L1/L2/L3 菜单 |
| `real.click` / `real.fill` | `selector[, value]` | 点击 / 填写（支持原始选择器） |
| `real.select_option` | `selector, option_text` | ElementUI 下拉选择 |
| `real.assert_page` | `component` | 断言页面已渲染（#el_main 可见且有内容） |
| `real.assert_element` | `selector` | 断言元素存在 |
| `real.assert_option_present` | `selector, option_text` | 断言下拉含某选项（差距验证） |
| `real.assert_visible` / `real.assert_text_contains` | key | 可见性 / 文本断言 |
| `real.ensure_switch` | `selector, checked` | 确保 el-switch 处于目标状态（不同则点击，幂等） |
| `real.assert_switch_checked` | `selector, checked` | 断言 el-switch 开启状态 |
| `real.assert_element_hidden` | `selector` | 断言元素不存在/不可见（v-if 移除视为隐藏） |
| `real.assert_input_value` | `selector, value` | 断言 el-input 当前值（自动取组件内部 input） |
| `real.click_button` | `text` | 按按钮文本点击（兼容无 id 的保存按钮） |
| `real.screenshot` | `name` | 截图 |

选择器 key（如 `login.username`）从 `operators/{op}/selectors.json` 解析；
也支持直接写原始选择器（`#fhId_xxx`、`text=退出`）。

### 7.1 双频合一（Band Steering）用例

- **CM 真机**：套件 `operators/cm/cases/wifi_band_steering.json`
  ```bash
  python runner/run_suite.py --operator cm --env real --suite wifi_band_steering
  ```
  双频合一开关位于「网络 → 无线基本配置」（`fhId_wifiBasicSettings_L3` → wificonfig 组件，
  route `/network/wifiSettings/wificonfig`），开关 `#fhId_onApplySameSSID`。开启后
  `#fhId_Enable5G`/`#fhId_SSID5G` 等 5G 独立配置区域隐藏，保存时 2.4G SSID/密码同步到 5G；
  保存按钮为纯文本「保存」（无 id，需 `real.click_button`）；弱密码保存会弹 `fh_confirm`
  确认框（自动 dismiss = 取消保存），用例须用强密码。gap 用例 TC-CM-WBS-005 验证
  wifiAdvanced（2.4G 无线高级配置）页无双频合一开关，真机执行将失败以暴露需求差异。
- **INTL**：套件 `operators/intl/cases/band_steering.json`，独立页面 route
  `/network/wifiSettings/bandSteering`，开关 `#fhId_Enable`，按钮 `#fhId_onApply`。
  MLO 开启或 FTTR_SUB 组网下表单禁用，用例将失败以暴露该限制。

## 8. 扩展新运营商

1. 复制 `operators/cm/` 为 `operators/{new_op}/`
2. 修改 `profile.json`（环境地址、账号、菜单模块、页面清单）
3. 修改 `selectors.json`（登录/菜单/通用元素选择器）
4. 编写 `cases/*.json` 用例
5. 运行：`python runner/run_suite.py --operator {new_op} --env real --suite smoke`
6. NL 生成器：`DEFAULT_UI_ROOTS` 中加入新运营商源码路径即可
   `python -m generator.generate_case --operator {new_op} --query "..."`
