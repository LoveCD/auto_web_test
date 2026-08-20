# -*- coding: utf-8 -*-
"""Mock 网关 Web 页面内存态。

对照真实设备 `web/web/UI/INTL/fiberweb` 的国际基线版本数据结构设计，
用于让自动化测试在一个可重复、可重置的仿真环境下运行。
"""

import threading
import time
import uuid

_LOCK = threading.Lock()

STATE = {
    # 会话: token -> {username, role, created}
    "sessions": {},
    "wifi": {
        "enabled": True,
        "ssid": "INTL_GW_24G",
        "security": "WPA2-PSK",
        "password": "Test123456",
        "max_clients": 32,
    },
    "status": {
        "model": "FG-8040H",
        "serial": "INTL202608010001",
        "software_version": "INTL_BASELINE_1.0.0",
        "firmware_version": "FG8_V1.0.0",
        "uptime_seconds": 86400,
        "boot_time": time.time() - 86400,
        "temperature_c": 42,
        "wan": {"status": "connected", "type": "dhcp", "ip": "100.64.1.10",
                "gateway": "100.64.0.1", "dns": "223.5.5.5", "mac": "A4:1F:72:00:00:01"},
        "wifi": {"enabled": True},
        "cpu_usage": 12,
        "memory_usage": 38,
    },
    "lan": {
        "ip": "192.168.1.1",
        "mask": "255.255.255.0",
        "dhcp_enabled": True,
        "dhcp_pool_start": "192.168.1.100",
        "dhcp_pool_end": "192.168.1.200",
        "hostname": "FH-Gateway",
    },
    "upgrade": {
        "current_version": "INTL_BASELINE_1.0.0",
        "latest_version": "INTL_BASELINE_1.0.1",
        "available": True,
        "size_mb": 42.6,
        "description": "Wi-Fi password rule & security fixes",
    },
    # WAN 连接列表（对齐真机 networkConn 页：可增删改查，INTERNET/TR069 多连接）
    "wan_connections": [
        {
            "id": 1,
            "name": "INTERNET_R_VID_10",
            "type": "PPPoE",
            "service": "INTERNET",
            "username": "cm@test",
            "password": "Test123456",
            "connection_trigger": "AlwaysOn",
            "idle_timeout": 0,
            "mtu": 1500,
            "vlan_id": 10,
            "status": "connected",
        }
    ],
    "wan_next_id": 2,
    # LAN 侧动态地址表（对齐真机 lanInfo 页：动态IP地址分配信息）
    "lan_hosts": [
        {"ip": "192.168.1.100", "ipv6": "", "mac": "AA:BB:CC:DD:EE:01",
         "hostname": "phone-01", "device_type": "WiFi", "port": "SSID1",
         "lease": 3600, "active": 1, "rssi": "-45dBm", "rate": "1200Mbps"},
        {"ip": "192.168.1.101", "ipv6": "", "mac": "AA:BB:CC:DD:EE:02",
         "hostname": "pc-01", "device_type": "Ethernet", "port": "LAN2",
         "lease": 7200, "active": 1, "rssi": "", "rate": "1000Mbps"},
    ],
    "last_restore_at": None,
    "last_factory_at": None,
    "last_reboot_at": None,
    "last_upgrade_at": None,
}

AUTH = {"username": "admin", "password": "admin123"}


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def create_session(username):
    """创建会话，返回 token。"""
    token = uuid.uuid4().hex
    with _LOCK:
        STATE["sessions"][token] = {"username": username, "role": "admin", "created": now_str()}
    return token


def is_valid_session(token):
    with _LOCK:
        return token in STATE["sessions"]


def destroy_session(token):
    with _LOCK:
        STATE["sessions"].pop(token, None)


def get_status():
    """按需动态生成 status（uptime 实时计算）。"""
    st = dict(STATE["status"])
    st["uptime_seconds"] = int(time.time() - st["boot_time"])
    st["boot_time_str"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st["boot_time"]))
    return st


def reset():
    """恢复出厂内存态，供测试前后重置。"""
    global STATE
    with _LOCK:
        STATE["sessions"].clear()
        STATE["wifi"].update({"enabled": True, "ssid": "INTL_GW_24G",
                              "security": "WPA2-PSK", "password": "Test123456", "max_clients": 32})
        st = STATE["status"]
        st.update({"software_version": "INTL_BASELINE_1.0.0",
                   "uptime_seconds": 86400, "boot_time": time.time() - 86400,
                   "temperature_c": 42})
        st["wan"].update({"status": "connected", "type": "dhcp", "ip": "100.64.1.10",
                          "gateway": "100.64.0.1", "dns": "223.5.5.5"})
        st["wifi"].update({"enabled": True})
        STATE["lan"].update({"ip": "192.168.1.1", "mask": "255.255.255.0",
                             "dhcp_enabled": True, "dhcp_pool_start": "192.168.1.100",
                             "dhcp_pool_end": "192.168.1.200"})
        STATE["upgrade"].update({"current_version": "INTL_BASELINE_1.0.0",
                                 "latest_version": "INTL_BASELINE_1.0.1", "available": True})
        STATE["wan_connections"] = [
            {"id": 1, "name": "INTERNET_R_VID_10", "type": "PPPoE",
             "service": "INTERNET", "username": "cm@test", "password": "Test123456",
             "connection_trigger": "AlwaysOn", "idle_timeout": 0,
             "mtu": 1500, "vlan_id": 10, "status": "connected"}
        ]
        STATE["wan_next_id"] = 2
        STATE["lan_hosts"] = [
            {"ip": "192.168.1.100", "ipv6": "", "mac": "AA:BB:CC:DD:EE:01",
             "hostname": "phone-01", "device_type": "WiFi", "port": "SSID1",
             "lease": 3600, "active": 1, "rssi": "-45dBm", "rate": "1200Mbps"},
            {"ip": "192.168.1.101", "ipv6": "", "mac": "AA:BB:CC:DD:EE:02",
             "hostname": "pc-01", "device_type": "Ethernet", "port": "LAN2",
             "lease": 7200, "active": 1, "rssi": "", "rate": "1000Mbps"},
        ]
        STATE["last_restore_at"] = None
        STATE["last_factory_at"] = None
        STATE["last_reboot_at"] = None
        STATE["last_upgrade_at"] = None
