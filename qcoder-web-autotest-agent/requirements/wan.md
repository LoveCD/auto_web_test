# WAN 页面需求说明

## 页面

`wan.html` — WAN 状态展示（只读）

## 元素

| 字段 | 控件 |
|---|---|
| Connection Type | `#wan_type` |
| Connection Status | `#wan_status` |
| IP Address | `#wan_ip` |
| Subnet Mask | `#wan_mask` |
| Gateway | `#wan_gateway` |
| Primary DNS | `#wan_dns` |
| MAC Address | `#wan_mac` |

## 业务规则

1. 基线版本 WAN 为 DHCP 连接，状态 `connected`。
2. 所有字段均需展示真实值（非 "-"）。
3. IP / 网关 / DNS 必须为合法 IPv4 地址。

## 测试重点

- 状态与连接类型正确
- 字段完整性（7 个字段非空）
- 与状态页 `wan_ip` 一致
