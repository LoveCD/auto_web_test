import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dotted_get(data, path):
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(path)
    return current


class ApiClient:
    def __init__(self, profile):
        self.profile = profile
        self.base_url = profile["base_url"].rstrip("/")
        self.token = None
        self.http_logs = []

    def _request(self, method, api_key, payload=None, use_auth=True):
        url = self.base_url + self.profile["api"][api_key]
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        if use_auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = request.Request(url, data=body, headers=headers, method=method)
        started = time.time()
        try:
            with request.urlopen(req, timeout=self.profile["timeouts"]["request_seconds"]) as resp:
                raw = resp.read().decode("utf-8")
                result = {
                    "status_code": resp.status,
                    "json": json.loads(raw or "{}"),
                    "duration_ms": int((time.time() - started) * 1000)
                }
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            result = {
                "status_code": exc.code,
                "json": json.loads(raw or "{}"),
                "duration_ms": int((time.time() - started) * 1000)
            }
        except Exception as exc:
            result = {
                "status_code": 0,
                "json": {"error": str(exc)},
                "duration_ms": int((time.time() - started) * 1000)
            }

        self.http_logs.append({
            "method": method,
            "url": url,
            "payload": payload,
            "use_auth": use_auth,
            "response": result
        })
        return result

    def login(self, username=None, password=None):
        auth = self.profile["auth"]
        response = self._request("POST", "login", {
            "username": username or auth["username"],
            "password": password or auth["password"]
        }, use_auth=False)
        if response["status_code"] == 200 and "token" in response["json"]:
            self.token = response["json"]["token"]
        return response

    def get_status(self, use_auth=True):
        return self._request("GET", "status", use_auth=use_auth)

    def get_wifi(self, use_auth=True):
        return self._request("GET", "wifi_get", use_auth=use_auth)

    def set_wifi(self, ssid, password):
        return self._request("POST", "wifi_set", {"ssid": ssid, "password": password})

    def get_wan_status(self):
        return self._request("GET", "wan_status")

    def reboot(self):
        return self._request("POST", "reboot", {})


def assert_expect(response, expect):
    failures = []
    for key, expected in (expect or {}).items():
        try:
            actual = response["status_code"] if key == "status_code" else dotted_get(response["json"], key.replace("json.", ""))
        except KeyError:
            failures.append(f"{key}: missing, expected {expected!r}")
            continue
        if actual != expected:
            failures.append(f"{key}: expected {expected!r}, got {actual!r}")
    return failures


def execute_step(client, step):
    action = step["action"]
    params = step.get("params", {})
    if action == "api.login":
        response = client.login(params.get("username"), params.get("password"))
    elif action == "api.get_status":
        response = client.get_status(params.get("use_auth", True))
    elif action == "api.get_wifi":
        response = client.get_wifi(params.get("use_auth", True))
    elif action == "api.set_wifi":
        response = client.set_wifi(params["ssid"], params["password"])
    elif action == "api.get_wan_status":
        response = client.get_wan_status()
    elif action == "api.reboot":
        response = client.reboot()
    else:
        response = {"status_code": 0, "json": {"error": f"unknown action {action}"}, "duration_ms": 0}

    expected = step.get("expect")
    if expected is None and action == "api.login":
        expected = {"status_code": 200}
    failures = assert_expect(response, expected)
    return {
        "action": action,
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "response": response
    }


def suite_path(suite):
    mapping = {
        "smoke": ROOT / "cases" / "smoke" / "baseline_smoke.json",
        "regression": ROOT / "cases" / "regression" / "core_regression.json"
    }
    if suite not in mapping:
        raise SystemExit(f"Unknown suite {suite}. Use smoke or regression.")
    return mapping[suite]


def write_report(report):
    run_dir = ROOT / "reports" / report["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "result.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        f"# Web API AutoTest Report: {report['suite_id']}",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Profile: `{report['profile']}`",
        f"- Total: {report['summary']['total']}",
        f"- Passed: {report['summary']['passed']}",
        f"- Failed: {report['summary']['failed']}",
        f"- Duration: {report['summary']['duration_seconds']}s",
        "",
        "## Cases",
        ""
    ]
    for case in report["cases"]:
        lines.append(f"- {case['status'].upper()} `{case['id']}` {case['title']}")
        for step in case["steps"]:
            if step["status"] == "fail":
                lines.append(f"  - Failed step `{step['action']}`: {'; '.join(step['failures'])}")
    (run_dir / "result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["smoke", "regression"], required=True)
    parser.add_argument("--profile", default="intl_baseline")
    args = parser.parse_args()

    profile = load_json(ROOT / "profiles" / f"{args.profile}.json")
    suite = load_json(suite_path(args.suite))
    started = time.time()
    cases = []

    for case in suite["cases"]:
        client = ApiClient(profile)
        step_results = []
        status = "pass"
        for step in case["steps"]:
            result = execute_step(client, step)
            step_results.append(result)
            if result["status"] == "fail":
                status = "fail"
                break
        cases.append({
            "id": case["id"],
            "title": case["title"],
            "module": case["module"],
            "priority": case["priority"],
            "tags": case["tags"],
            "status": status,
            "steps": step_results,
            "http_logs": client.http_logs
        })

    passed = len([case for case in cases if case["status"] == "pass"])
    run_id = dt.datetime.now().strftime(f"%Y%m%d_%H%M%S_%f_{args.suite}")
    report = {
        "run_id": run_id,
        "suite_id": suite["suite_id"],
        "profile": args.profile,
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "duration_seconds": round(time.time() - started, 2)
        },
        "cases": cases
    }
    report_dir = write_report(report)
    print(f"Report written to {report_dir}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
