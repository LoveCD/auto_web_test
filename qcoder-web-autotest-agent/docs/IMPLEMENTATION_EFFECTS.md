# 实现效果（Implementation Effects）

本文档汇总 QCoder Web AutoTest Agent 重构后的实现效果与实测数据。

## 1. 能力总览

| 能力 | 状态 | 说明 |
|---|---|---|
| 运营商区分 | ✅ | `--operator cm / intl`，配置/选择器/用例完全隔离 |
| 真机 UI 测试 | ✅ | Playwright 驱动，登录→菜单导航→页面断言→截图全链路 |
| 全页面遍历截图 | ✅ | navigation 套件自动展开 L1→L2→L3 菜单逐页截图 |
| Mock 离线测试 | ✅ | `--env mock`，无设备环境可用（CI 友好） |
| NL 自动生成用例 | ✅ | 一句中文需求 → 可执行用例 JSON + 需求差距报告 |
| 需求差距检测 | ✅ | 对照 UI 源码发现"需求 vs 实现"差距（如 320MHz 未实现） |

## 2. UI 源码索引能力（generator/page_index.py）

对真实 UI 源码（Vue SPA）静态扫描，**无需设备**：

| 运营商 | 扫描页面 | 索引页面 | 索引元素 | 路由映射 |
|---|---|---|---|---|
| CM（中国移动） | 139 | 89 | 690 | 83 |
| INTL（国际） | 139 | 130 | 1055 | — |

索引内容示例（CM `wifiAdvanced_5g` 页）：

```
OperatingChannelBandwidth  select  label=信道宽度管理
  options=['20MHz','40MHz','20MHz/40MHz/80MHz','80MHz',
           '20MHz/40MHz/80MHz/160MHz','160MHz']   ← 无 320MHz
```

索引还能提取数值校验规则（如 `vlanBind` 页用户侧 VLAN 的 `min:1, max:4094`），
为后续边界值用例生成提供依据。

## 3. NL 用例生成实测

### 例句 1："测试wan连接页面vlan绑定功能"

```
tokens: ['wan', 'vlan', '连接', '绑定']
→ 匹配页面: vlanBind（路由 /network/bindSettings/vlanBind，标题"VLAN绑定"）
→ 生成用例: TC-CM-GEN-001（7 步）
   login → navigate_spa → assert_page → screenshot
   → assert_element #fhId_userVlan → assert_element #fhId_selectWan → screenshot
→ 需求差距: 无
```

### 例句 2："测试wifi基础设置功能支持320MHZ频段设置"

```
tokens: ['wifi', '320mhz', '基础', '频段']  numbers: [320mhz]
→ 匹配页面: wifiBasic（"基础"→basic 驼峰词段匹配）
→ 跨页定位: "频段"功能元素实际在 wifiAdvanced / wifiAdvanced_5g
→ 生成用例: 3 条
   TC-CM-GEN-001  wifiBasic                    （5 步，主页面加载+截图）
   TC-CM-GEN-002  wifiAdvanced    信道宽度管理   （7 步，含 gap 断言）
   TC-CM-GEN-003  wifiAdvanced_5g 信道宽度管理   （7 步，含 gap 断言）
→ ⚠ 需求差距: 320MHz 在 2.4G/5G 信道宽度选项中均不存在（最大 160MHz）
```

**差距检测的价值**：需求"支持 320MHz 频段"在当前 UI 源码中未实现。
生成器不猜测、不静默通过——它生成 `assert_option_present(320MHz)` 用例，
真机执行必然失败，从而**把需求差距变成可执行、可追踪的失败用例**。
INTL 版同样检出（`wifiBasic_5g` 选项最大 `20/40/80/160 MHz`）。

生成器还做了单位域过滤：`wpsSettings` 的"频宽"（2.4G/5G 选择）不会被误报为
320MHz 差距，只有真正的 MHz 型选项选择器才参与差距检测。

## 4. Mock 链路实测（无设备环境）

| 套件 | 命令 | 结果 |
|---|---|---|
| INTL smoke | `--operator intl --env mock --suite smoke` | 7/7 通过 |
| CM mock_smoke | `--operator cm --env mock --suite mock_smoke` | 4/4 通过 |

Mock 与 real 共用同一 StepRunner，用例格式统一，CI 无设备环境可跑完整冒烟。

## 5. 真机实测记录（重构调试期间）

真机环境：烽火 HG3142F2（FTTR-Wi-Fi6 XG-PON 智能终端，`192.168.1.1`）

| 套件 | 结果 |
|---|---|
| CM smoke（11 条） | 11/11 通过（含登录、设备信息、WiFi、防火墙、固件升级、重启页、退出） |
| CM regression（8 条） | 8/8 通过（186s，含负向登录、角色登录、菜单导航、WiFi 页、URL 过滤、DMZ、恢复出厂、SSID 一致性） |
| navigation（98 个 L3 菜单） | 98/98 通过（809.5s，全 L3 菜单遍历截图，DOM 实时发现 L1→L2→L3，非静态清单） |

### 5.0 navigation 渲染断言修复（重要）

**现象**：首轮 navigation 98 页 67 pass / 31 fail，错误统一为 `el_main has no rendered fhId_* elements`。

**根因**：部分页面（帮助/状态/固件升级等）正常渲染但内容不含 `fhId_*` 元素，
以 `fhCount > 0` 断言过严导致误判。诊断脚本实测失败页面 textLen 31~297、url 均正确。

**修复**（`runner/run_suite.py` navigation 流程）：断言对齐 regression `assert_page` 标准——
`#el_main` 可见且 textLen≥5 或 htmlLen≥200；step detail 记录 url 与渲染统计。

### 5.1 负向登录修复（关键）

**根因**：CM 真机登录失败（密码错误）走 `alert("用户名或密码错误，请重试")` 浏览器弹窗，
`#login_error_hint` 节点为静态隐藏文本（`display:none`），从不显示。
此前断言页面文本/元素必然失败。

**修复**（`keywords/real_keywords.py`）：
- `start()` 注册 `page.on("dialog")` 监听，自动捕获并 dismiss 弹窗（避免阻塞）
- `assert_login_error()` 优先检查捕获的 dialog 消息（"用户名或密码错误/错误/不能为空"等），兜底检查 body 文本
- 负向用例需 `"auto_login": false` 禁用框架自动登录（`run_suite.py` 支持）

**验证**：`dialogs captured: [{"type": "alert", "message": "用户名或密码错误，请重试"}]` → 断言通过。

### 5.2 登录容器显示修复

设备 JS 以 `style.display == ""`（空字符串）表示容器"显示"（`onkeydown` 回车判断等）。
此前 navigate 强制 `display='block'` 会破坏 JS 判断，已改为置空字符串。

调试期间解决的关键真机问题（已沉淀到 keywords）：

- CM/AP 双登录容器自适应（`#user_name` / `#loginpp`）
- SPA 直接改 hash 部分页面不渲染 → 智能菜单点击导航 + 加载等待
- `setItemId('x')` 运行时生成 `fhId_x` 的 id 映射规则
- 页面渲染断言改为 `#el_main` 可见 + 内容长度（组件 id 与 component 名不一致）
- 退出登录后 SPA 不跳 `login.html` → 改为断言登录页元素出现
- 登录失败错误提示 = alert 弹窗 → dialog 监听捕获（见 5.1）
- NL 生成套件兼容：`load_suite` 支持 list/dict 两种格式，生成器输出统一 dict

> 真机环境后续恢复时，配置已在 `operators/cm/profile.json` 保留，
> 直接 `python runner/run_suite.py --operator cm --env real --suite smoke` 即可复测。

### 5.3 Skill 封装（双端适配）

已封装为 **qcoder-web-autotest** 技能：

| 平台 | 位置 | 格式 |
|---|---|---|
| WorkBuddy | `.workbuddy/skills/qcoder-web-autotest/`（项目内 + workspace 根） | SKILL.md（project-level） |
| QCoder | `skill_dist/qcoder-web-autotest.zip` | SkillHub zip（SKILL.md + README.md + _meta.json） |

内容：命令速查、真机账号、双登录容器/setItemId/dialog 等关键机制、NL 生成器用法、
用例规范（real.* 动作表）、扩展指南、故障排查表。详见 `docs/USAGE.md` 第 0 章。

## 6. 截图输出

- 每个运行目录 `reports/{run_id}_{operator}_{env}_{suite}/screenshots/`
- PASS 截图按步骤命名（`gen_wifiAdvanced_5g_01_loaded.png` 等）
- FAIL 截图带 `FAIL_TC-*` 前缀，失败瞬间自动抓取，便于定位
- navigation 套件输出全部 L3 菜单页面截图（全页面 UI 覆盖证据）

## 7. 扩展性

- **新运营商**：复制 `operators/cm/` 改配置即可，命令行 `--operator {new}` 区分
- **新页面用例**：NL 生成器直接覆盖（源码索引自动跟进 UI 版本，`--refresh` 更新）
- **新动作关键字**：`RealWebSession` 加方法 + StepRunner 自动分发（`real.*`）

## 8. 双技能集成（web-playwright-e2e-bootstrap）

引入 **web-playwright-e2e-bootstrap**（Node/Playwright 辅助基线技能）作为 Python 主链路的互补：

| 平台 | 交付物 | 验证结果 |
|---|---|---|
| WorkBuddy | `.workbuddy/skills/web-playwright-e2e-bootstrap/`（项目内 + workspace 根） | 集成验证通过 |
| QCoder | `skill_dist/web-playwright-e2e-bootstrap.zip` | 6 文件 SkillHub 兼容包 |
| 工程内副本 | `e2e_bootstrap/`（独立 npm 工程，可直接 clone 运行） | 见下方验证 |

**验证闭环**（`e2e_bootstrap/` 内）：`npm install`（26s）→ 三字段极简输入 `TEST_CASE_SPEC.md`
（测试类型/测试网址/测试内容）→ `npm run test:generate` 生成 `tests/generated/*.spec.js` 骨架
（默认 `describe.skip` 安全增量）→ `npm test` 5/5 通过 → `self-test-report-reporter.js`
按 `case-plan.js` 排序生成 DOCX 报告（7 media / 9 drawings / 6 image rels，`[[E2E_CASE_SCREEN_n]]`
标记渲染时替换为嵌入截图，`{{用例名}}` 块克隆生成 3+ 测试项）。

> 模板自带 `roaming-settings.spec.js` 与生成骨架的 case-plan 冲突，已移至 `tests_examples/`
> 作为参考示例（testDir 之外，不参与运行）。

## 9. GitHub 共享化（脱敏 + 可克隆即用）

为支持上传 GitHub 共享，完成以下改造（敏感信息零残留于仓库）：

### 9.1 `.env` 注入机制

- 新增 `core/config.py`：`load_dotenv()` + `${VAR}` / `${VAR:-default}` 占位符递归解析
- `operators/cm/profile.json` 真机地址/账号改为占位符；`operators/*/profile.json` 移除 `ui_source` 绝对路径
  → 改由 `QCT_UI_SOURCE_CM_DIR` / `QCT_UI_SOURCE_INTL_DIR` 环境变量注入
- `.env`（本地真实值，gitignore 排除）与 `.env.example`（公开模板）分离
- `tools/gen_word_report.py` 不再硬编码账号，从 cm profile 经 `.env` 解析读取
- 脱敏后链路回归：mock 链路、NL 生成器（`generator/index_cache/` 缓存离线可用，cm 89 页 / 690 元素）、
  DOCX 报告生成均验证通过

### 9.2 仓库配套

- `LICENSE`（MIT）、`.gitignore`（排除 `.env`/`reports/`/`*.docx`/`node_modules/`/`__pycache__`/生成用例等，
  例外放行 `skill_dist/*.zip`）、`README.md` GitHub 化重写
- `.github/workflows/ci.yml`：Python（mock 套件 + NL 生成器）+ Node（e2e_bootstrap 基线）双 job 离线 CI
- `docs/USAGE.md` 新增 `.env` 配置说明与 e2e_bootstrap 章节

### 9.3 双技能最终产物

```
skill_dist/
├── qcoder-web-autotest.zip            # Python 主链路（SKILL.md 已含 .env/脱敏说明）
└── web-playwright-e2e-bootstrap.zip   # Node 辅助基线
```

已扫描确认：zip 包无 `__pycache__`、无账号密码/本机路径残留（`192.168.1.1` 为设备出厂默认地址，保留）。
