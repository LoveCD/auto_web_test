# -*- coding: utf-8 -*-
"""Web 自动化测试执行器（运营商 + 环境感知）。

用法:
    # CM 真机（连接 192.168.1.1）
    python runner/run_suite.py --operator cm --env real --suite smoke

    # INTL Mock（离线）
    python runner/run_suite.py --operator intl --env mock --suite smoke

    # CM 全页面遍历截图
    python runner/run_suite.py --operator cm --env real --suite navigation

    # 运行 NL 生成的用例套件
    python runner/run_suite.py --operator cm --env real --suite generated/vlan_bind

退出码: 0 = 全部通过, 1 = 存在失败
"""
import argparse
import datetime
import json
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.config import resolve_config  # noqa: E402
from keywords.web_keywords import WebSession  # noqa: E402
from keywords.real_keywords import RealWebSession  # noqa: E402
from keywords.assert_keywords import assert_expect  # noqa: E402
from runner.report import new_run_id, write_reports  # noqa: E402


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_profile(operator):
    # .env 由 core.config 模块导入时自动加载（敏感配置注入）
    p = load_json(os.path.join(ROOT, "operators", operator, "profile.json"))
    s = load_json(os.path.join(ROOT, "operators", operator, "selectors.json"))
    return resolve_config(p), s


def build_navigation_cases(profile):
    """根据 profile.modules 自动生成页面遍历用例（profile 模式，作为 DOM 遍历的 fallback）。"""
    cases = []
    idx = 0
    for mod, cfg in profile.get("modules", {}).items():
        for page in cfg.get("pages", []):
            idx += 1
            comp = page.get("component", page["route"].split("/")[-1])
            cases.append({
                "id": f"TC-NAV-{idx:03d}-{comp}",
                "module": cfg.get("title", mod),
                "priority": "P0" if page.get("critical") else "P1",
                "title": page.get("title", comp),
                "steps": [
                    {"action": "real.navigate_spa", "params": {"route": page["route"]}},
                    {"action": "real.screenshot", "params": {"name": f"nav_{comp}"}},
                    {"action": "real.assert_page", "params": {"component": comp},
                     "expect": {"visible": "page.container"}}
                ]
            })
    return {"suite_id": f"{profile['operator'].upper()}-NAVIGATION", "operator": profile["operator"], "env": "real", "cases": cases}


def load_suite(operator, suite, profile):
    if suite == "navigation":
        return build_navigation_cases(profile)
    # 支持子目录套件（如 generated/vlan_bind），并防止路径穿越
    rel = suite.replace("\\", "/").strip("/")
    if not rel.endswith(".json"):
        rel += ".json"
    base = os.path.realpath(os.path.join(ROOT, "operators", operator, "cases"))
    path = os.path.realpath(os.path.join(base, rel))
    if not (path == base or path.startswith(base + os.sep)):
        raise SystemExit(f"invalid suite path: {suite}")
    if not os.path.exists(path):
        raise SystemExit(f"Suite file not found: {path}")
    data = load_json(path)
    # 兼容 generator 输出的裸 list 格式（仅含 cases）
    if isinstance(data, list):
        data = {
            "suite_id": f"{operator.upper()}-GEN",
            "operator": operator,
            "env": "real",
            "cases": data,
        }
    # 解析用例中 ${VAR} 占位符（如负向登录用例的有效用户名）
    resolve_config(data)
    return data


class StepRunner:
    """统一封装 Mock/Real 两种会话的 step 执行。"""

    def __init__(self, session, profile, selectors, report_dir):
        self.session = session
        self.profile = profile
        self.selectors = selectors
        self.report_dir = report_dir

    def run(self, step):
        action = step["action"]
        params = step.get("params", {})
        expect = step.get("expect", {})
        failures = []
        detail = None

        try:
            # 部分 action 返回额外信息（如 real.screenshot 返回截图路径），写入 result.detail
            detail = self._execute_action(action, params)
        except Exception as exc:
            failures.append(f"action {action} failed: {exc}")

        if not failures:
            failures.extend(self._check_expect(expect, params))

        result = {
            "action": action,
            "params": params,
            "status": "fail" if failures else "pass",
            "failures": failures,
        }
        if detail is not None:
            result["detail"] = detail
        return result

    def _execute_action(self, action, params):
        if action.startswith("real."):
            method = action.split(".", 1)[1]
            m = getattr(self.session, method)
            if method in ("login", "logout", "wait"):
                m(**params)
            elif method == "navigate":
                m(params.get("path", ""))
            elif method == "navigate_spa":
                m(params.get("route", ""))
            elif method == "fill":
                m(params["selector"], params["value"])
            elif method == "click":
                m(params["selector"])
            elif method == "click_menu":
                m(params.get("level", 1), params.get("title", ""))
            elif method == "wait_url":
                m(params.get("contains", ""))
            elif method == "assert_url_contains":
                # 兼容用例中常用的 contains / substring 两种参数名
                sub = params.get("substring") or params.get("contains", "")
                m(sub)
            elif method == "reload":
                m()
            elif method == "screenshot":
                path = m(params.get("name", "shot"))
                print(f"  screenshot -> {path}")
                return path
            elif method == "assert_page":
                m(params.get("component", ""))
            elif method == "assert_login_error":
                m()
            else:
                m(**params)
        else:
            # 旧 Mock/INTL 模式 action（如 page.login）
            self.session.execute_action(action, params)

    def _check_expect(self, expect, params):
        failures = []
        if not expect:
            return failures
        # Mock(WebSession) 旧风格 expect（text/non_empty/input_value/checked/toast 等）走旧断言引擎
        if isinstance(self.session, WebSession):
            try:
                failures.extend(assert_expect(self.session, expect))
            except Exception as exc:  # noqa: BLE001
                failures.append(f"expect error: {exc}")
            return failures
        # Real 风格 expect
        url_contains = expect.get("url_contains")
        if url_contains:
            if isinstance(url_contains, dict):
                for _k, sub in url_contains.items():
                    try:
                        self.session.assert_url_contains(sub)
                    except AssertionError as exc:
                        failures.append(str(exc))
            else:
                try:
                    self.session.assert_url_contains(url_contains)
                except AssertionError as exc:
                    failures.append(str(exc))
        visible = expect.get("visible")
        if visible is not None:
            keys = visible if isinstance(visible, (list, tuple)) else [visible]
            for key in keys:
                if key == "page.container":
                    try:
                        self.session.assert_page(params.get("component", ""))
                    except Exception as exc:
                        failures.append(f"page container {params.get('component')}: {exc}")
                else:
                    try:
                        self.session.assert_visible(key)
                    except Exception as exc:
                        failures.append(f"visible {key}: {exc}")
        hidden = expect.get("hidden")
        if hidden:
            keys = hidden if isinstance(hidden, (list, tuple)) else [hidden]
            for key in keys:
                try:
                    self.session.assert_visible(key)
                    failures.append(f"hidden {key}: element still visible")
                except Exception:
                    pass
        text_contains = expect.get("text_contains")
        if text_contains:
            items = text_contains.items() if isinstance(text_contains, dict) else \
                [(text_contains, None)] if isinstance(text_contains, str) else []
            for key, _sub in items:
                try:
                    self.session.assert_text_contains(key)
                except Exception as exc:
                    failures.append(f"text_contains {key}: {exc}")
        return failures


def run_suite(operator, env, suite, headed=False, browser="chromium", override_url=None):
    profile, selectors = load_profile(operator)
    profile["active_env"] = env
    if override_url:
        profile["env"][env]["base_url"] = override_url
    # WebSession(Mock/INTL) 仍读取顶层 base_url
    profile.setdefault("base_url", profile["env"][env]["base_url"])

    # ---------------- mock 兼容层：补齐旧 Page Object 需要的顶层键 ----------------
    if env == "mock":
        ecfg = profile["env"][env]
        profile.setdefault("auth", ecfg["auth"]["admin"])
        profile.setdefault("routes", {
            "login": "/login.html", "status": "/status.html", "wifi": "/wifi.html",
            "wan": "/wan.html", "lan": "/lan.html", "system": "/system.html",
            "upgrade": "/upgrade.html"})
        tmo = profile.setdefault("timeouts", {})
        tmo.setdefault("element_wait_seconds", tmo.get("element", 10000) / 1000)
        # mock UI 是共享的通用模拟器；若运营商 selectors 无 pages 结构，回退到 intl 的 pages
        if "pages" not in selectors:
            intl_sel = load_json(os.path.join(ROOT, "operators", "intl", "selectors.json"))
            selectors["pages"] = intl_sel.get("pages", {})

    suite_data = load_suite(operator, suite, profile)
    cases = suite_data["cases"]

    run_id = new_run_id(f"{operator}_{env}_{suite}")
    report_dir = os.path.join(ROOT, "reports", run_id)
    os.makedirs(os.path.join(report_dir, "screenshots"), exist_ok=True)

    mock_proc = None
    if env == "mock":
        # 端口已监听则复用（避免多次 runner 并发/串行 spawn 导致双绑定与状态不一致）
        ecfg = profile["env"].get("mock", {})
        _url = ecfg.get("base_url", "http://127.0.0.1:8090")
        _host, _port = _url.split("://")[-1].split(":")
        _port = int(_port.rstrip("/"))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _s:
            _s.settimeout(0.5)
            _already = _s.connect_ex((_host, _port)) == 0
        if not _already:
            cmd = [sys.executable, os.path.join(ROOT, "mock_web_ui", "server.py")]
            mock_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(2)
            print(f"[mock server started pid={mock_proc.pid}]")
        else:
            print(f"[mock server already running on {_host}:{_port}, reused]")

    start = time.time()
    results = []

    # ---------------------- navigation 特殊流程：单会话遍历所有 L3 菜单 ----------------------
    if suite == "navigation" and env == "real":
        session = RealWebSession(profile, selectors, report_dir=report_dir)
        session.start(headed=headed, browser_type=browser)
        login_path = profile["env"][env].get("login_path", "/login.html")

        def ensure_logged_in():
            if not getattr(session, "_logged_in", False) or session.is_login_page():
                session.navigate(login_path)
                session.login("admin")
                session._logged_in = True

        def collect_menu_items():
            menu_items = []
            l1s = session.page.evaluate("""() => [...document.querySelectorAll('#MenuArea_L1 > ul > li[id^="fhId_"]')].map(el => el.id)""")
            print(f"[navigation] L1 count: {len(l1s)}")
            for l1_id in l1s:
                session.page.locator(f"#{l1_id}").click()
                session.page.wait_for_timeout(800)
                l2s = session.page.evaluate("""() => [...document.querySelectorAll('#MenuArea_L2 > ul > li[id^="fhId_"]')].map(el => el.id)""")
                for l2_id in l2s:
                    session.page.locator(f"#{l2_id}").click()
                    session.page.wait_for_timeout(800)
                    l3s = session.page.evaluate("""() => [...document.querySelectorAll('#panel_sidebar > ul > li[id^="fhId_"]')].map(el => ({id: el.id, text: el.innerText.trim().replace(/\\s+/g, ' ')}))""")
                    for l3 in l3s:
                        menu_items.append({"l1": l1_id, "l2": l2_id, **l3})
            return menu_items

        ensure_logged_in()
        menu_items = collect_menu_items()
        print(f"[navigation] discovered {len(menu_items)} L3 menu items")

        for idx, item in enumerate(menu_items, 1):
            case_id = f"TC-NAV-{idx:03d}-{item['id']}"
            print(f"[{case_id}] {item['text']}")
            step_results = []
            case_status = "pass"
            try:
                ensure_logged_in()
                # 重新展开 L1/L2, 确保 L3 可见且可点击
                session.page.locator(f"#{item['l1']}").click()
                session.page.wait_for_timeout(800)
                session.page.locator(f"#{item['l2']}").click()
                session.page.wait_for_timeout(800)
                session.page.locator(f"#{item['id']}").click()
                session.page.wait_for_timeout(profile["timeouts"].get("page_load_extra", 2500))
                shot = session.screenshot(f"nav_{item['id']}")
                # 页面渲染断言：与 regression 的 assert_page 标准一致。
                # 部分页面（帮助/状态/固件升级等）正常渲染但内容不含 fhId_* 元素，
                # 故不能以 fhCount>0 为准，改用 #el_main 可见 + 内容长度判断。
                render = session.page.evaluate("""() => {
                    const main = document.querySelector('#el_main');
                    if (!main || main.offsetParent === null) return {ok: false, reason: 'el_main not visible'};
                    const textLen = (main.innerText || '').trim().length;
                    const htmlLen = main.innerHTML.length;
                    const fhCount = main.querySelectorAll('[id^="fhId_"]').length;
                    return {ok: textLen >= 5 || htmlLen >= 200, reason: `textLen=${textLen} htmlLen=${htmlLen} fhCount=${fhCount}`};
                }""")
                if not render["ok"]:
                    raise AssertionError(f"el_main render check failed: {render['reason']}")
                step_results.append({"action": "navigate", "status": "pass", "failures": [], "detail": f"url={session.page.evaluate('() => location.hash')}"})
                step_results.append({"action": "screenshot", "status": "pass", "failures": [], "detail": shot})
                step_results.append({"action": "assert_rendered", "status": "pass", "failures": [], "detail": render["reason"]})
            except Exception as exc:
                case_status = "fail"
                step_results.append({"action": "navigate_or_assert", "status": "fail", "failures": [str(exc)]})
                shot = os.path.join(report_dir, "screenshots", f"FAIL_{case_id}.png")
                try:
                    session.page.screenshot(path=shot, full_page=False)
                except Exception:
                    pass
            results.append({
                "id": case_id,
                "title": item["text"],
                "module": "Navigation",
                "priority": "P0",
                "status": case_status,
                "steps": step_results,
                "screenshot": None,
            })
        session.close()
    else:
        # ---------------------- 标准流程 ----------------------
        # real 非 regression 套件复用同一会话，降低设备登录压力；
        # regression 因包含负向登录/角色切换，保持每用例独立 session。
        shared_real = (env == "real" and suite != "regression")
        real_session = None
        if shared_real:
            real_session = RealWebSession(profile, selectors, report_dir=report_dir)
            real_session.start(headed=headed, browser_type=browser)
            login_path = profile["env"][env].get("login_path", "/login.html")
            real_session.navigate(login_path)
            real_session.login("admin")
            real_session._logged_in = True

        for case in cases:
            case_id = case["id"]
            print(f"[{case_id}] {case['title']}")

            if env == "real":
                if shared_real:
                    session = real_session
                    # 若上一用例已退出（如 logout 用例），重新登录
                    if not getattr(session, "_logged_in", False):
                        session.navigate(login_path)
                        session.login("admin")
                        session._logged_in = True
                else:
                    session = RealWebSession(profile, selectors, report_dir=report_dir)
                    session.start(headed=headed, browser_type=browser)
            else:
                session = WebSession(profile, selectors)

            runner = StepRunner(session, profile, selectors, report_dir)
            step_results = []
            case_status = "pass"

            for step in case["steps"]:
                # 每用例独立 session 时，除 navigate/login 外若未登录先自动登录
                # 若用例显式禁用自动登录（如负向登录测试），则跳过
                auto_login_disabled = case.get("auto_login") is False
                if (not shared_real and not auto_login_disabled and
                        step["action"] not in ("real.navigate", "real.login") and
                        env == "real" and not getattr(session, "_logged_in", False)):
                    session.navigate(profile["env"][env].get("login_path", "/login.html"))
                    session.login("admin")
                    session._logged_in = True

                result = runner.run(step)
                step_results.append(result)
                if result["status"] == "fail":
                    case_status = "fail"
                    break
                if step["action"] == "real.login":
                    session._logged_in = True
                if step["action"] == "real.logout":
                    session._logged_in = False

            screenshot = None
            if case_status == "fail" and env == "real":
                shot_path = os.path.join(report_dir, "screenshots", f"FAIL_{case_id}.png")
                try:
                    session.page.screenshot(path=shot_path, full_page=False)
                    screenshot = os.path.relpath(shot_path, report_dir)
                except Exception:
                    pass

            if not shared_real:
                session.close()

            results.append({
                "id": case_id,
                "title": case["title"],
                "module": case.get("module", ""),
                "priority": case.get("priority", ""),
                "status": case_status,
                "steps": step_results,
                "screenshot": screenshot,
            })

        if shared_real and real_session:
            real_session.close()

    if mock_proc:
        mock_proc.terminate()
        try:
            mock_proc.wait(timeout=3)
        except Exception:
            mock_proc.kill()

    duration = round(time.time() - start, 2)
    passed = sum(1 for r in results if r["status"] == "pass")
    report = {
        "run_id": run_id,
        "suite_id": suite_data.get("suite_id", ""),
        "title": f"{operator.upper()} {env} {suite}",
        "operator": operator,
        "env": env,
        "suite": suite,
        "profile": profile.get("name"),
        "browser": browser,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {"total": len(results), "passed": passed,
                    "failed": len(results) - passed, "duration_seconds": duration},
        "cases": results,
    }
    out_dir = write_reports(report, screenshot_dir=os.path.join(report_dir, "screenshots"))
    print(f"\nReport written to {out_dir}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return report


def main():
    parser = argparse.ArgumentParser(description="QCoder Web UI AutoTest runner (operator-aware)")
    parser.add_argument("--operator", required=True, choices=["cm", "intl"],
                        help="Operator profile (cm/intl)")
    parser.add_argument("--env", default="real", choices=["real", "mock"],
                        help="Test environment: real device or mock UI")
    parser.add_argument("--suite", required=True,
                        help="Test suite: smoke / regression / navigation / full / generated/<name>")
    parser.add_argument("--headed", action="store_true",
                        help="Run with visible browser window")
    parser.add_argument("--browser", default="chromium", choices=["chromium", "firefox", "webkit"],
                        help="Browser engine")
    parser.add_argument("--url", default=None,
                        help="Override base_url from profile")
    parser.add_argument("--admin-user", default=None,
                        help="Override admin username")
    parser.add_argument("--admin-pass", default=None,
                        help="Override admin password")
    args = parser.parse_args()

    report = run_suite(args.operator, args.env, args.suite,
                       headed=args.headed, browser=args.browser,
                       override_url=args.url)
    sys.exit(0 if report["summary"]["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
