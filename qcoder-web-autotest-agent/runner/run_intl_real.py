#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INTL 国际版真机 E2E 测试执行器
目标设备: http://192.168.1.1 (HG6163FC1 国际版)
架构: login.html 独立登录页 + main.html#/... SPA (ElementUI)

用法:
  python runner/run_intl_real.py --suite login|wan|status|reboot|all [--headful] [--out DIR]
"""
import argparse
import json
import os
import re
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, ROOT)

from core.config import load_dotenv, resolve_env_value  # noqa: E402

load_dotenv()  # 从工程根 .env 注入 QCT_INTL_* 等凭据（.env 不入库）

BASE_URL = os.environ.get("QCT_INTL_BASE_URL", "http://192.168.1.1")
ADMIN_USER = os.environ.get("QCT_INTL_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("QCT_INTL_ADMIN_PASS", "")  # 无默认值：缺失即空串
USER_PASS = os.environ.get("QCT_INTL_USER_PASS", "")    # 同上，真机登录前须在 .env 配置

SEL = json.load(open(os.path.join(ROOT, "operators", "intl", "selectors_real.json"), encoding="utf-8"))


def resolve_sel(key):
    """支持 'login.username' 或原始 CSS 选择器"""
    if key.startswith(("#", ".", "[", ":")):
        return key
    parts = key.split(".")
    node = SEL
    for p in parts:
        if isinstance(node, dict) and p in node:
            node = node[p]
        else:
            return None
    return node if isinstance(node, str) else None


class IntlSession:
    def __init__(self, page, out_dir):
        self.page = page
        self.out_dir = out_dir
        self._dialogs = []
        self._unauthorized = False
        page.on("dialog", lambda d: (self._dialogs.append(d.message), d.accept()))
        page.on("response", self._on_response)

    def _on_response(self, resp):
        if resp.status in (401, 403):
            self._unauthorized = True

    # ---------- 基础操作 ----------
    def navigate(self, path):
        url = BASE_URL if path in ("/", "") else BASE_URL + path
        self.page.goto(url, timeout=20000, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2500)

    def navigate_spa(self, route):
        self.page.goto(f"{BASE_URL}/main.html#{route}", timeout=20000, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2500)

    def click_menu(self, l1=None, l2=None, l3=None):
        if l1:
            self.page.click(f"#{l1}", timeout=8000)
            self.page.wait_for_timeout(1200)
        if l2:
            self.page.click(f"#{l2}", timeout=8000)
            self.page.wait_for_timeout(2000)
        if l3:
            self.page.click(f"#{l3}", timeout=8000)
            self.page.wait_for_timeout(2000)

    def fill(self, selector, value):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        loc.fill(resolve_env_value(value))

    def click(self, selector):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        loc.click()

    def wait(self, ms):
        self.page.wait_for_timeout(int(ms))

    # ---------- 登录/登出 ----------
    def login(self, role="admin", expect=True):
        username = ADMIN_USER if role == "admin" else "user"
        password = ADMIN_PASS if role == "admin" else USER_PASS
        self.page.fill("#user_name", username)
        self.page.fill("#loginpp", password)
        self.page.click("#login_btn")
        self.page.wait_for_timeout(3000)
        if expect:
            self.page.wait_for_url(re.compile(r"main\.html#/"), timeout=15000)
            return True
        else:
            return "/login.html" in self.page.url

    def logout(self):
        try:
            self.page.click(".el-dropdown-link.header_admin", timeout=8000)
            self.page.wait_for_timeout(1000)
            self.page.click("#fhId_logout", timeout=8000)
            self.page.wait_for_timeout(1500)
            # 处理退出确认框
            box = self.page.locator(".el-message-box")
            if box.count() and box.first.is_visible():
                box.locator("button").last.click()
                self.page.wait_for_timeout(2500)
            self.page.wait_for_url(re.compile(r"login\.html"), timeout=15000)
        except Exception:
            self.page.goto(f"{BASE_URL}/login.html", timeout=15000)
            self.page.wait_for_timeout(1500)

    # ---------- 断言 ----------
    def assert_visible(self, selector):
        sel = resolve_sel(selector) or selector
        self.page.locator(sel).wait_for(state="visible", timeout=8000)
        return True

    def assert_hidden(self, selector):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        if loc.count() == 0:
            return True
        try:
            loc.wait_for(state="hidden", timeout=5000)
            return True
        except PWTimeout:
            return False

    def assert_url_contains(self, substring):
        self.page.wait_for_url(re.compile(re.escape(substring)), timeout=10000)
        return True

    def assert_input_value(self, selector, value):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        return str(loc.input_value()) == str(value)

    def assert_input_value_not(self, selector, value):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        return str(loc.input_value()) != str(value)

    def assert_text_contains(self, selector, text):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        return text in (loc.inner_text() or "")

    def assert_text_not_contains(self, selector, text):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        return text not in (loc.inner_text() or "")

    def assert_login_error(self):
        err = self.page.locator("#login_error_hint")
        err.wait_for(state="visible", timeout=8000)
        return True

    def assert_login_stays(self):
        # 空用户名/空密码等前端校验拦截：停留登录页且错误提示隐藏
        if "/login.html" not in self.page.url:
            return False
        err = self.page.locator("#login_error_hint")
        if err.count() == 0:
            return True
        return not err.first.is_visible()

    def assert_element(self, selector):
        return self.assert_visible(selector)

    def assert_page(self, component="main"):
        self.page.locator("#app").wait_for(state="visible", timeout=8000)
        return True

    # ---------- 下拉 ----------
    def select_option(self, selector, option_text):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        loc.click()
        self.page.wait_for_timeout(800)
        # 用 filter(visible=True) 基于 is_visible() 精确过滤，避免多下拉框页面
        # （如日志页 LogLevel/LogViewLevel 共用下拉面板）匹配到隐藏面板的同名选项
        opt = self.page.locator(".el-select-dropdown__item").filter(has_text=option_text).filter(visible=True)
        opt.first.wait_for(state="visible", timeout=5000)
        opt.first.click()
        self.page.wait_for_timeout(500)
        return True

    def assert_option_present(self, selector, option_text):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        loc.click()
        self.page.wait_for_timeout(800)
        opts = self.page.locator(".el-select-dropdown__item")
        texts = [o.inner_text().strip() for o in opts.all() if o.is_visible()]
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(400)
        return option_text in texts

    # ---------- 确认框 ----------
    def assert_confirm_visible(self, keyword=""):
        box = self.page.locator(".el-message-box")
        box.wait_for(state="visible", timeout=8000)
        if keyword:
            return keyword in (box.inner_text() or "")
        return True

    def click_confirm(self, accept=True):
        box = self.page.locator(".el-message-box")
        box.wait_for(state="visible", timeout=8000)
        btns = box.locator("button")
        if accept:
            btns.last.click()
        else:
            btns.nth(btns.count() - 2).click()
        self.page.wait_for_timeout(1500)
        return True

    def assert_confirm_hidden(self):
        box = self.page.locator(".el-message-box")
        if box.count() == 0:
            return True
        try:
            box.wait_for(state="hidden", timeout=5000)
            return True
        except PWTimeout:
            return False

    # ---------- 其它 ----------
    def evaluate(self, script):
        return self.page.evaluate(script)

    def screenshot(self, name):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, f"{name}.png")
        self.page.screenshot(path=path, full_page=True)
        return path

    def no_dialog(self):
        return len(self._dialogs) == 0

    def assert_unauthorized(self):
        # 未登录访问受保护页面时，数据接口应返回 401/403
        return self._unauthorized

    def assert_unauth_redirect(self):
        # 未登录访问受保护页面：应跳转登录页（URL 含 login.html 或登录表单可见）
        self.page.wait_for_timeout(2500)
        if "/login.html" in self.page.url:
            return True
        if self.page.locator("#user_name").count() and self.page.locator("#user_name").first.is_visible():
            return True
        # 兜底：未跳转则视为未授权保护失效（记录为失败，暴露安全弱项）
        return False

    # ---------- 端口绑定（复选框） ----------
    def _is_checked(self, selector):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        return loc.first.evaluate("el => el.classList.contains('is-checked')")

    def check(self, selector):
        if not self._is_checked(selector):
            self.click(selector)
        return True

    def uncheck(self, selector):
        if self._is_checked(selector):
            self.click(selector)
        return True

    def assert_checked(self, selector):
        return self._is_checked(selector) is True

    def assert_unchecked(self, selector):
        return self._is_checked(selector) is False

    # ---------- WAN 清理 ----------
    def cleanup_wan(self):
        """删除宽带设置页面中所有 WAN 连接，保证用例起始状态干净。
        返回删除的 WAN 数量。若页面不在宽带设置页，先尝试导航过去。"""
        page = self.page
        # 确保在宽带设置页面
        try:
            if page.locator("#fhId_broadBandSettings_L2").count() == 0:
                page.click("#fhId_network_L1", timeout=8000)
                page.wait_for_timeout(1200)
                page.click("#fhId_broadBandSettings_L2", timeout=8000)
                page.wait_for_timeout(2500)
        except Exception:
            pass
        deleted = 0
        # 关闭任何残留的提示/警告框（如"最多4条路由"警告），避免其干扰后续删除确认框
        try:
            for _ in range(3):
                box = page.locator(".el-message-box")
                if box.count() and box.first.is_visible():
                    btns = box.locator(".el-message-box__btns button").all()
                    if btns:
                        btns[-1].click()
                        page.wait_for_timeout(1000)
                    else:
                        break
                else:
                    break
        except Exception:
            pass
        # 若 Add 表单处于打开状态，先点击 Add 切换回列表视图，避免表单遮挡干扰删除
        try:
            if page.locator("#fhId_onApply").count() and page.locator("#fhId_onApply").is_visible():
                page.click("#fhId_Add", timeout=5000)
                page.wait_for_timeout(1200)
        except Exception:
            pass
        # 反复扫描列表，直到没有 WAN 项为止
        for _ in range(20):
            items = page.locator("li[id^='fhId_Wan']").all()
            if not items:
                items = page.locator("li:has(.del_wan_icon)").all()
            if not items:
                break
            # 取第一个 WAN 项
            item = items[0]
            try:
                item.click()
                page.wait_for_timeout(600)
            except Exception:
                pass
            del_icon = item.locator(".del_wan_icon")
            if del_icon.count() == 0:
                # 尝试通过列表内删除按钮
                del_icon = page.locator("li:has(.del_wan_icon) .del_wan_icon").first
            try:
                del_icon.click(timeout=5000)
            except Exception:
                break
            # 确认删除：优先点 message-box 中的"确定/OK"按钮
            try:
                box = page.locator(".el-message-box")
                if box.count() and box.first.is_visible():
                    btns = box.locator(".el-message-box__btns button").all()
                    target = None
                    for b in btns:
                        t = (b.inner_text() or "").strip().lower()
                        if t in ("ok", "确定", "yes", "确认", "delete", "删除"):
                            target = b
                            break
                    if target is None and btns:
                        target = btns[-1]
                    if target is not None:
                        target.click()
                    page.wait_for_timeout(2500)
                else:
                    page.wait_for_timeout(1500)
            except Exception:
                page.wait_for_timeout(1500)
            deleted += 1
        # 删除完成后重新导航刷新列表，确保 body 文本更新
        try:
            page.click("#fhId_network_L1", timeout=8000)
            page.wait_for_timeout(1200)
            page.click("#fhId_broadBandSettings_L2", timeout=8000)
            page.wait_for_timeout(2500)
        except Exception:
            pass
        # 轮询等待 body 不再包含任何 WAN 项文本，确保删除完全生效
        try:
            for _ in range(10):
                body_txt = page.locator("body").inner_text()
                if "VID_" not in body_txt and "INTERNET_R_" not in body_txt:
                    break
                page.wait_for_timeout(1000)
        except Exception:
            pass
        return True


ACTION_MAP = {
    "real.navigate": lambda s, a: s.navigate(a["path"]),
    "real.navigate_spa": lambda s, a: s.navigate_spa(a["route"]),
    "real.login": lambda s, a: s.login(a.get("role", "admin"), a.get("expect", True)),
    "real.logout": lambda s, a: s.logout(),
    "real.fill": lambda s, a: s.fill(a["selector"], a["value"]),
    "real.click": lambda s, a: s.click(a["selector"]),
    "real.wait": lambda s, a: s.wait(a["ms"]),
    "real.click_menu": lambda s, a: s.click_menu(a.get("l1"), a.get("l2"), a.get("l3")),
    "real.assert_visible": lambda s, a: s.assert_visible(a["selector"]),
    "real.assert_hidden": lambda s, a: s.assert_hidden(a["selector"]),
    "real.assert_url_contains": lambda s, a: s.assert_url_contains(a["substring"]),
    "real.assert_input_value": lambda s, a: s.assert_input_value(a["selector"], a["value"]),
    "real.assert_input_value_not": lambda s, a: s.assert_input_value_not(a["selector"], a["value"]),
    "real.assert_text_contains": lambda s, a: s.assert_text_contains(a["selector"], a["text"]),
    "real.assert_text_not_contains": lambda s, a: s.assert_text_not_contains(a["selector"], a["text"]),
    "real.assert_login_error": lambda s, a: s.assert_login_error(),
    "real.assert_login_stays": lambda s, a: s.assert_login_stays(),
    "real.assert_page": lambda s, a: s.assert_page(a.get("component", "main")),
    "real.assert_element": lambda s, a: s.assert_element(a["selector"]),
    "real.select_option": lambda s, a: s.select_option(a["selector"], a["option_text"]),
    "real.assert_option_present": lambda s, a: s.assert_option_present(a["selector"], a["option_text"]),
    "real.assert_confirm_visible": lambda s, a: s.assert_confirm_visible(a.get("keyword", "")),
    "real.click_confirm": lambda s, a: s.click_confirm(a.get("accept", True)),
    "real.assert_confirm_hidden": lambda s, a: s.assert_confirm_hidden(),
    "real.evaluate": lambda s, a: s.evaluate(a["script"]),
    "real.screenshot": lambda s, a: s.screenshot(a["name"]),
    "real.no_dialog": lambda s, a: s.no_dialog(),
    "real.assert_unauthorized": lambda s, a: s.assert_unauthorized(),
    "real.assert_unauth_redirect": lambda s, a: s.assert_unauth_redirect(),
    "real.check": lambda s, a: s.check(a["selector"]),
    "real.uncheck": lambda s, a: s.uncheck(a["selector"]),
    "real.assert_checked": lambda s, a: s.assert_checked(a["selector"]),
    "real.assert_unchecked": lambda s, a: s.assert_unchecked(a["selector"]),
    "real.cleanup_wan": lambda s, a: s.cleanup_wan(),
}


def run_case(session, case, out_dir):
    case_id = case.get("id", "case")
    steps = case.get("steps", [])
    result = {
        "id": case_id,
        "title": case.get("title", ""),
        "priority": case.get("priority", "P1"),
        "tags": case.get("tags", []),
        "status": "PASS",
        "steps": [],
        "error": None,
        "start": datetime.now().isoformat(),
    }
    for i, step in enumerate(steps):
        action = step.get("action")
        desc = step.get("desc", "")
        step_result = {"index": i + 1, "action": action, "desc": desc, "status": "PASS", "error": None}
        try:
            if action in ACTION_MAP:
                ok = ACTION_MAP[action](session, step)
                if ok is False:
                    raise AssertionError(f"action {action} returned False")
                # screenshot 动作：把截图路径记录到 detail（供报告嵌入）
                if action == "real.screenshot" and isinstance(ok, str):
                    step_result["detail"] = ok
            else:
                raise AssertionError(f"unknown action: {action}")
        except Exception as e:
            step_result["status"] = "FAIL"
            step_result["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            result["status"] = "FAIL"
            result["error"] = f"step {i + 1} [{action}]: {type(e).__name__}: {str(e)[:300]}"
            try:
                step_result["screenshot"] = session.screenshot(f"FAIL_{case_id}_{i + 1}")
            except Exception:
                pass
            result["steps"].append(step_result)
            break
        result["steps"].append(step_result)
    result["end"] = datetime.now().isoformat()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="all", help="login|wan|status|reboot|all")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "reports", "intl_real"))
    args = ap.parse_args()

    cases_dir = os.path.join(ROOT, "operators", "intl", "cases", "real")
    suites = {
        "login": "login.json",
        "wan": "wan.json",
        "status": "status.json",
        "reboot": "reboot.json",
        "security": "security.json",
        "wifi": "wifi.json",
        "lan": "lan.json",
        "nat": "nat.json",
        "firewall": "firewall.json",
        "account": "account.json",
        "remote": "remote.json",
        "voip": "voip.json",
        "auth": "auth.json",
        "ddos": "ddos.json",
        "web": "web.json",
        "vpn": "vpn.json",
        "ddns": "ddns.json",
        "media": "media.json",
        "upnp": "upnp.json",
        "ntp": "ntp.json",
        "diag": "diag.json",
        "log": "log.json",
        "topology": "topology.json",
        "help": "help.json",
    }
    if args.suite == "all":
        # 隔离易产生副作用的套件，避免级联失败：
        #  - login.json 的 LOGIN-008 触发账号锁定（1 分钟），会波及其后所有套件登录
        #  - lan.json 修改 DHCP 租约/DNS 触发设备网络重启，会波及其后所有套件
        # 故将 login.json 与 lan.json 置于全量回归最后，使其副作用不影响其它套件。
        files = ["status.json", "wan.json", "reboot.json",
                 "wifi.json", "nat.json", "firewall.json", "account.json",
                 "remote.json", "voip.json", "auth.json", "ddos.json", "web.json",
                 "vpn.json", "ddns.json", "media.json", "upnp.json", "ntp.json",
                 "diag.json", "log.json", "topology.json", "help.json", "lan.json", "login.json"]
    else:
        files = [suites[args.suite]]

    all_cases = []
    for f in files:
        p = os.path.join(cases_dir, f)
        if os.path.exists(p):
            all_cases.extend(json.load(open(p, encoding="utf-8")))

    os.makedirs(args.out, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(args.out, ts)
    os.makedirs(out_dir, exist_ok=True)

    summary = {"total": 0, "pass": 0, "fail": 0, "cases": [], "start": datetime.now().isoformat()}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        for case in all_cases:
            summary["total"] += 1
            # 每个用例使用独立 context，隔离会话与 cookie
            context = browser.new_context(viewport={"width": 1600, "height": 900})
            page = context.new_page()
            session = IntlSession(page, out_dir)
            try:
                res = run_case(session, case, out_dir)
            except Exception as e:
                res = {"id": case.get("id"), "title": case.get("title"), "status": "ERROR",
                       "error": str(e)[:300], "steps": []}
            # 成功用例若未显式截图，自动补一张成果截图
            if res["status"] == "PASS":
                has_shot = any(st.get("detail") for st in res.get("steps", []))
                if not has_shot:
                    try:
                        shot = session.screenshot(f"OK_{case.get('id','case')}")
                        step = {"index": len(res.get("steps", [])) + 1, "action": "real.screenshot",
                                "desc": "用例成果截图", "status": "PASS", "detail": shot}
                        res.setdefault("steps", []).append(step)
                    except Exception:
                        pass
            context.close()
            summary["cases"].append(res)
            if res["status"] == "PASS":
                summary["pass"] += 1
            else:
                summary["fail"] += 1
            print(f"[{res['status']}] {res['id']} - {res['title']}")
            if res.get("error"):
                print(f"    -> {res['error']}")
        browser.close()

    summary["end"] = datetime.now().isoformat()
    summary["pass_rate"] = round(summary["pass"] / summary["total"] * 100, 1) if summary["total"] else 0
    result_file = os.path.join(out_dir, "result.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n=== INTL 真机测试完成 ===")
    print(f"总数: {summary['total']}  通过: {summary['pass']}  失败: {summary['fail']}  通过率: {summary['pass_rate']}%")
    print(f"结果: {result_file}")
    return summary


if __name__ == "__main__":
    main()
