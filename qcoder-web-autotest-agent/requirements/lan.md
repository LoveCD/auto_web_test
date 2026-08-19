# LAN 页面需求说明

## 页面

`lan.html` — LAN 设置

## 元素

| 字段 | 控件 | 约束 |
|---|---|---|
| LAN IP Address | 输入框 `#lan_ip` | 合法 IPv4 |
| Subnet Mask | 输入框 `#lan_mask` | 合法 IPv4 |
| DHCP Server | 开关 `#dhcp_enabled` | 勾选 = 开启 |
| DHCP Pool | 文本 `#dhcp_pool` | 只读展示 |
| Apply | 按钮 `#save_lan` | 保存并提示 |

## 业务规则

1. LAN IP 必须为合法 IPv4，非法拒绝并提示 `lan_ip_error`。
2. 子网掩码必须为合法 IPv4。
3. 保存成功 toast 显示 "applied successfully"，刷新后 IP 保持。
4. 基线默认: IP 192.168.1.1，掩码 255.255.255.0，DHCP 开启。

## 边界值

- IP: 192.168.1.1 通过；999.1.1.1 / 空 / 非数字拒绝
- 掩码: 255.255.255.0 通过；非法拒绝
