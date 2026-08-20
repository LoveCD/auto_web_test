# -*- coding: utf-8 -*-
"""mock 网关后端 API 自测（WAN CRUD / LAN hosts / 设备管理）。

用法：先启动 mock 服务器（`python mock_web_ui/server.py`），再运行本脚本。
覆盖：登录会话、WAN 增删改查、边界规则（对齐真机 networkConn.js）、
LAN hosts 查询、恢复默认/恢厂（含会话失效语义）。
"""
import json
import sys
import urllib.request
import urllib.error
import http.cookiejar

BASE = "http://127.0.0.1:8090"
PASSED = []
FAILED = []

# Cookie 会话：登录后自动携带 gw_session
_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(method, path, body=None, expect=None):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _opener.open(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            code = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        code = e.code
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"__raw__": raw[:200]}
    ok = expect is None or code == expect
    tag = "PASS" if ok else "FAIL"
    (PASSED if ok else FAILED).append(f"[{tag}] {method} {path} -> {code} {json.dumps(parsed, ensure_ascii=False)[:160]}")
    return code, parsed


def step(name):
    print(f"\n=== {name} ===")


def main():
    step("1. 登录")
    call("POST", "/api/login", {"username": "admin", "password": "admin123"}, 200)

    step("2. WAN 列表（初始 1 条）")
    _, d = call("GET", "/api/wan/connections", expect=200)
    conns = d.get("connections", [])
    assert len(conns) == 1 and conns[0]["id"] == 1, conns
    assert conns[0]["password"] == "******", "密码应脱敏"

    step("3. 新增 WAN 连接")
    _, d = call("POST", "/api/wan/connections", {
        "name": "INTERNET_R_VID_20", "type": "PPPoE", "service": "INTERNET",
        "username": "user02", "password": "pass02", "connection_trigger": "AlwaysOn",
        "idle_timeout": 0, "mtu": 1500, "vlan_id": 20,
    }, 200)
    assert d["connection"]["id"] == 2, d

    step("4. 边界：用户名 64 字符被拒")
    call("POST", "/api/wan/connections", {"name": "x", "username": "u" * 64,
                                          "password": "p"}, 400)

    step("5. 边界：MTU 超界被拒")
    call("POST", "/api/wan/connections", {"name": "x", "username": "u",
                                          "password": "p", "mtu": 2001}, 400)

    step("6. 更新 WAN 连接（PUT）")
    _, d = call("PUT", "/api/wan/connections/2", {"mtu": 1400, "vlan_id": 30}, 200)
    assert d["connection"]["mtu"] == 1400 and d["connection"]["vlan_id"] == 30, d

    step("7. 更新不存在连接 -> 404")
    call("PUT", "/api/wan/connections/999", {"mtu": 1000}, 404)

    step("8. 删除 WAN 连接（DELETE）")
    call("DELETE", "/api/wan/connections/2", expect=200)
    _, d = call("GET", "/api/wan/connections", expect=200)
    assert len(d["connections"]) == 1, d

    step("9. 默认连接禁止删除")
    call("DELETE", "/api/wan/connections/1", expect=400)

    step("10. LAN hosts 查询")
    _, d = call("GET", "/api/lan/hosts", expect=200)
    assert len(d["hosts"]) == 2, d

    step("11. 状态端点 sanity")
    _, d = call("GET", "/api/status", expect=200)
    assert d.get("model"), d

    step("12. 恢复默认（不失效会话）")
    call("POST", "/api/restore_default", expect=202)
    call("GET", "/api/status", expect=200)

    step("13. 恢厂 -> 内存态重置且会话失效")
    call("POST", "/api/factory_reset", expect=202)
    _, d = call("GET", "/api/status", expect=401)
    assert d.get("error") == "unauthorized", d
    call("POST", "/api/login", {"username": "admin", "password": "admin123"}, 200)
    _, d = call("GET", "/api/wan/connections", expect=200)
    assert len(d["connections"]) == 1 and d["connections"][0]["id"] == 1, d

    print("\n" + "=" * 60)
    for line in PASSED:
        print(line)
    for line in FAILED:
        print(line)
    print("=" * 60)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
