# -*- coding: utf-8 -*-
"""Mock 网关 Web 管理界面服务器。

纯标准库实现（http.server），无第三方依赖。监听 127.0.0.1:8090。

能力:
  - 静态页面: /login.html /status.html /wifi.html /wan.html /lan.html /system.html /upgrade.html
  - Cookie 会话鉴权: 未登录访问页面或 /api/* 均跳转/拒绝
  - JSON API: /api/login /api/logout /api/status /api/wifi /api/wan /api/lan /api/system /api/reboot /api/upgrade
  - 业务校验: SSID 1-32、密码 8-63、LAN IP 合法性，与真实设备规则一致
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
        elif path == "/api/lan":
            if self._authorized():
                self._send_json(200, state.STATE["lan"])
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
        elif path == "/api/lan":
            if self._authorized():
                self._handle_set_lan(payload)
        elif path == "/api/reboot":
            if self._authorized():
                self._handle_reboot()
        elif path == "/api/reset":
            self._handle_reset()
        elif path == "/api/upgrade":
            if self._authorized():
                self._handle_upgrade(payload)
        else:
            self._send_json(404, {"error": "not found"})


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
