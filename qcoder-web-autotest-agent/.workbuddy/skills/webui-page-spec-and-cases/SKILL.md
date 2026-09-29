---
name: webui-page-spec-and-cases
description: 从网关 Web UI 页面源码（web_v3/html/src/content/pages/*.js）反向生成「页面级需求文档」与「通用版测试用例」，并可按需转成用例表格。当用户提供某个页面 js 文件，或要求"根据某页面生成需求文档/测试用例/通用用例"时使用。
agent_created: true
---

# 网关 Web 页面 → 需求文档 + 通用版测试用例

把 `web_v3/html/src/content/pages/<page>.js` 这类单页 Vue 组件源码，反向还原为可评审的需求文档，并据此设计不依赖局方定制的通用测试用例。

## 适用对象与路径

- 页面源码目录：`web_v3/html/src/content/pages/`（5G 版为 `<name>_5g.js`）
- 数据节点常量：`web_v3/html/js/xmlnode.js`
- 语言资源：`web_v3/html/lang/<locale>/<module>_res.js`
- 菜单/路由注册：`web_v3/html/src/menu/menudata.js`
- 老 UI 自动化用例：`auto_web_test_repo/qcoder-web-autotest-agent/operators/intl/cases/real/html/<page>.json`
- 输出目录：`web_v3/docs/`
  - 需求文档：`需求文档-<page>-<中文页名>.md`
  - 通用用例：`测试用例-<page>-通用版.md`

## 分析清单（逐项扫源码，缺一不可）

1. **入口与依赖**：`define(["vue", ...])` 的依赖；语言资源路径；页面 `created` 的初始化动作（loading + getData）
2. **路由与菜单**：在 `menudata.js` 中 grep 页面名，确认 `path` 与 `component`；**注意局方分支可能把同名菜单挂到别的页面**（例：TH_AIS 下 `wifiBasic` 挂的是 `wifiAdvanced`）
3. **字段清单**：从 template 里逐项提取 → 控件类型、`:label`、`:id="setItemId('X')"`、`v-model`、`prop`、`:disabled`、`v-if` 条件、`el-option` 取值
4. **`setItemId` 规则**：`setItemId('X')` 生成 DOM id **`fhId_X`**（自动化选择器锚点）；注意 id 语义可能误导（例：Cancel 按钮 id 是 `fhId_onDelete`）
5. **校验规则**：`checkData` 中的 `required`/`type`/`min`/`max`/`trigger`（**trigger 为 change/blur，不是实时**）；以及 `onApply` 内的附加判断与弹窗文案
6. **联动规则**：`watch` 里每个 handler 逐条读（强制赋值、选项集切换、重新拉取、非法值回退）
7. **保存分支**：`onApply` → `onSubmit*` 的分支条件（只读态只下发某字段、按索引分支、常规批量），以及**派生字段**（例：无 `AutoChannelEnable` 控件，由 `Channel` 派生）
8. **接口契约**：`$post` / `$multipost` 的方法名与字段清单；读接口、写接口、日志审计接口分别列出
9. **局方差异**：全文 grep `operator_name`，把每个局方的差异化需求（可见区块、禁用态、默认值、下发字段）整理成矩阵
10. **已知坑**：命名误导 id、共用 id（同页多区块复用同一 id，需可见性判断避免 strict mode 冲突）、只读态改变保存语义、下拉无可选项导致不可提交（应 SKIP 而非 FAIL）

## 需求文档结构（固定）

0 文档信息表 → 1 功能概述与能力边界 → 2 入口与前置条件（含禁用/只读表）→ 3 字段需求表（含元素 ID、数据节点、取值域、默认、校验、显示条件）→ 4 交互与联动规则（编号 R1..Rn）→ 5 保存逻辑（分支 + 下发字段）→ 6 数据接口需求（读写表 + 节点前缀 + 白名单提醒）→ 7 元素 ID 清单 → 8 局方差异矩阵 → 9 与对偶页（2.4G/5G）差异 → 10 约束边界与已知问题 → 11 验收标准（已有用例对照 + 建议补充）→ 附表（枚举清单、节点清单）

## 通用版测试用例要求

- **通用 = 不依赖任何局方定制分支**；涉及机型能力的用例写成"条件前置"，不满足时 SKIP
- 局方专属内容单独放「附录 B：非通用用例」，不混进基线集
- 用例字段：编号 / 优先级 / 类型 / 需求追溯（对应需求文档章节号）/ 前置条件 / 测试步骤 / 预期结果 / 备注
- 编号约定：`TC-<页名缩写>-GEN-NNN`
- 覆盖维度：页面可访问与初始态、每个必填字段的保存与回读、多级联动（字段 A 变化 → 字段 B 被强制/选项集变化）、非法值回退、必填校验拦截、按钮语义（Apply/Cancel）、幂等、持久化（刷新/重登/重启）、安全（未登录拦截，**前提是服务端会话已注销**）
- 优先级：P0 核心链路保存与回读；P1 联动与校验；P2 边界与观察项
- 开头必写「编写与执行注意事项」，把源码坑点（校验时机、误导 id、派生字段、无选项 SKIP、只读态语义）前置告知执行者

## 真机执行约定（若需落地为自动化用例）

```bash
cd auto_web_test_repo/qcoder-web-autotest-agent
/Users/zzmima6ge0/.workbuddy/binaries/python/envs/default/bin/python runner/run_intl_real_html.py --suite <suite> --ui html [--cases <ID>]
```
- 执行需 `dangerouslyDisableSandbox: true` 才能直连设备
- **登录态复用（落地用例时必守）**：用例首步统一写 `{"action": "real.ensure_login", "desc": "确保已登录（会话复用：整个 run 只登录一次；会话失效自动重登）"}`，**不要**在每条用例里重复「访问登录页 → 填用户名 → 填密码 → 点登录」四步——执行器 run 开始登录一次并存 `_session_state.json`，以 `ensure_login`/`open_page` 开头的用例注入该会话。已生成的旧用例可用 `python tools/apply_single_login.py <用例.json>` 一键收敛（幂等）
  - 批量收敛前**必须先 `--dry-run` 复核**。工具的安全护栏只认「纯前置条件」型登录块：①动作/选择器序列一致；②两个 fill 取值**严格等于** `${QCT_INTL_ADMIN_USER}` / `${QCT_INTL_ADMIN_PASS}`；③尾部不含 `assert_login_error`/`assert_login_stays`/`.login_error_hint`；另外 `login.json`、`security.json` 整文件默认跳过（收敛后执行器会给它们注入会话，「未登录态/锁定态」断言就失效了，需 `--force-files` 才处理）
  - 反例（这些**不能**收敛，登录/输入本身就是被测点）：`INTL-LOGIN-002`（错误密码，值为 `WrongPass123`）、`INTL-LOGIN-003`（空用户名/密码）、`INTL-SEC-002`（锁定期间无法登录）、`INTL-STATUS-004`（登录框 XSS 注入，值为 `<img src=x onerror=alert(1)>`）
- 例外：登录流程本身、错误密码、未登录拦截（首步是 `navigate` 或首步后立即 `logout`）的用例保持原样——它们的登录/登出就是被测点，执行器也不会给它们注入会话
- **填值后必须触发 blur/change**，否则旧 UI 校验不触发。**执行器的 `fill` 只做 `locator.fill()`，不含 blur**（2026-09-16 核对源码），所以断言校验提示前必须另有一步真实点击（点 Apply 或点别处）来施焦——否则读到的是**上一条取值的陈旧提示**，会得到"看起来一致但完全错位"的结论
- 选择器统一 `#fhId_<name>`；多区块共用 id 时需加可见性过滤
- **`setItemId` 落点决定断言方式**（2026-09-16 真机实测）：
  - el-switch / el-checkbox → id 在**不可见**内层 input，断言用容器 `.el-switch` 的 `is-checked`
  - **el-select 被 `:disabled` 时只给内层 input 加 `disabled` 属性，容器 `.el-select` 不带 `is-disabled`** → 断言"下拉已禁用"用 `input.disabled`，勿查容器类名
- **多规则字段存在短路，测试值要避开先命中的规则**：如密钥框规则为「`length<8||>63` → 长度提示；否则 `isCnInclude` → 中文提示」，若"含中文"的测试值只有 7 字符，永远只看到长度提示、nocn 分支不可达 → 这类测试值必须同时满足其它规则的通过条件（中文密钥用 ≥8 字符，如 `中文密钥1234`）
- 断言文案要取 **i18n 原文**（含结尾标点），从 `web_v3/html/lang/en/*.js` 的 key 反查（如 `enter_noch_char` = `"Please do not enter Chinese character."`），不要按印象拼写
- 涉及会话状态的用例（未登录拦截类）必须先"登录→正确登出"清理服务端会话

## 反模式（不要做）

- 不要照搬源码变量名当需求描述（要转成业务语言，如 `mruEnable` → "MRU 使能"）
- 不要把局方分支混进通用用例，也不要把通用结论写成"仅某局方适用"
- 不要在无源码依据时臆造校验规则与默认值；不确定的写进 Notes 并标注"以设备实测为准"
- 需求文档与用例集必须互相可追溯（用例里带需求章节号）
