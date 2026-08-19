# 固件升级页面需求说明

## 页面

`upgrade.html` — 固件升级

## 元素

| 字段 | 控件 |
|---|---|
| Current Version | `#cur_version` |
| Latest Version | `#new_version` |
| Upgrade Available | `#upgrade_available` |
| Package Size | `#pkg_size` |
| Description | `#upgrade_desc` |
| Firmware URL | 输入框 `#firmware_url` |
| Upgrade | 按钮 `#upgrade_btn` |

## 业务规则

1. 展示当前版本 `INTL_BASELINE_1.0.0` 与最新版本 `INTL_BASELINE_1.0.1`。
2. 固件 URL 必须以 http:// 或 https:// 开头，否则拒绝并提示 "invalid"。
3. 合法 URL 触发升级，提示 "Upgrade started"，并更新当前版本。

## 边界值

- URL: `http://fw.example.com/x.bin` 通过；`not-a-url` / 空拒绝
