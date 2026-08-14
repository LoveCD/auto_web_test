from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
from urllib.parse import urlparse


STATE = {
    "token": "demo-token",
    "wifi": {
        "enabled": True,
        "ssid": "INTL_GW_24G",
        "security": "WPA2-PSK"
    },
    "status": {
        "software_version": "INTL_BASELINE_1.0.0",
        "uptime": 3600,
        "wan": {
            "status": "connected",
            "type": "dhcp",
            "ip": "100.64.1.10"
        },
        "wifi": {
            "enabled": True
        }
    }
}


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "MockInternationalGateway/1.0"

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def _write_json(self, status_code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        return self.headers.get("Authorization") == f"Bearer {STATE['token']}"

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/login":
            data = self._read_json()
            if data.get("username") == "admin" and data.get("password") == "admin123":
                self._write_json(200, {"token": STATE["token"], "role": "admin"})
            else:
                self._write_json(401, {"error": "invalid credentials"})
            return

        if not self._authorized():
            self._write_json(401, {"error": "unauthorized"})
            return

        if path == "/api/wifi":
            data = self._read_json()
            ssid = data.get("ssid", "")
            password = data.get("password", "")
            if not (1 <= len(ssid) <= 32):
                self._write_json(400, {"error": "ssid length must be 1-32"})
                return
            if not (8 <= len(password) <= 63):
                self._write_json(400, {"error": "password length must be 8-63"})
                return
            STATE["wifi"]["ssid"] = ssid
            STATE["status"]["wifi"]["enabled"] = True
            self._write_json(200, {"result": "ok", "ssid": ssid, "enabled": True})
            return

        if path == "/api/reboot":
            time.sleep(0.1)
            self._write_json(202, {"result": "rebooting"})
            return

        self._write_json(404, {"error": "not found"})

    def do_GET(self):
        path = urlparse(self.path).path
        if not self._authorized():
            self._write_json(401, {"error": "unauthorized"})
            return

        if path == "/api/status":
            self._write_json(200, STATE["status"])
            return

        if path == "/api/wifi":
            self._write_json(200, STATE["wifi"])
            return

        if path == "/api/wan":
            self._write_json(200, STATE["status"]["wan"])
            return

        self._write_json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8088), GatewayHandler)
    print("Mock international gateway API listening on http://127.0.0.1:8088")
    server.serve_forever()

