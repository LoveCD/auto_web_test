# -*- coding: utf-8 -*-
"""INTL 老 UI（HTML 多页版）用例「执行顺序」的唯一来源。

背景：执行顺序与报告呈现顺序必须一致，否则报告里的「测试项 N」与实际执行
次序对不上。历史上两处各写一份顺序定义——
  * 执行器 runner/run_intl_real_html.py：显式文件列表（副作用隔离序）
  * 报告生成器 tools/gen_intl_word.py：sorted(glob()) 文件名字典序
结果 65 个页面中 64 个位置错位。本模块将顺序收敛为单一来源，两边同源引用。

排序原则（副作用隔离）：只读/低副作用套件在前，配置类居中，高危套件
（system：恢复出厂 / 固件升级 / 管理端口 / 管理账号）与登录锁定类
（login/security）置末，避免其副作用波及其它套件造成级联失败。
"""

# 套件名 → 该模块下各页面用例文件列表（每个页面一个独立 json 文件）
SUITES = {
    "login": ["login.json"],
    "wan": ["wan.json"],
    "status": ["status.json"],
    "reboot": ["reboot.json"],
    # 2026-09-18：移除 mobile.json（手机端兼容性 5 条用例已按需求删除，套件不再保留）
    "wifi": ["wifi_basic.json", "wifi_basic_5g.json", "wifi_advanced.json",
             "wifi_advanced_5g.json", "wifi_control.json", "wifi_control_5g.json",
             "band_steering.json", "wps.json", "multi_ap_enable.json"],
    "lan": ["lan_settings.json", "static_ip_settings.json"],
    "route": ["default_route.json", "static_route.json"],
    # 2026-09-11：移除 port_isolation.json（设备无端口隔离页面，INTL-FW-012 用例已删除）
    "firewall": ["firewall_control.json", "ip_filter.json", "url_filter.json",
                  "mac_filter.json", "port_scan.json", "acl_settings.json",
                  "ipv6_filter.json", "ipv6_mac_filter.json", "ipv6_acl_settings.json",
                  "ddos.json", "https.json", "dhcp_filter.json"],
    "remote": ["remote.json"],
    "voip": ["voip_key.json", "voip_basic.json", "voip_advanced.json",
              "voip_timer.json", "voip_coding.json"],
    "system": ["restore_default.json", "firmware_up.json", "config_file.json",
                "user_account.json", "ntp.json", "log_view.json",
                "admin_account.json", "web_port.json"],
    "status_rest": ["wan_status.json", "lan_status.json", "eth_ports.json",
                     "dhcp_list.json", "optical_info.json", "voip_status.json",
                     "wifi_status_2g.json", "wifi_status_5g.json",
                     "wifi_list.json", "topo.json"],
    "network_rest": ["internet_settings.json", "iptv_settings.json", "olt_authentication.json"],
    "app_rest": ["vpn.json", "ddns.json", "port_mapping.json", "upnp.json",
                  "nat.json", "dmz.json", "ping.json", "traceroute.json"],
    # security 置末：其 SEC-001/002 会触发登录锁定，放最后执行避免污染其他套件
    "security": ["security.json"],
}

# --suite all 的完整执行顺序（副作用隔离序）
ALL_FILES = (["status.json", "reboot.json"] + SUITES["status_rest"]
             + ["wan.json"] + SUITES["app_rest"] + SUITES["network_rest"]
             + SUITES["wifi"] + SUITES["route"] + SUITES["firewall"]
             + SUITES["remote"] + SUITES["voip"] + SUITES["lan"]
             + SUITES["system"] + ["login.json", "security.json"])

# 触发登录锁定的用例必须移到最后执行（否则账号锁定会污染后续用例）
LOCKOUT_IDS = {"INTL-SEC-001", "INTL-SEC-002"}


def ordered_stems():
    """按执行顺序返回用例文件名主干（去 .json、去重）。

    报告生成器用它给页面排序，保证报告测试项顺序 == 实际执行顺序。
    """
    stems = []
    for f in ALL_FILES:
        stem = f[:-5] if f.endswith(".json") else f
        if stem not in stems:
            stems.append(stem)
    return stems


def ordered_file_names(suite="all"):
    """返回指定套件的用例文件名列表；suite='all' 返回全量执行顺序。"""
    return list(ALL_FILES) if suite == "all" else list(SUITES.get(suite, []))


def sort_cases(cases_list):
    """对单个页面内的用例排序：锁定类用例（SEC-001/002）置尾，其余保持声明序。

    与执行器「normal_cases + lockout_cases」的排序语义一致。
    """
    lock = [c for c in cases_list if c.get("id") in LOCKOUT_IDS]
    normal = [c for c in cases_list if c.get("id") not in LOCKOUT_IDS]
    return normal + lock
