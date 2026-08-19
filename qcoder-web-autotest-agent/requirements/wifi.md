# Wi-Fi 页面需求说明

## 页面

`wifi.html` — Wi-Fi 基本设置（2.4G）

## 元素

| 字段 | 控件 | 约束 |
|---|---|---|
| Enable Wi-Fi | 开关 `#wifi_enabled` | 主无线总开关 |
| SSID | 输入框 `#ssid` | 1-32 字符 |
| Security Mode | 下拉 `#security_mode` | WPA2-PSK / WPA3-Personal / WPA2/WPA3 |
| Wi-Fi Password | 密码框 `#wifi_password` | 8-63 字符 |
| Apply | 按钮 `#save_wifi` | 保存并提示 |

## 业务规则

1. SSID 长度 1-32，超长拒绝并提示 `ssid_error`。
2. 密码长度 8-63，不足拒绝并提示 `pwd_error`。
3. 保存成功 toast 显示 "applied successfully"，且重新进入页面后 SSID 保持。
4. 修改 SSID 后，状态页 `wifi_ssid` 同步更新。

## 边界值

- SSID: 1 / 32 通过，33 拒绝，空拒绝
- 密码: 8 / 63 通过，7 / 64 拒绝，空拒绝
