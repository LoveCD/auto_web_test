---
name: qcoder-web-autotest
description: 运营商网关 Web UI 自动化测试工具（WorkBuddy/QCoder 双端适配）。适用于烽火 FTTR 等网关设备管理界面的端到端测试，支持 CM（中国移动）/INTL（国际）双运营商、真机 Playwright（--env real）与离线 Mock（--env mock）双环境、中文自然语言一键生成可执行测试用例（如"测试wan连接页面vlan绑定功能"、"测试wifi基础设置功能支持320MHZ频段设置"）、全菜单遍历截图、回归/冒烟套件执行与报告输出。当用户提出测试网关/路由器 Web 界面、运行 smoke/regression/navigation 套件、用自然语言生成 Web 测试用例、真机 UI 验证、Mock 离线测试、或要求封装/使用本测试工具时触发。
license: Internal
disable: false
---

# QCoder Web AutoTest Agent

面向**烽火网关真实 Web UI** 的端到端自动化测试技能，核心能力：

- **双运营商**：`--operator cm`（中国移动 CM）/ `--operator intl`（国际），目录化扩展
- **双环境**：`--env real`（真机 Playwright + 截图）/ `--env mock`（离线 Mock 服务，无设备可跑）
- **自然语言生成用例**：一句中文需求 → 扫描真实 UI 源码 → 自动生成可执行用例 JSON（含需求差距检测）
- **全菜单遍历截图**：navigation 套件自动展开 L1→L2→L3 菜单逐页截图

## 何时使用

- 用户要求"测试 XX 页面 XX 功能"（中文自然语言生成用例）
- 用户要求运行 smoke / regression / navigation / 生成的用例套件
- 用户要求对网关/路由器 Web 管理界面做 UI 自动化验证、截图、回归
- 无真机时要求离线 Mock 测试、CI 集成
- 用户要求封装、部署、查看本工具的使用说明

## 项目位置与目录结构

项目根：`qcoder-web-autotest-agent`（本 Skill 所在项目，所有命令在项目根执行）

```text
qcoder-web-autotest-agent/
├── core/config.py               # 统一配置：.env 加载 + ${VAR} 占位符解析（敏感信息注入）
├── operators/
│   ├── cm/                     # 中国移动运营商
│   │   ├── profile.json        #   环境地址/账号/超时/SPA 配置（敏感值 ${QCT_*} 占位）
│   │   ├── selectors.json      #   登录/菜单/页面选择器
│   │   └── cases/              #   用例库
│   │       ├── smoke.json      #   冒烟（11 条）
│   │       ├── regression.json #   回归（8 条）
│   │       ├── mock_smoke.json #   Mock 专用冒烟
│   │       └── generated/      #   NL 生成器输出（gitignore）
│   └── intl/                   # 国际运营商（同构目录）
├── keywords/
│   ├── real_keywords.py        # 真机会话：导航/登录/元素级动作/断言/dialog 捕获
│   └── assert_keywords.py      # Mock 旧断言引擎
├── runner/run_suite.py         # 执行器：加载 profile/suite → 逐 case 执行 → 报告
├── generator/
│   ├── page_index.py           # UI 源码索引器（setItemId → fhId_xxx）
│   ├── generate_case.py        # NL 用例生成器（含 gap 检测）
│   └── index_cache/            # 页面索引缓存（无源码也可 NL 生成）
├── mock_web_ui/server.py       # 离线 Mock 网关（127.0.0.1:8899）
├── e2e_bootstrap/              # Node 端 E2E 基线（web-playwright-e2e-bootstrap 技能模板）
├── docs/                       # USAGE / DEPLOYMENT / IMPLEMENTATION_EFFECTS
└── reports/                    # 执行报告（JSON/MD/HTML + 截图，gitignore）
```

## e2e_bootstrap（辅助基线，可选）

Node 端 Playwright 基线（模板来自 web-playwright-e2e-bootstrap 技能）：
三字段极简输入（`e2e_bootstrap/TEST_CASE_SPEC.md`）→ 生成用例骨架 → `npm test`
→ HTML + DOCX 自测报告（截图嵌入每条用例备注）。详见 `e2e_bootstrap/README.md`。
触发语："用 e2e_bootstrap 生成用例和报告"。

**用例文档 / 执行报告统一模板**：所有用例文档与测试报告按 e2e-bootstrap 模板生成
（同一 DOCX 模板、同版式），`gen-case-doc.js` 三种模式（在 e2e_bootstrap 目录下执行）：

```bash
# ① 单套件设计文档（结果/结论=待执行）
node scripts/gen-case-doc.js ../operators/cm/cases/login.json --topic "CM登录界面验证用例" --out ../reports
# ② 批量设计文档（operators 下全部套件，排除 generated/）
node scripts/gen-case-doc.js --all --out ../reports
# ③ 执行报告（读取 run_suite.py 的 result.json，自动填充结果/结论并嵌入截图）
node scripts/gen-case-doc.js --result ../reports/<run_id>/result.json --out ../reports
```

（`--project-code`/`--base-url`/`--preconditions`/`--qcoder-root` 可选；
run_suite.py 的 `real.screenshot` 步骤会把截图路径写入 `result.detail`，报告模式据此嵌入截图。）

## 环境与账号（CM 真机）

```text
设备地址   ${QCT_CM_BASE_URL}（默认 http://192.168.1.1）
管理员     ${QCT_CM_ADMIN_USER} / ${QCT_CM_ADMIN_PASS}
普通用户   ${QCT_CM_USER_USER} / ${QCT_CM_USER_PASS}
登录页     /login.html  →  登录成功跳 /main.html（SPA，hash 路由 main.html#/...）
```

真机地址与账号**不写入代码库**，通过工程根 `.env` 注入（复制 `.env.example` 为 `.env` 填写；
`operators/cm/profile.json` 中以 `${QCT_*}` 占位符引用，运行时由 `core/config.py` 解析）。
也可命令行临时覆盖：`--url http://x.x.x.x --admin-user xxx --admin-pass xxx`。

⚠️ 连续 3 次密码错误设备锁定 1 分钟；涉及配置修改的用例只做只读断言，不点"保存设置"。

## 命令速查（在项目根目录执行）

```bash
# ---- 1. 环境准备（首次）----
pip install -r requirements.txt
playwright install chromium

# ---- 2. 自然语言生成用例（无需设备）----
python -m generator.generate_case --operator cm --query "测试wan连接页面vlan绑定功能"
python -m generator.generate_case --operator cm --query "测试wifi基础设置功能支持320MHZ频段设置"

# ---- 3. 真机测试 ----
python runner/run_suite.py --operator cm --env real --suite smoke                 # 冒烟 11 条
python runner/run_suite.py --operator cm --env real --suite regression           # 回归 8 条
python runner/run_suite.py --operator cm --env real --suite navigation           # 全菜单遍历截图
python runner/run_suite.py --operator cm --env real --suite generated/gen_wifi_320mhz  # 运行生成用例

# ---- 4. Mock 测试（离线/CI）----
python mock_web_ui/server.py                            # 终端 1：起 Mock（127.0.0.1:8899）
python runner/run_suite.py --operator intl --env mock --suite smoke
python runner/run_suite.py --operator cm  --env mock --suite mock_smoke

# 可选参数：--headed（有头调试）/ --browser firefox / --url http://x.x.x.x（覆盖 base_url）
# 退出码：0 全通过，1 有失败（可接 CI 门禁）
```

## 真机关键机制（务必理解再改用例）

1. **双登录容器**：普通版 `#wraplogin_CM`（`#user_name`/`#loginpp`/`#login_btn`）
   与 AP 版 `#fh_login_container`（`#user_name_ap`/`#loginpp_ap`/`#login_btn_ap`）仅一套可见。
   框架自动用 `offsetParent !== null` 判断激活版本，并强制显示普通版（`style.display=''`，
   注意设备 JS 以空字符串表示显示，不能设 'block'）。
2. **错误提示 = alert 弹窗**：CM 真机负向登录（密码错误）走 `alert("用户名或密码错误，请重试")`，
   `#login_error_hint` 是静态隐藏文本从不显示。会话已注册 dialog 监听自动捕获并 dismiss，
   `real.assert_login_error` 优先检查捕获的 dialog 消息，兜底检查 body 文本。
3. **setItemId() 机制**：UI 源码 `setItemId('x')` 运行时生成元素 id `fhId_x`；
   源码 JS 模板字符串中单引号转义为 `\'`，需还原再正则匹配。
4. **菜单层级 id**：L1/L2/L3 菜单 id 为 `fhId_{英文标识}_L{level}`（如 `fhId_network_L1`），
   与中文文本不同；navigation 套件按此规律自动展开遍历。
5. **真机菜单与源码存在差异**（如安全模块只有 urlFilter/firewall/parentControl/portFilter，
   WLAN 下 L3 为 wifiBasicSettings/wifiAdvanced/wifiAdvanced_5g 等）——以真机实测为准，
   改用例前先跑一次 navigation 拿真实菜单树。
6. **会话保持**：设备可能保留上一会话，访问 login.html 被重定向到 main.html；
   navigate 自动检测并 logout 后重试。
7. **navigation 渲染断言标准**：部分页面（帮助/状态/固件升级等）正常渲染但内容不含
   `fhId_*` 元素，遍历断言不能以 fhCount>0 为准，需对齐页面渲染标准——
   `#el_main` 可见且 textLen≥5 或 htmlLen≥200（与 regression `assert_page` 一致）。
8. **双频合一（Band Steering）位置**：
   - **CM（烽火 FTTR）**：开关在「网络 → 无线基本配置」（真机菜单 `fhId_wifiBasicSettings_L3`，
     实际加载 wificonfig 组件，route `/network/wifiSettings/wificonfig`），开关 `#fhId_onApplySameSSID`
     （el-switch，active-value=1/inactive-value=0，v-if 需 `wifi && wifi5`；isShowSphy 需
     FTTR_MAIN/FTTR_SUB 或广西地区）。开启后 2.4G/5G 独立配置区域隐藏
     （`v-if="sameSSIDEnable != 1"`，即 `#fhId_Enable5G`/`#fhId_SSID5G` 等不可见），保存时
     onSubmit 把 2.4G 的 SSID/密码同步写入 5G（`seturl.SSID5G`）。保存按钮为纯文本「保存」
     （**无 id**，须用 `real.click_button`）；修改弱密码会弹 `fh_confirm` 确认框（dialog
     自动 dismiss = 取消保存），用例应使用强密码（如 `Cmb5Test@2026`）。
     XML 节点：`x_wifi_WifiBandSteering_obj + x_BandSteering_Enable`。
   - **INTL**：独立页面「Band Steering」，route `/network/wifiSettings/bandSteering`，
     开关 `#fhId_Enable`，按钮 `#fhId_onApply`（Apply）/`#fhId_onCalcel`。MLO 开启或
     FTTR_SUB 组网下 `disabledForm` 会禁用表单。
   - 注意：**2.4G 无线高级配置（wifiAdvanced）页没有双频合一开关**；若需求写
     「高级设置双频合一」而要求开关在 wifiAdvanced 页，需做 gap 检查用例暴露差异。

## 自然语言生成用例（核心能力）

```bash
python -m generator.generate_case --operator cm --query "测试wifi基础设置功能支持320MHZ频段设置"
```

流程：扫描真实 UI 源码（`web/web/UI/CM/fiberweb/html/src/content/pages/*.js`）建索引
→ 分词匹配页面/元素 → 跨页搜索真实功能位置 → **需求差距检测（gap）**：需求值不在源码
选项中时生成"验证选项存在"用例，真机执行失败即证明需求未实现 → 输出到
`operators/cm/cases/generated/{name}.json` + 报告。UI 源码更新后加 `--refresh` 重建索引。

## 用例编写规范（real 模式）

用例 JSON 放 `operators/{operator}/cases/*.json`：

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

常用 `real.*` 动作：`login`/`logout`/`navigate_spa`(route)/`click_menu`(level,title)/
`click`/`fill`(selector,value)/`select_option`(selector,option_text)/
`assert_page`(component)/`assert_element`(selector)/`assert_option_present`(selector,option_text)/
`assert_option_absent`(selector,option_text)/`assert_visible`/`assert_text_contains`/`screenshot`(name)。

**开关/表单类补充关键字**（双频合一、无线总开关等场景）：
- `ensure_switch(selector, checked)` —— 确保 el-switch 处于目标状态，不同则点击（幂等，适合用例前置归一化）
- `assert_switch_checked(selector, checked=true)` —— 断言 el-switch 开启状态（is-checked 类 / 内部 checkbox）
- `assert_element_hidden(selector)` —— 断言元素不存在或不可见（v-if 移除视为隐藏）
- `assert_input_value(selector, value)` —— 断言 el-input 当前值（id 挂在组件根 div，自动取内部 input）
- `click_button(text)` —— 按按钮文本点击（兼容无 id 的保存按钮，如 wificonfig 的「保存」）

选择器 key（如 `login.username`）从 `operators/{op}/selectors.json` 解析，也支持原始选择器
（`#fhId_xxx`、`text=退出`）。负向登录用例需加 `"auto_login": false` 禁用自动登录。

**双频合一用例套件**：
- CM 真机：`operators/cm/cases/wifi_band_steering.json`（套件名 `wifi_band_steering`，5 条：
  开关存在 / 开启隐藏 5G 区域并持久化 / 关闭恢复 5G 区域并持久化 / 开启时 SSID 同步 5G /
  gap 检查 wifiAdvanced 页无开关）
- INTL：`operators/intl/cases/band_steering.json`（套件名 `band_steering`，3 条）
- 执行：`python runner/run_suite.py --operator cm --env real --suite wifi_band_steering`

### INTL 老 UI 执行器（run_intl_real_html.py）补充动作（2026-09-16）

同一页面在不同局方/机型上能力不同时，优先用「条件跳过」动作把环境受限降级为 SKIP，而不是让它 FAIL：

- `real.set_switch(selector, on)` —— 幂等设置 el-switch（已是目标态则不动，切换后复读校验）。适合无线开关这类「用例要求先处于某状态」的前置，避免单纯 `click` 的切换语义让同一用例时对时错
- `real.skip_if_disabled(selector, steps)` —— 控件置灰时跳过后续 steps 步（如 Domain 仅 FTTR_MAIN/FTTR_SUB/COMMON/SFU/AP_COMMON 五类局方可编辑）
- `real.skip_if_option_absent(selector, option_text, steps)` —— 下拉无该选项时跳过后续 steps 步（如机型不支持 11ax 制式）
  ⚠️ 必须放在 `select_option` **之前**：`select_option` 遇选项缺失抛的是超时（判 FAIL），不是 SKIP
- 下拉当前值/开关状态这类读值断言用 `real.evaluate` 自带脚本：`#fhId_X` 的 id 可能挂在组件根 div 上，`assert_input_value` 只对原生 `<input>` 生效。脚本内 `throw new Error(...)` 判 FAIL、`return true` 判 PASS
- 需要跨整页导航/重新登录保存的中间值写 `localStorage`（`window.*` 在整页导航后会丢）

## 报告与截图

每次运行生成 `reports/{时间戳}_{operator}_{env}_{suite}/`：`result.json`（用例/步骤级）、
`report.json`/`report.html`（人读）、`screenshots/*.png`（PASS 按步骤命名，FAIL 前缀标红）。

## 扩展新运营商

1. 复制 `operators/cm/` 为 `operators/{new_op}/`
2. 改 `profile.json`（地址/账号/菜单/页面清单）、`selectors.json`（选择器）
3. 写 `cases/*.json`
4. 运行 `python runner/run_suite.py --operator {new_op} --env real --suite smoke`
5. NL 生成器 `generator/page_index.py` 的 `DEFAULT_UI_ROOTS` 加新运营商源码路径

## 常见故障排查

| 现象 | 原因与处理 |
|---|---|
| fill `#user_name` 超时 | 设备残留会话被重定向；navigate 会自动 logout 重试；确认容器为普通版 |
| `assert_login_error` 失败 | 确认已注册 dialog 监听；错误提示是 alert 弹窗而非页面文本 |
| 菜单 id 找不到 | 真机菜单与源码有差异，先跑 navigation 拿真实 `fhId_*` 菜单树 |
| NEG 用例误判 | 负向用例必须 `"auto_login": false`，否则框架会先自动登录 |
| Mock 端口占用 | 改 `mock_web_ui/server.py` 端口并同步 profile.json |
| INTL 老 UI 登录被填入 `${QCT_INTL_ADMIN_USER}` 字面量 | `run_intl_real_html.py` 的 `_inject` 曾只替换旧 `${INTL_*}` 命名，与用例实际 `${QCT_INTL_*}` 不一致；2026-09-10 已改为 `core.config.resolve_env_value` 通用解析。若复现请检查该函数 |
| `real.click` 报 strict mode violation（多元素命中） | 用例中不要手写"展开下拉"的 click/wait 步骤（如 `.el-select .el-input__inner`），`select_option` 自带展开逻辑；删除冗余步骤即可（INTL-WAN-006 已修复） |
| INTL 真机报告设备型号与实际不符 | `tools/gen_intl_word.py` 的 `DEVICE["model"]` 已按 `--variant` 区分（html=HG6163FC1，new_ui=HG6142HT）；换设备时以状态页 `#fhId_ModelName` 实测为准 |
| 负向校验断言必失败（提示不出现） | 老 UI 的表单校验提示（`.el-form-item__error` 等）在 **blur（失焦）时**才触发，`fill` 后直接断言拿不到；执行器 `fill` 已改为失焦收尾（2026-09-10）。若新用例仍失败，确认断言前有失焦动作 |
| WAN 接口/服务下拉 `select_option` 失败 | 设备未开通 WAN 业务（ONU O1、WAN List 空）时下拉无可选项，属**环境受限**；执行器会抛 `PreconditionBlocked` 判 SKIP，不要改成 FAIL |
| `assert_unauthorized`（接口级 401/403 断言）必失败 | HG6163FC1 数据接口走加密 RPC（FHNCAPIS），前端路由拦截后根本不发请求，被动监听采不到 401/403；接口级鉴权断言在本固件不可行，用例已删除该步，仅保留菜单/路由两级断言 |
| CRUD 用例在真机留下残留数据 | 清理段约定：`desc` 以「清理」开头的步骤起到用例结尾恒会执行（无论成败）；删行用 `real.delete_wan_row`（按行文本）或 `real.delete_row_at`（按行号，支持 `if_count_gt` 行数保护防误删出厂规则）。回归后务必全页面扫残留 |
| ~~已知固件缺陷~~（2026-09-10 已推翻，勿再上报） | ① ~~INTL-SEC-006 未登录直连受保护路由不跳登录~~ → 实为**设备残留活动会话放行**（见下方"会话残留"条），用例已加"登录→正确登出"前置后 PASS；② ~~INTL-FW-034 ACL 必填项为空无校验~~ → 实为**起始/结束 IP 可同时为空属合法行为**，用例已改为正向断言创建成功。当前全量回归 **0 真实缺陷** |
| 未授权类用例（跳登录页/拦截）在真机 FAIL，手动测却正常 | 设备在**存在活动会话期间会对新客户端放行受保护页**（零 cookie 全新上下文照样拿到 sessionid、数据接口 200）。回归时上游 system/其它套件登录后的**服务端会话残留**是主因。修法：用例开头加 `real.login` + `real.logout`（确保服务端会话真正注销，URL 回 login.html）再测拦截。注意 `real.logout` 的 fallback 只跳 login.html、**不注销服务端会话**，依赖会话状态的用例必须走真实登出流程 |
| 跨套件依赖预置数据（如绑定 WAN 的用例） | 绑定 WAN 接口的用例（DDNS APP-116/117、NAT APP-118/119、端口映射 APP-114/115、静态路由 ROUTE-008/009）统一绑定 **INTL-WAN-012 预置的 `INTERNET_R_VID_99`**（VLAN 99 Internet 路由，刻意不删除），以解耦出厂 `INTERNET` WAN 被 wan 套件 CRUD 改动后的连带失败。全量顺序天然满足（wan 在 app_rest/route 之前）；**单独跑下游套件前须先跑 wan 套件**，否则下拉无选项会 `PreconditionBlocked` SKIP |
| 预置/清理类动作重跑失败（VLAN 重复校验拦截） | 保留不删除的预置数据在重跑时必须先清理旧条目。用 `real.delete_wan_row_if_exists`（存在才删 + 内部处理确认框，不存在静默跳过）。**坑**：执行器把动作返回 `False` 判为断言失败，"跳过"分支必须 `return True` |
| 端口隔离用例（原 INTL-FW-012）已删除 | HG6163FC1 老 UI **无端口隔离页面**，该用例每次只能 SKIP。2026-09-11 按维护要求删除：删除 `cases/real/html/port_isolation.json`、从 `core/intl_suite_order.py` 的 `SUITES["firewall"]` 移除该文件、从 `gen_intl_word.py` 页面标题表移除 `port_isolation` 项。若后续机型具备该页面再按需重建 |
| 报告测试项顺序 ≠ 实际执行顺序 | 顺序唯一来源是 `core/intl_suite_order.py`（`SUITES` / `ALL_FILES` / `LOCKOUT_IDS`），**runner 与 tools/gen_intl_word.py 同源引用**。2026-09-11 前两处各写一份（执行器=副作用隔离序、报告=sorted(glob) 文件名字典序），导致 66 个页面中 65 个位置错位。**改执行顺序只改这一个模块**，报告顺序自动跟随；新增/删除用例文件时必须同步登记该模块，否则新页面会退化为按字典序排到最后 |
| 页面用例改了设备配置却没还原 | 会点 Apply 的用例必须自带「清理：」段还原：开局 `real.evaluate` 把原值存进 `localStorage`，末尾按原值回填并重新 Apply（或开关幂等回位）。参考 `wifi_basic.json` 的 INTL-WIFI-035/038/040/041/044/048/051。不改配置的观测型用例用 `#fhId_onDelete`（实为 Cancel，丢弃未保存修改）收尾即可。清理段失败会把用例判 FAIL——这是故意的，防残留静默 |
| wifiBasic 用例集已从 3 条扩到 22 条 | `cases/real/html/wifi_basic.json` = 既有 3 条（001/002/013）+ 新增 19 条（`INTL-WIFI-033`~`051`，对应 `web_v3/docs/测试用例-wifiBasic-通用版.md` 的 GEN-001~022，ID 对照见该文档附录 C）。**2026-09-16 落成时测试机不在本机网段（本机在 192.168.88.0/24），尚未真机验证**；首次接入设备后重点核对这四个来源静态分析的锚点：`#fhId_RegulatoryDomain`、全制式文案 `802.11 b/g/n`、校验文案 `Please select an option.`、`#fhId_onDelete`（Cancel） |
