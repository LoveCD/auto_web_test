# 四类页面自动化测试范本与可扩展指南

> 适用项目：qcoder-web-autotest-agent（烽火 HG3142F2 FTTR 网关 Web 自动化测试）
> 版本：v1.1（2026-08-20）
> 状态：
> - **mock 套件已验证通过 20/20**（wan_crud_mock 9、lan_info_mock 4、device_mgmt_mock 7）
> - **真机四套件 22/22 全部通过**（wan_crud 7/7、lan_info 4/4、device_mgmt 6/6、security 5/5）

---

## 1. 范本定位

本范本固化**四类页面**的自动化测试模式，同时覆盖**真机（real）与 mock（mock）**两套执行环境，
后续新增页面时按第 6 章「三步接入模板」即可扩展，可持续、可复用。

| # | 页面类别 | 覆盖功能点 | 真机套件 | mock 套件 |
|---|----------|-----------|----------|-----------|
| 1 | 登录页面 | 登录测试（正/负向、会话、登出） | `login.json`（复用） | mock_smoke 登录段 |
| 2 | WAN 连接 | 增删改查 + 边界校验 | `wan_crud.json` | `wan_crud_mock.json` |
| 3 | 设备状态页 | LAN 侧地址（动态主机表） | `lan_info.json` | `lan_info_mock.json` |
| 4 | 设备管理页 | 重启 / 恢复默认 / 恢复出厂 | `device_mgmt.json` | `device_mgmt_mock.json` |
| + | 安全测试 | XSS 三型 + 安全头 + 弱口令 | `security.json` | 依赖真机结果 |

统一覆盖的功能点：**① 规则增删改查；② 边界测试；③ 安全测试（含 XSS，AI 可辅助的环节见第 5 章）**。

---

## 2. 双环境策略：真机零风险 vs mock 真执行

| 维度 | 真机（real，192.168.1.1） | mock（127.0.0.1:8090） |
|------|---------------------------|------------------------|
| 数据操作 | **零风险**：查询回显、表单不保存、确认框取消、校验拦截 | **真执行**：真建/真改/真删，模拟完整 CRUD 生命周期 |
| 确认框 | fh_confirm（Element UI `$confirm` DOM 弹窗，非原生 confirm） | 原生 `confirm()`（Playwright dialog 事件） |
| 危险操作 | 点按钮 → 断言确认框弹出 → **取消** | accept=True 真正执行（mock 内存态，可 reset 恢复） |
| 状态可重复性 | 天然不变（不提交任何写操作） | `POST /api/reset` 恢复出厂态；套件自清理 |
| 会话 | 保留设备会话 | Cookie `gw_session` 会话；恢厂后会话失效 |
| 登录失败 | 原生 `alert()`（login.js `login_result==4`） | HTTP 401 JSON |

**原则**：真机套件是「可对客户设备直接执行」的绿色安全范本；mock 套件是「完整功能验证」的加速器。
两者动作命名空间分离（`real.*` / `page.*`），同一份业务意图双写。

---

## 3. 真机关键机制（调试沉淀）

1. **登录失败 = alert 弹窗**：密码错误走 `alert("用户名或密码错误，请重试")`；`#login_error_hint` 是静态隐藏文本从不显示。断言必须用 dialog 监听捕获。
2. **双登录容器**：`#wraplogin_CM`（普通版）与 `#fh_login_container`（AP 版）仅一套可见；`_to_selector` 用 `offsetParent!==null` 判断。强制显示普通版时 `style.display=''`（不能设 'block'）。
3. **setItemId 机制**：`setItemId('x')` 运行时生成 `fhId_x`；源码模板字符串单引号转义为 `\'`，需还原再正则。
4. **菜单 id**：`fhId_{英文标识}_L{level}`；真机菜单与源码有差异，以 navigation 实测为准。
5. **会话保持**：设备保留上一会话时访问 login.html 被重定向 main.html，navigate 自动 logout 重试。
6. **负向登录用例**必须 `"auto_login": false` 禁用框架自动登录。
7. **页面渲染断言**：`#el_main` 可见且 textLen≥5 / htmlLen≥200 / childCount>0（短轮询 6 次）。
8. **WAN 边界规则**（networkConn.js checkData）：Username/Password 1-63、MTU 0-2000、VLANIDMark 0-4095、MulticastVlan -1~4095、IdleDisconnectTime 0-65535。
9. **真机非 regression 套件共享 session**：同一套件内用例共用浏览器/会话。若前面用例修改了表单输入或连接选择，后续用例会继承该页面状态。涉及"表单修改不保存"类用例，**验证设备数据未变的正确姿势**（五轮实测排错沉淀）：
   - ❌ `real.reload`（F5）：Chrome 会恢复有 id 的 input 刷新前输入值（表单恢复特性）
   - ❌ SPA 路由跳走再回来（`navigate_spa` 去他页再回）：真机前端 **keep-alive 缓存组件**，表单值保持
   - ✅ `real.evaluate` 清 `sessionStorage`/`localStorage` + `real.navigate` 整页导航 `/main.html`（组件全新 mounted，从设备拉真实数据）
   - ✅ **断言用动态偏移值**：如 fill MTU=1508（与默认值必不同），重进后 `assert_input_value_not` 1508 即证明未保存。**切勿臆测设备默认值**——本设备出厂 MTU=1492（中国移动 PPPoE 标准，非 1500），fill 1492 等于原值导致"恢复 1500"类断言必败
   - 新增 `real.evaluate(script)` 通用 JS 执行（读原值写 detail / 清缓存）

### 3.1 四类页面路由与关键元素（真机实测）

| 页面 | SPA 路由 | 关键元素 |
|------|----------|----------|
| WAN 连接 | `#/network/broadband/networkConn` | `fhId_selectWan`/`fhId_Username`/`fhId_Password`/`fhId_MTU`/`fhId_VLANIDMark`/`fhId_onApply`/`fhId_delWAN`；新增=下拉"新增WAN连接" |
| LAN 侧地址 | `#/status/userInfo/lanInfo` | `fhId_hostData`（动态IP表）+ `fhId_lanData`（以太网接口表），5s 自动轮询 |
| 设备管理-重启 | `#/management/deviceManagement/rebootDevice` | `fhId_onApply` |
| 设备管理-恢厂 | `#/management/deviceManagement/restoreDefault` | `fhId_onApplyRestore`（恢复默认）+ `fhId_onApplyFactory`（恢复出厂，v-if user==2） |

### 3.2 fh_confirm 确认框断言（DOM 级）

真机确认框基于 Element UI `$confirm`（DOM MessageBox），**不触发 Playwright dialog 事件**：

```
real.assert_confirm_visible  {"message_keyword": "您真的要删除该条连接么？"}   # .el-message-box 出现且文本匹配
real.click_confirm           {"accept": false}                               # 点「取消」按钮
real.assert_confirm_hidden                                                    # .el-message-box 消失
```

---

## 4. mock 套件执行与可重复性

```bash
# 1) 启动 mock 网关（端口 8090）
python mock_web_ui/server.py

# 2) 执行前重置状态（保证初始态）
curl -X POST http://127.0.0.1:8090/api/reset

# 3) 执行范本套件（CM 运营 profile，mock 环境）
python runner/run_suite.py --operator cm --env mock --suite wan_crud_mock
python runner/run_suite.py --operator cm --env mock --suite lan_info_mock
python runner/run_suite.py --operator cm --env mock --suite device_mgmt_mock
```

- 退出码 0 = 全通过，1 = 有失败（可接 CI）。
- `wan_crud_mock` 内部自清理：新增的 `MOCK_WAN_NEW_1` 由删除用例清除，MTU 修改后改回 1500。
- 执行中断导致残留时，重新 `curl -X POST /api/reset` 即可。

### 4.1 mock 断言能力（assert_expect）

`url_contains` / `title_contains` / `text`（精确）/ `text_contains` / **`text_not_contains`**（负向，删除后列表不再含某行）/ `input_value` / `visible` / `hidden` / `checked` / `non_empty` / `toast_success` / `toast_error`。

---

## 5. 安全测试：AI 可辅助的环节（调研结论）

### 5.1 自动化可全流程执行（Playwright 已落地）

| 类型 | 用例 | 自动化做法 |
|------|------|-----------|
| XSS-反射型 | 登录页用户名注入 payload | 填表→提交→`assert_no_dialog_containing(keyword)`（无弹窗携带 payload）→`assert_login_error` |
| XSS-存储型防线 | WAN 用户名塞 `<script>` 超长 payload | 依赖 1-63 长度校验拦截 → `assert_element(".el-form-item__error")` |
| XSS 面分析 | 确认框消息为静态文案 | `assert_confirm_visible(message_keyword)` 精确匹配 → 证明 `dangerouslyUseHTMLString` 无可控注入点 |
| 安全头 | 登录页响应头 | `assert_response_header("X-Frame-Options", path)`（防点击劫持） |
| 弱口令/暴力破解 | 错误密码尝试 | `assert_login_error`；批量字典由离线生成 + 解读扫描输出 |

### 5.2 建议 AI + 工具链分工

| 环节 | AI/LLM 角色 | 工具角色 |
|------|-------------|----------|
| payload 库生成 | 离线生成 XSS/注入/SQLi payload 变体库（按设备上下文裁剪） | 入库为 JSON 数据驱动用例 |
| 扫描输出解读 | 解读 Burp Suite / ZAP / nikto 扫描报告，标注可利用性与误报 | Burp/ZAP 主动扫描、被动代理流量采集 |
| 危险渲染点定位 | 辅助定位 `v-html` / `dangerouslySetInnerHTML` / `innerHTML=` 危险渲染点 | grep/代码检索 + navigation 截图比对 |
| 执行与回归 | 编写数据驱动用例 + 结果判定 | Playwright 全自动执行、截图留证 |
| 暴力破解字典 | 生成弱口令字典（设备默认密码规律） | 登录页批量尝试 + 失败计数 |

> 结论：XSS 三型、安全头检查、弱口令尝试**可 100% 自动化**（本范本已落地 security.json）；
> payload 变体生成、扫描输出解读、危险渲染点定位属 **AI 高价值辅助**环节，建议纳入后续 CI 流程。

---

## 6. 新增页面三步接入模板

以新增「防火墙规则」页为例（已存在 mock 页面 `firewall.html`）：

### 第 1 步：确认路由与元素（真机 navigation 实测 + mock 页面）

- 真机：`#/security/firewall`（以 navigation 实测为准），记录 `fhId_*` 元素 id、确认框文案、边界规则（前端 checkData）。
- mock：在 `mock_web_ui/pages/firewall.html` 实现页面 + `server.py` 增加 REST 端点。

### 第 2 步：注册 selectors

在 `operators/intl/selectors.json`（mock 回退源）+ `profiles/selectors/intl_baseline_selectors.json`（模板源）的 `pages` 增加：

```json
"firewall": {
  "url": "/firewall.html",
  "elements": {
    "fw_rule_list": "#fw_rule_list",
    "fw_name": "#fw_name",
    "fw_save_btn": "#fw_save_btn",
    "fw_del_btn": "#fw_del_btn",
    "fw_msg": "#fw_msg"
  }
}
```

> ⚠️ 两个文件必须同步（runner 的 mock 兼容层从 `operators/intl/selectors.json` 回退读取）。

### 第 3 步：编写双环境套件

```json
{
  "suite_id": "CM-REAL-FIREWALL",
  "operator": "cm", "env": "real",
  "cases": [ { "id": "TC-CM-FW-001", "title": "...", "steps": [
      {"action": "real.login", "params": {"role": "admin"}},
      {"action": "real.navigate_spa", "params": {"route": "/security/firewall"}},
      {"action": "real.assert_page", "params": {"component": "firewall"}},
      {"action": "real.assert_element", "params": {"selector": "#fhId_..."}}
  ]} ]
}
```

对应 mock 套件用 `page.*` actions（`page.goto` / `page.expect` 等），套件命名规则：
`{页面}_mock.json`，suite_id 前缀 `CM-MOCK-`。

### 套件设计检查清单

- [ ] 真机：零风险（不提交写操作 / 确认框必取消）
- [ ] 覆盖：查询回显 / 增删改入口 / 边界（下限-1、上限+1、正常值）/ 安全（注入点、确认框文案）
- [ ] mock：完整 CRUD 真执行 + 自清理或依赖 reset
- [ ] 可重复：同一套件连续执行两次均通过

---

## 7. 范本套件清单汇总

| 套件 | 环境 | 用例数 | 动作命名空间 | 核心断言 |
|------|------|--------|-------------|----------|
| login.json | real | 10 | real.* | 登录成功/失败、会话、登出 |
| wan_crud.json | real | 7 | real.* | 回显/新增入口/不保存/删除取消/边界 |
| lan_info.json | real | 4 | real.* | 双表容器/行数据/5s 轮询 |
| device_mgmt.json | real | 6 | real.* | 确认框取消/会话保持 |
| security.json | real | 5 | real.* | XSS 三型/安全头/弱口令 |
| wan_crud_mock.json | mock | 9 | page.* | 真建/真改/真删/边界 |
| lan_info_mock.json | mock | 4 | page.* | 表加载/行数据/刷新 |
| device_mgmt_mock.json | mock | 7 | page.* | 取消零风险/确认真执行/恢厂会话失效 |

### 首轮真机执行与修复记录（2026-08-20）

| 套件 | 首轮结果 | 失败用例 | 根因 | 修复 |
|------|----------|----------|------|------|
| wan_crud.json | 5/7 | TC-CM-WAN-004/006 | 共享 session：004「切走再切回」受 keep-alive 组件缓存，表单值保持；006 未切回 INTERNET 导致 Username 字段缺失 | 004 改「清 storage + 整页导航」+ 动态偏移值 1508 断言；006/SEC-002 增加 `select_option` 切回 INTERNET |
| lan_info.json | 4/4 | — | — | — |
| device_mgmt.json | 5/6 | TC-CM-DEV-002 | `real.assert_url_contains` 分发未兼容 `contains` 参数名 | runner 增加 `contains`/`substring` 双参数兼容 |
| security.json | 4/5 | TC-CM-SEC-002 | 同 006：未切回 INTERNET，Username 字段缺失 | 增加 `select_option` 切回 INTERNET |

### 最终验证结果（2026-08-20 14:15，修复后第二轮全量重跑）

| 套件 | 最终结果 | 耗时 | 执行报告 |
|------|----------|------|----------|
| wan_crud.json | **7/7** ✅ | 214.96s | `reports/case-docs/测试报告-CM-REAL-WAN-CRUD-20260820-141009.docx` |
| lan_info.json | **4/4** ✅ | — | `reports/case-docs/测试报告-CM-REAL-LAN-INFO-20260820-143301.docx` |
| device_mgmt.json | **6/6** ✅ | 183.29s | `reports/case-docs/测试报告-CM-REAL-DEVICE-MGMT-20260820-143301.docx` |
| security.json | **5/5** ✅ | 67.40s | `reports/case-docs/测试报告-CM-REAL-SECURITY-20260820-143302.docx` |

> **合计：真机 22/22、mock 20/20，双环境范本全部验证通过**（执行报告均嵌入真实截图）。
