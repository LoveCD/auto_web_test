# -*- coding: utf-8 -*-
"""Mock 网关 Web 管理界面服务器。

纯标准库实现（http.server），无第三方依赖。监听 127.0.0.1:8090。

能力:
  - 静态页面: /login.html /status.html /wifi.html /wan.html /lan.html /system.html /upgrade.html
  - Cookie 会话鉴权: 未登录访问页面或 /api/* 均跳转/拒绝
  - JSON API: /api/login /api/logout /api/status /api/wifi /api/wan /api/lan /api/system /api/reboot /api/upgrade
  - WAN 连接 CRUD: GET/POST /api/wan/connections, PUT/DELETE /api/wan/connections/{id}
  - LAN 主机表: GET /api/lan/hosts；设备管理: POST /api/restore_default /api/factory_reset
  - 业务校验: SSID 1-32、密码 8-63、LAN IP 合法性，与真实设备规则一致
  - WAN 边界校验（对齐真机 networkConn.js）: 名称/用户名/密码 1-63、MTU 0-2000、VLAN 0-4095、空闲 0-65535
"""

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state

HOST = "127.0.0.1"
PORT = 8090
ROOT = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(ROOT, "pages")
STATIC_DIR = os.path.join(ROOT, "static")

COOKIE_NAME = "gw_session"
PAGE_NAMES = {
    "/": "login.html",
    "/login.html": "login.html",
    "/status.html": "status.html",
    "/wifi.html": "wifi.html",
    "/wan.html": "wan.html",
    "/lan.html": "lan.html",
    "/system.html": "system.html",
    "/upgrade.html": "upgrade.html",
    "/main.html": "status.html",
}

RE_IPV4 = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


def valid_ipv4(ip):
    m = RE_IPV4.match(ip)
    if not m:
        return False
    return all(0 <= int(g) <= 255 for g in m.groups())


class MockGatewayHandler(BaseHTTPRequestHandler):
    server_version = "MockGateway/1.0"

    # ------------------------------------------------------------------ utils
    def _send_json(self, code, payload, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        for key, value in (extra_headers or []):
            self.send_header(key, value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _session_token(self):
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith(COOKIE_NAME + "="):
                return part[len(COOKIE_NAME) + 1:]
        return None

    def _authorized(self):
        token = self._session_token()
        if token and state.is_valid_session(token):
            return True
        self._send_json(401, {"error": "unauthorized"})
        return False

    def _set_session_cookie(self, token):
        return ("Set-Cookie", f"{COOKIE_NAME}={token}; Path=/; HttpOnly")

    def _clear_session_cookie(self):
        return ("Set-Cookie", f"{COOKIE_NAME}=; Path=/; Max-Age=0")

    def log_message(self, fmt, *args):
        sys.stdout.write("[mock-web] %s - %s\n" % (self.address_string(), fmt % args))

    # ------------------------------------------------------------------ pages
    def _serve_page(self, path):
        page_file = PAGE_NAMES.get(path)
        if page_file is None:
            self._send_json(404, {"error": "not found"})
            return
        if page_file == "login.html":
            # 已登录访问登录页 -> 直接进状态页
            if state.is_valid_session(self._session_token()):
                self.send_response(302)
                self.send_header("Location", "/status.html")
                self.end_headers()
                return
        else:
            if not state.is_valid_session(self._session_token()):
                self.send_response(302)
                self.send_header("Location", "/login.html")
                self.end_headers()
                return
        fp = os.path.join(PAGES_DIR, page_file)
        if not os.path.exists(fp):
            self._send_json(404, {"error": "not found"})
            return
        with open(fp, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path):
        rel = path[len("/static/"):] if path.startswith("/static/") else path.lstrip("/")
        fp = os.path.join(STATIC_DIR, rel)
        if not os.path.isfile(fp):
            self._send_json(404, {"error": "not found"})
            return
        ctype = "text/css" if fp.endswith(".css") else "application/octet-stream"
        with open(fp, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------ API
    def _handle_login(self, payload):
        username = str(payload.get("username") or "")
        password = str(payload.get("password") or "")
        if username == state.AUTH["username"] and password == state.AUTH["password"]:
            token = state.create_session(username)
            self._send_json(200, {"result": "ok", "role": "admin", "username": username},
                            extra_headers=[self._set_session_cookie(token)])
        else:
            self._send_json(401, {"error": "invalid credentials"})

    def _handle_logout(self):
        state.destroy_session(self._session_token() or "")
        self._send_json(200, {"result": "ok"},
                        extra_headers=[self._clear_session_cookie()])

    def _handle_get_wifi(self):
        wifi = dict(state.STATE["wifi"])
        wifi.pop("password", None)  # 不返回明文密码
        self._send_json(200, wifi)

    def _handle_set_wifi(self, payload):
        ssid = str(payload.get("ssid") or "")
        password = str(payload.get("password") or "")
        enabled = payload.get("enabled", state.STATE["wifi"]["enabled"])
        if not (1 <= len(ssid) <= 32):
            self._send_json(400, {"error": "ssid length must be 1-32"})
            return
        if not (8 <= len(password) <= 63):
            self._send_json(400, {"error": "password length must be 8-63"})
            return
        state.STATE["wifi"].update({
            "ssid": ssid, "password": password,
            "enabled": bool(enabled),
            "security": payload.get("security", "WPA2-PSK"),
            "max_clients": int(payload.get("max_clients", 32)),
        })
        state.STATE["status"]["wifi"]["enabled"] = bool(enabled)
        self._send_json(200, {"result": "ok", "ssid": ssid,
                              "enabled": bool(enabled), "applied": True})

    def _handle_set_lan(self, payload):
        ip = str(payload.get("ip") or "")
        mask = str(payload.get("mask") or "")
        if not valid_ipv4(ip):
            self._send_json(400, {"error": "invalid lan ip"})
            return
        if not valid_ipv4(mask):
            self._send_json(400, {"error": "invalid netmask"})
            return
        state.STATE["lan"].update({
            "ip": ip, "mask": mask,
            "dhcp_enabled": bool(payload.get("dhcp_enabled", state.STATE["lan"]["dhcp_enabled"])),
        })
        self._send_json(200, {"result": "ok", "ip": ip, "applied": True})

    def _handle_reboot(self):
        state.STATE["last_reboot_at"] = state.now_str()
        state.STATE["status"]["boot_time"] = __import__("time").time()
        self._send_json(202, {"result": "rebooting"})

    def _handle_restore_default(self):
        """恢复默认配置（模拟：记录时间，状态保持默认值）。"""
        state.STATE["last_restore_at"] = state.now_str()
        self._send_json(202, {"result": "restoring"})

    def _handle_factory_reset(self):
        """恢复出厂配置（模拟：重置内存态 + 记录时间，会话随 reset 失效）。"""
        state.reset()
        state.STATE["last_factory_at"] = state.now_str()
        self._send_json(202, {"result": "resetting"})

    # ------------------------------------------------------------------ WAN CRUD
    WAN_FIELDS = ("name", "type", "service", "username", "password",
                  "connection_trigger", "idle_timeout", "mtu", "vlan_id")

    def _validate_wan(self, data, partial=False):
        """对齐真机 networkConn.js checkData 边界规则。返回 (errors, normalized)。

        partial=True（更新语义）：字符串字段为空串表示"不修改"，跳过校验且不写入。
        """
        errors = []
        norm = {}
        for f in self.WAN_FIELDS:
            if f not in data:
                continue
            v = data[f]
            if f in ("name", "username", "password"):
                s = str(v)
                if partial and s == "":
                    continue  # 更新时留空 = 保持不变（对齐真机表单语义）
                norm[f] = s
                if len(s) == 0:
                    errors.append(f"{f} is required")
                elif len(s) > 63:
                    errors.append(f"{f} length must be 1-63 (got {len(s)})")
            elif f in ("mtu", "vlan_id", "idle_timeout"):
                try:
                    n = int(v)
                    norm[f] = n
                except (TypeError, ValueError):
                    errors.append(f"{f} must be an integer")
                    continue
                if f == "mtu" and not (0 <= n <= 2000):
                    errors.append(f"mtu must be 0-2000 (got {n})")
                if f == "vlan_id" and not (0 <= n <= 4095):
                    errors.append(f"vlan_id must be 0-4095 (got {n})")
                if f == "idle_timeout" and not (0 <= n <= 65535):
                    errors.append(f"idle_timeout must be 0-65535 (got {n})")
            else:
                norm[f] = v
        if partial:
            return errors, norm
        # 新增/全量更新：必填
        for f in ("name", "username", "password"):
            if f not in norm:
                errors.append(f"{f} is required")
        return errors, norm

    def _wan_list(self):
        conns = []
        for c in state.STATE["wan_connections"]:
            item = dict(c)
            item["password"] = "******"  # 不返回明文
            conns.append(item)
        self._send_json(200, {"connections": conns,
                              "next_id": state.STATE["wan_next_id"]})

    def _wan_create(self, payload):
        errors, norm = self._validate_wan(payload)
        if errors:
            self._send_json(400, {"error": "; ".join(errors)})
            return
        conn = {"id": state.STATE["wan_next_id"], "status": "connected",
                "type": norm.get("type", "PPPoE"),
                "service": norm.get("service", "INTERNET"),
                "connection_trigger": norm.get("connection_trigger", "AlwaysOn")}
        conn.update(norm)
        state.STATE["wan_connections"].append(conn)
        state.STATE["wan_next_id"] += 1
        self._send_json(200, {"result": "ok", "connection": conn})

    def _wan_update(self, conn_id, payload):
        conn = self._find_wan(conn_id)
        if conn is None:
            self._send_json(404, {"error": "connection not found"})
            return
        errors, norm = self._validate_wan(payload, partial=True)
        if errors:
            self._send_json(400, {"error": "; ".join(errors)})
            return
        conn.update(norm)
        self._send_json(200, {"result": "ok", "connection": conn})

    def _wan_delete(self, conn_id):
        conn = self._find_wan(conn_id)
        if conn is None:
            self._send_json(404, {"error": "connection not found"})
            return
        if conn_id == 1:
            self._send_json(400, {"error": "default connection cannot be deleted"})
            return
        state.STATE["wan_connections"] = [
            c for c in state.STATE["wan_connections"] if c["id"] != conn_id]
        self._send_json(200, {"result": "deleted"})

    def _find_wan(self, conn_id):
        for c in state.STATE["wan_connections"]:
            if c["id"] == conn_id:
                return c
        return None

    def _handle_get_wan_connections(self):
        self._wan_list()

    def _handle_post_wan_connections(self, payload):
        self._wan_create(payload)

    def _handle_wan_connection(self, conn_id, payload, method):
        if method == "DELETE":
            self._wan_delete(conn_id)
        elif method == "GET":
            conn = self._find_wan(conn_id)
            if conn is None:
                self._send_json(404, {"error": "connection not found"})
                return
            item = dict(conn)
            item["password"] = "******"  # 单查同样脱敏
            self._send_json(200, item)
        else:
            self._wan_update(conn_id, payload)

    # ------------------------------------------------------------------ LAN hosts
    def _handle_lan_hosts(self):
        self._send_json(200, {"hosts": state.STATE["lan_hosts"]})

    def _handle_reset(self):
        """测试支持端点：恢复出厂内存态，供用例间数据隔离。"""
        state.reset()
        self._send_json(200, {"result": "reset"})

    def _handle_upgrade(self, payload):
        url = str(payload.get("url") or "")
        if url and not url.startswith(("http://", "https://")):
            self._send_json(400, {"error": "invalid firmware url"})
            return
        state.STATE["last_upgrade_at"] = state.now_str()
        state.STATE["upgrade"]["current_version"] = state.STATE["upgrade"]["latest_version"]
        self._send_json(202, {"result": "upgrading", "to_version": state.STATE["upgrade"]["latest_version"]})

    # ------------------------------------------------------------------ do_*
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/login":
            self._send_json(404, {"error": "not found"})
        elif path == "/api/logout":
            self._handle_logout()
        elif path.startswith("/api/status"):
            if self._authorized():
                self._send_json(200, state.get_status())
        elif path == "/api/wifi":
            if self._authorized():
                self._handle_get_wifi()
        elif path == "/api/wan":
            if self._authorized():
                self._send_json(200, state.STATE["status"]["wan"])
        elif path == "/api/wan/connections":
            if self._authorized():
                self._handle_get_wan_connections()
        elif path.startswith("/api/wan/connections/"):
            if self._authorized():
                conn_id = self._path_id(path, "/api/wan/connections/")
                if conn_id is not None:
                    self._handle_wan_connection(conn_id, {}, "GET")
                else:
                    self._send_json(404, {"error": "bad connection id"})
        elif path == "/api/lan":
            if self._authorized():
                self._send_json(200, state.STATE["lan"])
        elif path == "/api/lan/hosts":
            if self._authorized():
                self._handle_lan_hosts()
        elif path == "/api/system":
            if self._authorized():
                st = state.get_status()
                self._send_json(200, {
                    "model": st["model"], "serial": st["serial"],
                    "firmware_version": st["firmware_version"],
                    "software_version": st["software_version"],
                    "uptime_seconds": st["uptime_seconds"],
                    "temperature_c": st["temperature_c"],
                    "cpu_usage": st["cpu_usage"], "memory_usage": st["memory_usage"],
                })
        elif path == "/api/upgrade":
            if self._authorized():
                self._send_json(200, state.STATE["upgrade"])
        elif path.startswith("/api/"):
            self._send_json(404, {"error": "not found"})
        elif path.startswith("/static/"):
            self._serve_static(path)
        else:
            self._serve_page(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        payload = self._read_body()
        if path == "/api/login":
            self._handle_login(payload)
        elif path == "/api/logout":
            if self._authorized():
                self._handle_logout()
        elif path == "/api/wifi":
            if self._authorized():
                self._handle_set_wifi(payload)
        elif path == "/api/wan/connections":
            if self._authorized():
                self._handle_post_wan_connections(payload)
        elif path == "/api/lan":
            if self._authorized():
                self._handle_set_lan(payload)
        elif path == "/api/reboot":
            if self._authorized():
                self._handle_reboot()
        elif path == "/api/restore_default":
            if self._authorized():
                self._handle_restore_default()
        elif path == "/api/factory_reset":
            if self._authorized():
                self._handle_factory_reset()
        elif path == "/api/reset":
            self._handle_reset()
        elif path == "/api/upgrade":
            if self._authorized():
                self._handle_upgrade(payload)
        else:
            self._send_json(404, {"error": "not found"})

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        payload = self._read_body()
        if path.startswith("/api/wan/connections/"):
            if self._authorized():
                conn_id = self._path_id(path, "/api/wan/connections/")
                if conn_id is not None:
                    self._handle_wan_connection(conn_id, payload, "PUT")
                else:
                    self._send_json(404, {"error": "bad connection id"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/wan/connections/"):
            if self._authorized():
                conn_id = self._path_id(path, "/api/wan/connections/")
                if conn_id is not None:
                    self._wan_delete(conn_id)
                else:
                    self._send_json(404, {"error": "bad connection id"})
        else:
            self._send_json(404, {"error": "not found"})

    def _path_id(self, path, prefix):
        """从 REST 路径提取数字 id，失败返回 None。"""
        rest = path[len(prefix):]
        try:
            return int(rest)
        except (ValueError, TypeError):
            return None


def main():
    state.reset()
    server = ThreadingHTTPServer((HOST, PORT), MockGatewayHandler)
    print(f"[mock-web] Mock gateway web UI listening on http://{HOST}:{PORT}")
    print(f"[mock-web] default account: {state.AUTH['username']} / {state.AUTH['password']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[mock-web] shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
