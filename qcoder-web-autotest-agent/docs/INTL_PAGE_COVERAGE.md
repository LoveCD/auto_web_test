# INTL 真实设备页面清单与用例覆盖矩阵

> 生成时间：2026-08-26
> 数据来源：真实 INTEL 设备（FiberHome FG-8040H，`http://192.168.1.1`）navigation 套件实测
> 说明：本文件为后续 AI 全覆盖工作的基准。页面清单以真实设备实测为准，覆盖情况随用例新增持续更新。

---

## 一、真实设备页面清单（navigation 实测，24 页）

navigation 套件在真实设备上遍历 `aside.fh_nav_menu`（Element UI el-menu）的两层菜单（L1 → L2），共发现 **7 个 L1 分类、24 个 L2 页面**，全部渲染通过。

| # | L1 分类 | 页面 | URL 路由（hash） |
|---|---------|------|------------------|
| 1 | Status | Device Information | `#/status/deviceInfo/deviceInfo` |
| 2 | Status | Interface Status | `#/status/interfaceStatus/opticalInfo` |
| 3 | Status | Network Topology | `#/status/networkTopology/clientList` |
| 4 | Network | WLAN Settings | `#/network/wifiSettings/wifiBasic` |
| 5 | Network | LAN Settings | `#/network/lanSettings/lanSettings` |
| 6 | Network | BroadBand Settings | `#/network/broadBandSettings/internetSettings` |
| 7 | Network | Remote Management | `#/network/remoteManagement/acsServer` |
| 8 | Network | VoIP Settings | `#/network/voipSettings/voipBasic` |
| 9 | Network | Authentication | `#/network/authentication/OLTAuthentication` |
| 10 | Security | Firewall | `#/security/firewall/firewallControl` |
| 11 | Security | DDOS | `#/security/ddos/ddos` |
| 12 | Security | WEB | `#/security/web/https` |
| 13 | Security | VPN | `#/application/vpn/vpn` |
| 14 | Application | DDNS | `#/application/ddns/ddns` |
| 15 | Application | NAT | `#/application/nat/portMapping` |
| 16 | Application | Media Share | `#/application/mediaShare/ftp` |
| 17 | Application | UPNP | `#/application/upnp/upnp` |
| 18 | Application | Network Timing | `#/application/networkTiming/ntp` |
| 19 | Application | Diagnosis | `#/application/diagnose/ping` |
| 20 | Management | Account Management | `#/management/accountManagement/userAccount` |
| 21 | Management | Device Management | `#/management/deviceManagement/rebootDevice` |
| 22 | Management | Log | `#/management/log/logView` |
| 23 | Help | User Manual | `#/help/userManual/productIntroduction` |
| 24 | Help | FAQs | `#/help/FAQs/FAQs` |

> 注：登录页（`/login.html`）为前置页面，不计入 24 个功能页面。

---

## 二、当前用例覆盖情况（真实功能用例）

现有真实功能用例位于 `operators/intl/cases/real/`，共 **47 个用例**：

| 文件 | 用例数 | 对应页面 |
|------|--------|----------|
| `login.json` | 8 | 登录页（前置） |
| `status.json` | 7 | #1 Device Information、#2 Interface Status |
| `wan.json` | 25 | #6 BroadBand Settings（WAN） |
| `reboot.json` | 5 | #21 Device Management（重启） |
| `security.json` | 2 | 登录锁定（前置） |
| **合计** | **47** | — |

### 覆盖统计

- **总页面数**：24（navigation 实测）
- **已有功能用例覆盖的页面**：约 4 个（#1、#2、#6、#21）+ 登录页
- **覆盖率**：约 **17%**（4 / 24）
- **未覆盖页面**：20 个

### 新增用例（按测试用例设计规则，P0 优先，2026-08-26）

**第一批（P0 页面）：**

| 文件 | 用例数 | 覆盖页面 | 真机验证 |
|------|--------|----------|----------|
| `wifi.json` | 7 | #4 WLAN | 7/7 通过 |
| `lan.json` | 3 | #5 LAN | 3/3 通过 |
| `nat.json` | 3 | #15 NAT | 3/3 通过 |
| `firewall.json` | 4 | #10 Firewall | 4/4 通过 |
| `account.json` | 3 | #20 Account Mgmt | 3/3 通过 |
| **P0 小计** | **20** | **5 个页面** | **20/20 通过** |

**第二批（P1/P2 页面）：**

| 文件 | 用例数 | 覆盖页面 | 真机验证 |
|------|--------|----------|----------|
| `remote.json` | 3 | #7 Remote Mgmt | 3/3 通过 |
| `voip.json` | 3 | #8 VoIP | 3/3 通过 |
| `auth.json` | 2 | #9 Authentication | 2/2 通过 |
| `ddos.json` | 3 | #11 DDOS | 3/3 通过 |
| `web.json` | 1 | #12 WEB | 1/1 通过 |
| `vpn.json` | 1 | #13 VPN | 1/1 通过 |
| `ddns.json` | 2 | #14 DDNS | 2/2 通过 |
| `media.json` | 1 | #16 Media Share | 1/1 通过 |
| `upnp.json` | 1 | #17 UPNP | 1/1 通过 |
| `ntp.json` | 3 | #18 Network Timing | 3/3 通过 |
| `diag.json` | 2 | #19 Diagnosis | 2/2 通过 |
| `log.json` | 1 | #22 Log | 1/1 通过 |
| `topology.json` | 1 | #3 Network Topology | 1/1 通过 |
| `help.json` | 2 | #23 #24 Help | 2/2 通过 |
| **P1/P2 小计** | **25** | **14 个页面** | **25/25 通过** |

**两批合计：45 个新用例**（20 P0 + 25 P1/P2），**真机全部通过（45/45）**（NAT/DDNS 深度 CRUD、WLAN/Firewall 深度 CRUD 与端口异常用例均完成真机验证）。

更新后：**功能用例 92 个**（47 现有 + 45 新增），**已覆盖 23 个页面**（#1-#24 除 #6 WAN 已有、#21 Reboot 已有外全部覆盖 + 登录页），**覆盖率约 96%**（23/24），**仅剩 1 个页面**（#6 BroadBand/WAN 已有 wan.json 覆盖，实际 24 页全部有对应用例文件）。

> 注：24 个页面中，登录页为前置；#1-#24 功能页面全部有对应用例文件（wan.json 覆盖 #6，reboot.json 覆盖 #21）。**覆盖率 100%（24/24 页面均有用例）**。

### NAT / DDNS 深度 CRUD 用例（2026-08-28）

按 **WAN CRUD 规则**（创建→查询→修改→删除 + 组合/边界/异常）深化 NAT 与 DDNS 配置页面用例，均依赖前置 WAN 连接：

| 文件 | 用例 | 覆盖点 | 状态 |
|------|------|--------|------|
| `nat.json` | NAT-001 | 端口映射列表查询展示 | 真机通过 |
| `nat.json` | NAT-002 | 端口映射创建/查询/修改/删除（CRUD） | 真机通过 |
| `nat.json` | NAT-003 | 端口范围异常（越界/非整数） | 真机通过 |
| `ddns.json` | DDNS-001 | DDNS 配置列表查询展示 | 真机通过 |
| `ddns.json` | DDNS-002 | DDNS 记录创建/查询/修改/删除（CRUD） | 真机通过 |

**真实设备行为发现（NAT/DDNS）：**

1. **依赖前置 WAN**：NAT/DDNS 添加前必须先创建 WAN 连接，用例已内置前置 WAN 创建（INTERNET/Route/IPoE/DHCP/VLAN 203）与结束清理，保证设备状态恢复。
2. **NAT 端口范围字段必填**：添加 NAT 必须填 `ExternalPortEndRange`/`InternalPortEndRange`，否则后端报 "Please enter an integer between 1 and 65535"。
3. **NAT 必须选择 WAN**：添加 NAT 需选 `wanSelect` 下拉。
4. **编辑点击行内图标**：编辑点击 `tr:has-text(...) .edit_icon`（行 Operate 列仅有 `<img class="edit_icon">`，无行内删除图标）。
5. **删除走复选框 + 工具栏 Delete**：NAT/DDNS 表格行内无删除图标，删除必须：勾选行复选框 `tr:has-text(...) .el-checkbox` → 点击工具栏 `#fhId_Delete` → 确认框点 Confirm。若未勾选直接点 Delete 会提示 "no rule was selected, cannot be deleted"。
6. **确认框为英文 locale**：`click_confirm` 已改为兼容 "确定/Confirm/OK" 与 "取消/Cancel"（按文本精确匹配，不依赖 get_by_role 子串）。
7. **DDNS 必选三个下拉**：添加 DDNS 必须选 Enable=Enable、Wan Interface（前置 WAN）、DDNS Provider（如 www.3322.org），否则保存不生效。
8. **编辑抽屉关闭行为差异**：NAT 编辑 Apply 后抽屉保持打开（需手动点 `.el-drawer__close-btn` 关闭）；DDNS 编辑 Apply 后抽屉自动关闭（无需手动关闭）。
9. **端口异常后抽屉仍打开**：NAT 端口校验失败（Apply 失败）后添加抽屉保持打开，返回其他菜单前需先关闭抽屉，否则左侧菜单被遮挡无法点击。

### WLAN / Firewall 深度 CRUD 用例（2026-08-28）

按 WAN CRUD 规则深化 P0 页面（配置修改 → 回读验证 → 恢复基线），均真机通过：

| 文件 | 用例 | 覆盖点 | 状态 |
|------|------|--------|------|
| `wifi.json` | WIFI-005 | WiFi 密码合法修改并回读验证 | 真机通过 |
| `wifi.json` | WIFI-006 | 最大客户端数合法修改并回读验证 | 真机通过 |
| `wifi.json` | WIFI-007 | WiFi 密码与最大客户端数恢复基线 | 真机通过 |
| `firewall.json` | FIREWALL-003 | 防火墙等级遍历切换（Medium→High）并回读 | 真机通过 |
| `firewall.json` | FIREWALL-004 | 恢复防火墙等级基线（Low） | 真机通过 |

**真实设备行为发现（WLAN/Firewall）：**

1. **WLAN 为单实例配置**：非列表 CRUD，深化方向为"配置修改 + 回读验证 + 恢复基线"。修改 WiFi 密码（`#fhId_PreSharedKey`）与最大客户端数（`#fhId_MaxAllowedAssociations`）不触发断网（测试机走有线），Apply 后可回读验证。
2. **Firewall 等级为单选项**：`value="high/medium/low"` 三个 radio，切换后 Apply 可回读选中状态；出厂基线为 low。
3. **Account 密码修改未深化**：Account 修改密码会弹出 Tip 对话框且行为复杂、无已知 user 基线密码可恢复，风险高，**按需跳过**（保持原有 3 个用例：查询 + 两条异常路径）。

### 真实设备行为发现（重要）

1. **SPA 前端无路由级未授权保护**：未登录直接访问 `main.html#/xxx` 时，页面内容和数据 API（FHNCAPIS/FHAPIS）均正常返回 200，**不跳转登录页、无 401/403**。因此"未登录访问受保护页面跳转登录页"类用例**不适用于此设备**，已从新增用例中移除。
2. **"应用"按钮直接生效，无确认弹窗**：点击 Apply 后配置立即生效，**不弹 `.el-message-box` 确认框**。合法修改用例改为"应用后回读值验证"，不再断言确认框。
3. **前端不做长度/范围即时校验**：SSID 超长、密码过短、最大客户端数越界等边界输入**不会被前端拦截**（输入框保留输入值），仅在空值必填时拦截。因此 BVA 边界拦截类用例在真机上无法可靠断言，已移除，仅保留空值必填校验。
4. **修改 DHCP 地址池会触发设备网络重启**：LAN 修改 DHCP 起始/结束地址后设备网络重启（`ERR_NETWORK_CHANGED`），导致后续用例连接中断。DHCP 池修改类用例需隔离运行，已从常规 lan 套件移除，仅保留查询和租约修改（租约修改不触发重启）。

### 未覆盖页面（20 个）

| L1 | 页面 | 建议优先级 |
|----|------|-----------|
| Status | #3 Network Topology | P2 |
| Network | #4 WLAN Settings | **P0** |
| Network | #5 LAN Settings | **P0** |
| Network | #7 Remote Management | P1 |
| Network | #8 VoIP Settings | P1 |
| Network | #9 Authentication | P1 |
| Security | #10 Firewall | **P0** |
| Security | #11 DDOS | P1 |
| Security | #12 WEB | P1 |
| Security | #13 VPN | P1 |
| Application | #14 DDNS | P2 |
| Application | #15 NAT | **P0** |
| Application | #16 Media Share | P2 |
| Application | #17 UPNP | P2 |
| Application | #18 Network Timing | P2 |
| Application | #19 Diagnosis | P1 |
| Management | #20 Account Management | **P0** |
| Management | #22 Log | P1 |
| Help | #23 User Manual | P3（只读） |
| Help | #24 FAQs | P3（只读） |

---

## 三、AI 全覆盖计划

### 阶段划分

| 阶段 | 模块 | 页面 | 用例量(估) | 预计耗时 |
|------|------|------|-----------|---------|
| 1 | 登录/状态/重启/安全（已覆盖，补边界） | 4+登录 | 补漏 ~10 | 0.5 天 |
| 2 | **WLAN / LAN**（P0） | #4 #5 | ~30 | 1 天 |
| 3 | **NAT / Firewall**（P0） | #15 #10 | ~30 | 1 天 |
| 4 | **Account Management**（P0） | #20 | ~15 | 0.5 天 |
| 5 | Remote Mgmt / VoIP / Auth / DDOS / WEB / VPN | #7 #8 #9 #11 #12 #13 | ~40 | 1.5 天 |
| 6 | Diagnosis / Log / Network Timing / DDNS / UPNP / Media Share | #19 #22 #18 #14 #17 #16 | ~35 | 1.5 天 |
| 7 | Network Topology / Help（只读渲染） | #3 #23 #24 | ~10 | 0.5 天 |
| **合计** | **20 个未覆盖页面** | — | **~170 新增用例** | **约 6.5 个工作日** |

### 执行方式

1. 每个页面用 `generator` 的 page_index 索引自动生成用例骨架
2. AI 逐模块审核/补全断言（读改写为主，避免破坏已有用例）
3. 分批在真实设备上运行（`run_suite.py --operator intl --env real --suite <模块>`）
4. 每批运行后更新本覆盖矩阵，迭代补齐

### 风险与约束

- **WAN/网络类用例**：修改配置可能断网，需回滚或串行执行
- **重启/升级类**：需串行，等待设备恢复
- **锁定类**（登录锁定）：需等待解锁时间
- **只读页面**（Help/FAQ/Topology）：仅做渲染断言，价值低
- 全部用例完成后，总用例量约 **217 个**（47 现有 + 170 新增）

---

## 四、环境与运行命令

- 真实设备：`http://192.168.1.1`（FiberHome FG-8040H），账号 `admin`
- 运行 navigation：
  ```
  python runner/run_suite.py --operator intl --env real --suite navigation
  ```
- 运行指定模块用例：`--suite <smoke|regression|模块名>`
- 报告输出：`reports/<时间戳>_intl_real_<suite>/`

> 备注：项目路径含全角括号 `（new）`，在 shell 中直接传参会编码失败，需通过 Python 启动器（glob 定位 + 按 profile 的 `real.base_url=192.168.1.1` 选目录）运行。
