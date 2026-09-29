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
- `real.click_checkbox(selector, [on], [state_from], [field])` —— 同上的 el-checkbox 版本；`state_from`/`field` 从快照记录值取目标态（清理步骤用）
- `real.skip_if_disabled(selector, steps)` —— 控件置灰时跳过后续 steps 步（如 Domain 仅 FTTR_MAIN/FTTR_SUB/COMMON/SFU/AP_COMMON 五类局方可编辑）
- `real.skip_if_option_absent(selector, option_text, steps)` —— 下拉无该选项时跳过后续 steps 步（如机型不支持 11ax 制式）
  ⚠️ 必须放在 `select_option` **之前**：`select_option` 遇选项缺失抛的是超时（判 FAIL），不是 SKIP
- ⚠️ **读值/回读断言一律用声明式动作，不要写 `real.evaluate` 自带脚本**（见下节）。
  背景：`#fhId_X` 的 id 常挂在组件根 div 上、内层真实 input 被隐藏，`assert_input_value`
  只对原生 `<input>` 生效——这类场景执行器已备好对应动作：勾选态
  `assert_checkbox_checked`、开关 `assert_switch`、下拉 `assert_option_set` /
  `select_option_first` / `select_option_dynamic`、字段 `assert_field_*`。
- ⚠️ **`click_menu` 必须一次给完整三级路径 `l1`+`l2`+`l3`**（仓库 271 处范式，别拆开写）。
  执行器的等待是**逐级内建**的：点 l1 → `_wait_visible(l2,3000)` → 点 l2 → `_wait_visible(l3,3000)`
  → 点 l3 → `_wait_page_loaded(8000)`。
  若拆成「`click_menu(l1,l2)` → `wait` → `click_menu(l3)`」，第二次只给 l3 会**跳过前两级等待**，
  退化成固定盲等；菜单未展开时点击落空，但 `click_menu` 仍报 PASS，随后断言找不到元素而超时。
  先例：`INTL-LAN-015` step14 曾是全仓库**唯一**「只给 l3」的写法，导致该用例 9/18 与 9/22
  两次全量跑间歇 FAIL（且都是第 14 步中断，前 13 步完全相同）、9/18 另两次全量却 PASS。
  2026-09-22 已补齐为完整路径（步数不变）。
  `real.evaluate` 只作「确实没有对应动作」时的最后手段。
- 需要跨整页导航/重新登录保存的中间值：优先用 `real.snapshot`（见下节）——
  它同时写**执行器内存**（给声明式断言用）与 **`window['__<name>']` + `localStorage`**
  （与改造前内联脚本同形，给 `select_option_dynamic` / `click_checkbox(state_from=)` 读）。
  ⚠️ 这两条消费路径是**既有实现，不要改动**：记录侧必须继续往 localStorage 写一份。

### 声明式动作：原值快照 / 回读校验（2026-09-22）

「记住设备原值 → 改配置 → 回读一致 → 恢复原值」**不要写内联 `real.evaluate` 脚本**
（旧用例有 140 段用 localStorage 手工维护快照：刷新即丢、每个字段一段重复代码）。
改用执行器持有的快照，用例侧只声明意图：

- `real.snapshot(name, fields, [bools], [lengths])` —— 记录一组 `{别名: 选择器}` 当前值。
  ⚠️ **读取方式由执行器 `FIELD_KINDS` 按别名定**（`adv`=勾选态、`keylen`=只记长度 →
  密钥明文不进快照与日志），**用例里不要再写 `bools`/`lengths`**；显式传仍生效（取并集）。
  表按**别名**而非选择器定：`#fhId_PreSharedKey` 在 `key`（文本）与 `keylen`（长度）下不同。
- `real.assert_unchanged(name,[fields],[timeout_ms])` / `real.assert_changed(...)` ——
  断言与快照一致 / 已变化。`fields` 省略=全量比对，给子集=只校验该子集（别把「单字段恢复」
  悄悄放大成「整组没变」）；`timeout_ms>0` 轮询等待，替代用例里 24×500ms 的 Promise 轮询。
- `real.assert_snapshot_diff(a, b, [fields])` —— 两快照间至少一项不同（切换重填生效）。
- `real.assert_field_value_wait(selector, value, [timeout_ms])` —— 轮询等某字段变成固定值。
- `real.assert_checkbox_checked(selector, on, [timeout_ms], [poll_ms])` —— 断言勾选态。
  `timeout_ms=0`（默认）读一次即断言；`timeout_ms>0` 轮询等到命中即返回。
  用于「重进页面后回读设备参数」：勾选态是异步到位的、元素也可能尚未挂载，
  替代用例里 24×500ms 的 Promise 轮询（INTL-WIFI-080 即此改造）。
- 2026-09-22 16:0x 为「wifi 内联脚本清零」补的 7 个通用动作（都是既有动作的**缺口补位**，
  全部复用 `_is_disabled` / `_blur_active_input` / `_CLICK_JS` / `_wait_until`，不是另造一套）：
  - `real.assert_field_length(selector, length, [timeout_ms], [poll_ms])` —— 断言字段**长度**。
    密钥类字段**必须**用它：`assert_field_matches` 会把实际值写进失败信息 → 明文进报告。
  - `real.assert_field_not_matches(selector, pattern)` —— 断言**不**匹配正则（`assert_field_matches` 的镜像）。
    例：密钥用例前置 `pattern="^(None|.*Enterprise.*)$"` 表达「当前为个人模式」。
  - `real.assert_field_in_options(selector)` —— 断言字段当前值**属于它自己的选项集**。
    期望集运行期才知道（换频宽/监管域后信道列表刷新），静态 `contains` 表达不了。
  - `real.assert_field_value_if_option(selector, option_text, if_present, if_absent)` ——
    取值随「下拉是否含某选项」而不同（信道 36 在新列表则保留、否则回退 Auto Selected）。
  - `real.assert_option_set_cond(selector, by_selector, cases)` —— 期望选项集**取决于另一字段取值**。
    `cases=[{"pattern": "(?i)(ax|be)", "contains": [...]}, {"contains": [...]}]`：
    第一条 `pattern` 命中 `by_selector` 当前值的分支生效，**无 `pattern` 的那条作兜底（必须给）**，
    其余参数同 `assert_option_set`。
  - `real.assert_option_set(..., count=N)` —— 新增参数：选项数量**精确等于** N（`min_count` 只管下限）。
  - `real.probe_disabled(selectors, [label])` —— **只记录**一组控件的可编辑性到日志，**不做断言**。
    用于「行为固化」类步骤（老用例写 `window.__closeState`，报告里根本看不到，等于白记）。
  - `real.clear_select(selector)` —— 把 el-select 置为「未选择」态并触发 change（构造必填校验场景）。
    直接改 `input.value` 不会让 ElementUI 重新校验，必须打组件事件。
  - 内部另抽出 `_read_option_items(selector)`（展开下拉 → 读可见选项 → 收起面板），
    由 `assert_option_set` / `assert_field_in_options` / `assert_field_value_if_option` /
    `assert_option_set_cond` 共用——老用例每处都要重抄一遍展开逻辑。
- `real.restore(name, [fields])` —— 恢复为记录值（值相同则跳过；禁用态与长度类字段跳过）。
- `real.assert_radio_one_of(labels, [selector])` —— 断言一组 `.el-radio` 文案中**恰好选中一个**。
  ⚠️ 射频 Enable/Disable 类场景**别写死 `assert_radio_checked('Enable', true)`**：该选哪一项
  取决于设备当前配置（该 SSID 射频是否打开），2.4G 首项是 Enable、5G 首项是 Disable，
  写死会随设备时对时错（2026-09-22 真机 096 FAIL 即此因）。
- `real.assert_radio_checked([selector], label, checked)` —— 按**显示文案**定位单个 `.el-radio`。
- 📌 **找不到 `id` 的单选组一律用文案定位，别写结构 CSS**。以上两个动作内部就是
  `querySelectorAll('.el-radio')` + `innerText` 精确匹配（+ 过滤不可见），**本质已是一张"文案→元素"映射**，
  无需再另建选择器表。先例：`INTL-WIFI-004` step9 原为
  `div.el-form-item:has-text("WPA Algorithms") .el-radio-group`（**全仓库唯一的结构 CSS**），
  2026-09-22 改成 `assert_radio_one_of labels=["AES","TKIPAES"]` → 全仓库结构 CSS 归零。
  ⚠️ **`labels` 必须写"显示文案"**：WPA Algorithms 的底层 `input[value]` 是 `TKIPandAES`，
  而 `.el-radio__label` 显示的是 **`TKIPAES`** —— 文案定位读的是 `innerText`，写 `TKIPandAES` 会找不到。
  ⚠️ **控件 disabled 不影响判定**：`.el-radio` 仍可见（`getBoundingClientRect().width > 0`）即可
  （实测该组正是 `is-disabled` 状态，AES 带 `is-checked`，`assert_radio_one_of` 通过）。
  ⚠️ 别用 `:has-text("...")` 做结构定位：它是**子串 + 大小写不敏感**匹配，容易误命中。
- `real.select_option_first(selector)` —— 选下拉首个可见项（选项文案随设备配置变化的场景，
  别写死 `select_option(sel, "1")`，设备上没该项时直接超时判 FAIL）。
- 快照日志对 `#fhId_PreSharedKey` 等密钥选择器打 `***`。
- ⚠️ **记录侧的存储介质不要改**：`snapshot` 除写执行器内存外，还必须按原样补写
  `window['__<name>'] = o` 与 `localStorage.setItem(<name>, JSON.stringify(o))`，
  其中 `o` 是「别名 → 纯值」字典（不含内部 selector/kind）。漏写这一份，
  `select_option_dynamic`（读 `o[field]`）与 `click_checkbox(state_from=)` 会抛
  「记录值 X.Y 缺失，无法恢复」——2026-09-22 改造时只写内存，9 条用例（076/098 的 `sel`，
  080/102/091/113 的 `adv`，064/065/071 的 `ch`/`gi`）全断链。消费侧一个字都不用动。

⚠️ 2026-09-22 曾做过一轮「动作合并 + 等待参数化」（`set_checked` / `delete_row` / 参数化断言 /
`_poll_until` / 表意别名），**当日整体回退**。动作名以本文件为准，别在执行器里再引入那套名字。
（注意区分：`assert_checkbox_checked` / `_wait_until` 的 `timeout_ms`/`poll_ms` 参数，以及 16:0x
为「wifi 内联脚本清零」补的 7 个动作 + `assert_option_set(count=)`，都是**按需补缺口**，
不是那套合并方案的残留——那套名字（`set_checked`/`delete_row`/`_poll_until`/表意别名）仍一个都不许出现。）

### `run_intl_real_html.py` 第二批新增动作（2026-09-22 17:2x，html 内联清零）

- `real.assert_field_nonempty(selector, [optional])` / `real.assert_field_matches(selector, pattern, [optional])` /
  `real.assert_field_not_matches(selector, pattern, [optional])` —— 新增 **`optional`** 参数：
  字段**未渲染**时视为通过。底层是 `_need_field(selector, optional=True)` 返回 `None`。
  老用例写成 `!el || (...)` 的「该字段按设备形态可能没有」一律用它，别再写内联脚本。
- `real.assert_html_not_contains(selector, texts)` —— 断言元素**源码 innerHTML** 不含给定子串。
  ⚠️ 和 `assert_text_not_contains` 不是一回事：后者读渲染后的 `inner_text`，payload 真被解析成
  `<img onerror=...>` 元素时它的属性**根本不进 inner_text**，断言会「假通过」。安全类用例必须用本动作。
- `real.assert_field_plain_text(selector, [contains], [tag])` —— 断言字段以**文本**呈现、未被解析成元素。
  `tag='img'` 只查该标签子元素数；省略 `tag` 则要求字段内**没有任何**元素子节点（更严格）。
  `contains` 可再断言可见文本含该片段（转义成功后原文仍读得到）。
- `real.assert_element_count(selector, [equals], [gt], [min])` —— 断言匹配元素个数（典型：表格行数）。
  用于「列表条数相对出厂基线增减」——基线值运行期才知道，静态文本断言表达不了。
- `real.inject_vue_data(key, value, [root="#app"], [max_depth=8])` —— **激励动作**（非断言）：
  从 `root.__vue__` 深度优先找 `_data`/`$data` 含 `key` 的组件并赋值，模拟「设备上报里带恶意串」。
  找不到持有者直接失败（页面结构变了就该暴露，不能静默放过）。

### 虚拟选择器别名表 `SELECTOR_ALIASES`（2026-09-22，sunstar 要求）

**问题**：有些控件在 DOM 里**根本没有 id**，用例侧只能退化成写业务文案或结构 CSS，与其它步骤形态不一致。
典型是 Wi-Fi 高级页的 **WPA Algorithms 单选组**——2026-09-22 真机只读探测确认：
`.el-radio-group` / `.el-form-item` / `input[type=radio]` / `.el-radio__inner` **全都没有 id**
（`groupId`、`formItemId`、`input.id`、`box.id` 一律 null/空串），连它的 value 也和显示文案不同
（显示 `TKIPAES`，`input.value` 是 `TKIPandAES`）。改造前的原始 JS 就是靠 `innerText` 文案匹配的。

**做法**：用例侧统一写成 `#fhId_xxx` 形态（与真实 id 控件观感一致），由执行器集中映射：

```python
# runner/run_intl_real_html.py（与 FIELD_KINDS / FIELD_FORMATS 同族：实现细节收在执行器）
SELECTOR_ALIASES = {
    "#fhId_WPAAlgorithms": {
        "selector": 'div.el-form-item:has-text("WPA Algorithms") .el-radio-group',
        "options": ["AES", "TKIPAES"],   # 该组候选文案（el-radio 的**显示值**）
    },
}
```

用例侧因此回到统一形态，且不必再出现候选文案：

```json
{"action": "real.assert_radio_one_of", "selector": "#fhId_WPAAlgorithms", "desc": "…"}
```

- ⚠️ **表里的键不是 DOM 中的真实 id**：拿去浏览器 `querySelector` 查不到，必须经 `resolve_sel()` 解析。
  加表项时务必在注释里写明"DOM 无 id"的**探测依据**（免得后人误当真 id 用）。
- 解析优先级（`resolve_sel`）：虚拟别名 → 已是 CSS 形态（`#`/`.`/`[`/`:` 开头）→ 语义 key（`selectors_real*.json`）。
- 🚨 **别名解析出来的值必须能被"消费它的引擎"认识**：`selector` 里如果用 `:has-text()`，
  那是 **Playwright 的扩展伪类，浏览器原生 `document.querySelector` 不认** —— 传进 `page.evaluate`
  直接抛 `SyntaxError: ... is not a valid selector`（首版就栽在这：`assert_radio_*` 原本用
  `page.evaluate` + `document.querySelector` 解析作用域，别名一进 → 3 条用例全 FAIL）。
  → 已把 radio 族改为 `self._radio_scope(sel).evaluate(...)`（Playwright Locator；JS 首参即该元素，
  写成 `(el, a) => { const scope = el; ... }`），并新增 `_radio_scope()` 统一解析作用域
  （省略 selector 时用 `body`，语义等于原 `document`）。
  → **适用边界**：走 `page.locator` 的动作（`click`/`fill`/`assert_visible`/`assert_element_count`…）
  与 radio 族支持 `:has-text`；而 `_need_field`/`read_field`/`assert_absent`/`assert_field_error`/
  `probe_disabled` 走原生 `querySelector`，遇到 `:has-text` 会**明确报错**（不会静默错判）。
  要给这些动作用别名，得先把它迁到 Playwright 路径。
- 覆盖范围：24 处调用 `resolve_sel` 的动作（含 `assert_visible` / `click` / `fill` / `select_option` …），
  外加 `_need_field`（`assert_field_*` 全家）、`read_field`、`_wait_visible`、`assert_absent`、
  `assert_element_count`、`assert_field_error`、`probe_disabled`、以及 `assert_radio_checked` /
  `assert_radio_one_of`（用别名的 `snapshot` 只在记录时解析一次，消费侧读快照里那份）。
- `assert_radio_one_of(labels=None, selector=None)`：`labels` 省略时自动取别名表的 `options`；
  两者都没有会**明确报错**，不会静默放过。
- 启动时 `_validate_selector_aliases()` 自检（键必须是选择器形态、必须给出非空真实选择器）。
- 新增一个别名的步骤：① 只读探测该控件的真实 DOM（确认是否真无 id）；② 加表项（`selector` + 需要的 `options`）；
  ③ 用例改写成别名形态；④ 真机跑该用例确认。
  **反例**：已有真 id 的控件不要建别名（多一层跳转、且名字会与真 id 混淆）。

### 内联脚本改造进度

- **wifi 4 文件已清零**（2026-09-22 16:0x，70 处 → 0）。
- **html 3 文件已清零**（2026-09-22 17:2x，20 处 → 0）：`status.json`（15）、`acl_settings.json`（4）、
  `ntp.json`（1）。本轮 20 处**全部**一一映射到既有/新增动作，**没有一处需要拆成多步**，
  所以 `skip_if_*(steps=N)` 一个都没动（这三个文件里本来也没有 skip_if）。
- 剩余内联脚本：`new_ui/status.json`（3）、`cm/cases/wan_crud.json`（2）—— 这两处跑的是**另外两套
  执行器**（`run_intl_real.py` 37 动作 / `run_suite.py` 另一套 schema），要改得单独起一轮。
- 改造手法照 wifi：能对应既有动作的直接换；没有的加**通用**动作（别造一次性的）；
  ⚠️ 若一步 evaluate 拆成多步，**必须回头核对同用例里的 `skip_if_*(steps=N)`**
  （它按绝对步数跳；wifi 轮 082/104 4→8、044 8→9 就是这么修的）。
- 🔧 改写 JSON 时的省事姿势（2026-09-22 验证，**按该文件实测行尾二选一**）：
  - LF 文件：`json.dumps(data, ensure_ascii=False, indent=2) + "\n"`
  - CRLF 文件：`json.dumps(data, ensure_ascii=False, indent=2).replace("\n", "\r\n") + "\r\n"`
    （⚠️ 只写末尾 `+ "\r\n"` 不够——`json.dumps` 内部的缩进换行全是 `\n`，漏了 `replace` 会整体少 N 字节。）
  两者都与原文件**字节级一致**（已实测），所以可以 `json.load` → 改 → 写回，
  不必手写转义（正则里的 `\d`、payload 里的 `<`/`>` 手写极易出错）。
  ⚠️ 但转换脚本里的映射要**显式列全**并对未命中项 `sys.exit(1)`，别留静默兜底。

### 改动用例/执行器后的备份约定（sunstar 要求，2026-09-22）

一轮改动做完后，把**改前的文件**放进仓库根下的时间戳文件夹：

- 命名：`_backup_<YYYYMMDD_HHMMSS>/`，如 `_backup_20260922_140910/`（时间戳=备份时刻）。
- 内容：本轮被改的文件（例：`runner/run_intl_real_html.py`、`operators/intl/cases/real/html/wifi_advanced{,_5g}.json`）。
- 用 `touch -d "<原 mtime>"` 还原各备份件的原始修改时间，便于日后辨认。
- ⚠️ **必须字节级读写**（`open(p,"rb")` / `open(p,"wb")`）：Python 文本模式（`open(p,"w")`）
  在 Windows 会把 `\n` 写成 `\r\n`，备份即变形（现象：`diff` 整文件全不同）。
  先 `raw.count(b"\r\n")` 判断该文件当前是 CRLF 还是 LF，再决定写回时怎么处理。
- 📌 行尾**逐文件而异，没有统一规律，改前必须实测**（2026-09-22 全目录实测）：
  `operators/intl/cases/real/html/*.json` = 61 个 LF + **4 个 CRLF**（`wifi_basic` / `wifi_basic_5g` /
  `wifi_advanced` / `wifi_advanced_5g`，即 16:0x 那轮改造过的四个）；`new_ui/*.json` = 17 CRLF + 7 LF；
  `runner/*.py` = 3 LF + 2 CRLF（`run_intl_real_html.py` 是 LF）。
  → 早前"json 是 CRLF"与"都是纯 LF"两种说法**都不准确**，别照抄，`raw.count(b"\r\n")` 实测为准。
- ⚠️ **Edit 工具会把 CRLF 归一化成 LF**：改行尾为 CRLF 的文件时，务必改完回查字节；
  但用 Python 脚本改写则不会（脚本按二进制写）。
- 校验：把备份**施加本轮改动**后与现行文件做 **`sha256(字节)`** 比对，一致才算"备份=改前原文"。
  ⚠️ 别用文本模式做哈希校验——它对 CRLF/LF 不敏感，会漏掉换行变形。

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
| CRUD 用例在真机留下残留数据 | 清理段约定：`desc` 以「清理」开头的步骤起到用例结尾恒会执行（无论成败）；删行统一用 `real.delete_wan_row`（按行文本）/ `real.delete_row_at`（按行号，支持 `if_count_gt` 行数保护防误删出厂规则）/ `real.delete_wan_row_if_exists`（存在才删 + 处理确认框）。回归后务必全页面扫残留 |
| ~~已知固件缺陷~~（2026-09-10 已推翻，勿再上报） | ① ~~INTL-SEC-006 未登录直连受保护路由不跳登录~~ → 实为**设备残留活动会话放行**（见下方"会话残留"条），用例已加"登录→正确登出"前置后 PASS；② ~~INTL-FW-034 ACL 必填项为空无校验~~ → 实为**起始/结束 IP 可同时为空属合法行为**，用例已改为正向断言创建成功。当前全量回归 **0 真实缺陷** |
| 未授权类用例（跳登录页/拦截）在真机 FAIL，手动测却正常 | 设备在**存在活动会话期间会对新客户端放行受保护页**（零 cookie 全新上下文照样拿到 sessionid、数据接口 200）。回归时上游 system/其它套件登录后的**服务端会话残留**是主因。修法：用例开头加 `real.login` + `real.logout`（确保服务端会话真正注销，URL 回 login.html）再测拦截。注意 `real.logout` 的 fallback 只跳 login.html、**不注销服务端会话**，依赖会话状态的用例必须走真实登出流程 |
| 跨套件依赖预置数据（如绑定 WAN 的用例） | 绑定 WAN 接口的用例（DDNS APP-116/117、NAT APP-118/119、端口映射 APP-114/115、静态路由 ROUTE-008/009）统一绑定 **INTL-WAN-012 预置的 `INTERNET_R_VID_99`**（VLAN 99 Internet 路由，刻意不删除），以解耦出厂 `INTERNET` WAN 被 wan 套件 CRUD 改动后的连带失败。全量顺序天然满足（wan 在 app_rest/route 之前）；**单独跑下游套件前须先跑 wan 套件**，否则下拉无选项会 `PreconditionBlocked` SKIP |
| 预置/清理类动作重跑失败（VLAN 重复校验拦截） | 保留不删除的预置数据在重跑时必须先清理旧条目。用 `real.delete_wan_row_if_exists`（存在才删 + 内部处理确认框，不存在静默跳过）。
**坑**：执行器把动作返回 `False` 判为断言失败，"跳过"分支必须 `return True` |
| 端口隔离用例（原 INTL-FW-012）已删除 | HG6163FC1 老 UI **无端口隔离页面**，该用例每次只能 SKIP。2026-09-11 按维护要求删除：删除 `cases/real/html/port_isolation.json`、从 `core/intl_suite_order.py` 的 `SUITES["firewall"]` 移除该文件、从 `gen_intl_word.py` 页面标题表移除 `port_isolation` 项。若后续机型具备该页面再按需重建 |
| 报告测试项顺序 ≠ 实际执行顺序 | 顺序唯一来源是 `core/intl_suite_order.py`（`SUITES` / `ALL_FILES` / `LOCKOUT_IDS`），**runner 与 tools/gen_intl_word.py 同源引用**。2026-09-11 前两处各写一份（执行器=副作用隔离序、报告=sorted(glob) 文件名字典序），导致 66 个页面中 65 个位置错位。**改执行顺序只改这一个模块**，报告顺序自动跟随；新增/删除用例文件时必须同步登记该模块，否则新页面会退化为按字典序排到最后 |
| 页面用例改了设备配置却没还原 | 会点 Apply 的用例必须自带「清理：」段还原：开局 `real.snapshot(name, {别名: 选择器})` 记录原值（写入由执行器持有，别再用 `real.evaluate` 手工写 localStorage），末尾按原值回填并重新 Apply（`real.restore(name)`，或开关/复选框 `real.click_checkbox(..., state_from=, field=)` 幂等回位）。参考 `wifi_basic.json` 的 INTL-WIFI-035/038/040/041/044/048/051。不改配置的观测型用例用 `#fhId_onDelete`（实为 Cancel，丢弃未保存修改）收尾即可。清理段失败会把用例判 FAIL——这是故意的，防残留静默 |
| 点 el-switch 开关的用例用 `real.click` 而不是 `real.set_switch` | `click` 是**切换**语义，设备残留状态一变，同一用例就时对时错；`set_switch` 幂等（已是目标态则不动，切换后复读校验）。**真实案例（2026-09-22）**：`band_steering` 的 011/019/020 三条全部栽在「设备上 Band Steering 残留为开启」——用例假设初始为关、点一下就开，结果点成了关，`#fhId_RSSIThreshold(5G)` 隐藏 → 三条齐挂（历史 9/10、9/11、9/18 都 PASS，只因当时设备状态是关）。**开关类前置一律用 `real.set_switch(sel, on=True/False)`**。该 3 条已于 2026-09-22 按此规则修好、真机重跑 3/3 PASS。另：`multi_ap_enable` 的 `#fhId_Enable`/`#fhId_Disable` 是 radio 不是开关，点哪个就是哪个，无此风险 |
| wifiBasic 用例集已从 3 条扩到 22 条 | `cases/real/html/wifi_basic.json` = 既有 3 条（001/002/013）+ 新增 19 条（`INTL-WIFI-033`~`051`，对应 `web_v3/docs/测试用例-wifiBasic-通用版.md` 的 GEN-001~022，ID 对照见该文档附录 C）。**2026-09-16 落成时测试机不在本机网段（本机在 192.168.88.0/24），尚未真机验证**；首次接入设备后重点核对这四个来源静态分析的锚点：`#fhId_RegulatoryDomain`、全制式文案 `802.11 b/g/n`、校验文案 `Please select an option.`、`#fhId_onDelete`（Cancel） |
| 某条用例刚 Apply 保存过配置，**紧随其后**的用例 `open_page` 全挂（`ERR_CONNECTION_ABORTED` / `ERR_NETWORK_CHANGED` / `ERR_CONNECTION_RESET`） | 设备保存配置会**短暂中断 Web 服务/网口**，紧接着的导航被掐断 —— 属设备行为，**不是用例缺陷**。**真实案例（2026-09-23）**：`INTL-LAN-015`（保存 DHCP 租约时长 + 恢复）跑完后，套件同段紧随的 `LAN-012`/`LAN-013` 必挂 step1（1.1s / 6.9s）；而 `--cases INTL-LAN-012,INTL-LAN-013` **不带 015 单跑 → 2/2 PASS**（双向对照坐实）；其间的 `LAN-005`/之后的 `LAN-014` 不受影响。判定法：失败点在**用例第一步**且报错是网络层（而非选择器/元素）→ 先单独重跑该用例确认，**别改用例**。修法方向：给 `open_page`/`navigate` 加"网络层瞬时错误"重试（仅上述几类，不重试元素级超时） |
