# 系统维护页面需求说明

## 页面

`system.html` — 系统维护（设备信息 + 重启）

## 元素

| 字段 | 控件 |
|---|---|
| Product Model | `#sys_model` |
| Serial Number | `#sys_serial` |
| Software Version | `#sys_sw_version` |
| Firmware Version | `#sys_fw_version` |
| CPU Usage | `#sys_cpu` |
| Memory Usage | `#sys_memory` |
| Temperature | `#sys_temperature` |
| Reboot | 按钮 `#reboot_btn` |

## 业务规则

1. 设备信息全部展示真实值（非 "-"）。
2. 软件版本为基线版本 `INTL_BASELINE_1.0.0`。
3. 点击 Reboot 弹出确认对话框；确认后请求被接受，提示 "accepted"。
4. 重启为高风险操作，需二次确认。

## 测试重点

- 设备信息字段完整性
- 重启确认流程（dialog 处理）
- 重启受理结果提示
