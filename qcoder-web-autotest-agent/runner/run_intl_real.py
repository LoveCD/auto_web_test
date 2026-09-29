#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INTL 国际版真机 E2E 测试执行器 —— 新 UI（SPA）专用
目标设备: HG6142HT / HG6163FC1 等国际版网关（login.html 独立登录页 + main.html#/... SPA，ElementUI）
用例目录: operators/intl/cases/real/new_ui/（24 套件）

用法:
  python runner/run_intl_real.py --suite login|wan|status|reboot|all [--scheme <协议>] [--headful] [--out DIR]
  --scheme 支持自然语言描述是否走 HTTPS/HTTP，如 "https加密访问"、"http明文"、"自动探测"；
           默认 auto：自动探测设备可达协议（HTTPS 优先，自签证书自动忽略校验）。

老 UI（HTML 多页版）用例请使用独立执行器: runner/run_intl_real_html.py
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
USER_USER = os.environ.get("QCT_INTL_USER_USER", "user")
USER_PASS = os.environ.get("QCT_INTL_USER_PASS", "")    # 同上，真机登录前须在 .env 配置


# ---------- 访问协议（HTTP/HTTPS）选择：支持自然语言描述 ----------
def set_base_url(url):
    """运行期更新模块级 BASE_URL（SPA 路由/登录页跳转均引用它）"""
    global BASE_URL
    BASE_URL = url.rstrip("/")


def parse_scheme(text):
    """自然语言解析访问协议: 返回 'https' | 'http' | 'auto'

    支持: "https" / "https加密" / "安全" / "tls" / "ssl" -> https
          "http" / "明文" / "不加密" / "非加密"          -> http
          "自动" / "auto" / "都支持" / 空                -> auto（探测，HTTPS 优先）
    """
    if not text:
        return "auto"
    t = str(text).strip().lower()
    if not t:
        return "auto"
    if any(k in t for k in ("auto", "自动", "都支持", "都可以", "both", "探测")):
        return "auto"
    # https 关键词先判（避免 'http' 子串误命中 'https'）
    if any(k in t for k in ("https", "加密", "安全", "tls", "ssl", "证书")):
        return "https"
    if any(k in t for k in ("http", "明文", "不加密", "非加密", "普通")):
        return "http"
    return "auto"


def probe_scheme(host):
    """探测设备实际可达协议：HTTPS 优先（自签证书忽略校验），失败回退 HTTP"""
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for scheme in ("https", "http"):
        try:
            req = urllib.request.Request(f"{scheme}://{host}/login.html", method="GET")
            resp = urllib.request.urlopen(req, timeout=6, context=ctx if scheme == "https" else None)
            if resp.status in (200, 301, 302, 401, 403):
                return scheme
        except Exception:
            continue
    return None


def resolve_base_url(scheme_text):
    """按自然语言协议描述解析最终 BASE_URL；auto 时自动探测"""
    m = re.match(r"^(?:https?://)?([^/]+)", BASE_URL)
    host = m.group(1) if m else "192.168.1.1"
    scheme = parse_scheme(scheme_text)
    if scheme == "auto":
        detected = probe_scheme(host)
        if not detected:
            print("[WARN] 自动探测失败（HTTPS/HTTP 均不可达），回退 HTTP")
            detected = "http"
        scheme = detected
        print(f"[SCHEME] 自动探测: 使用 {scheme.upper()} 访问 {host}")
    else:
        print(f"[SCHEME] 指定协议: 使用 {scheme.upper()} 访问 {host}")
    set_base_url(f"{scheme}://{host}")
    return BASE_URL


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
        username = ADMIN_USER if role == "admin" else USER_USER
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
        err = self.page.locator("#login_error_hint, .login_error_hint")
        err.wait_for(state="visible", timeout=8000)
        return True

    def assert_login_stays(self):
        # 空用户名/空密码等前端校验拦截：停留登录页且错误提示隐藏
        if "/login.html" not in self.page.url:
            return False
        err = self.page.locator("#login_error_hint, .login_error_hint")
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

    # 关闭表单/弹窗对话框（WAN 添加表单等）。
    # 老 UI 的 WAN 添加表单为页面内嵌表单（无 el-dialog），关闭用 #fhId_Cancel；
    # Element UI 弹窗用 .el-dialog__headerbtn/.el-dialog__close；兜底按 Escape。
    def close_dialog(self):
        for sel in ("#fhId_Cancel", ".el-dialog__headerbtn", ".el-dialog__close",
                    ".el-dialog__header-close", ".modal_close", ".close_btn"):
            loc = self.page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                self.page.wait_for_timeout(500)
                return True
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        return True

    def close_boxes(self):
        """容错：循环关闭页面上所有残留弹窗/提示（模态遮罩会拦截后续点击）。
        覆盖 Element UI message-box / dialog / message 及常见自定义弹层，
        最多 5 轮直到无可见弹窗。返回是否清干净。"""
        for _ in range(5):
            cleaned = False
            # 1) Element UI 确认框（.el-message-box）：点最后一个按钮（确定/OK）
            boxes = self.page.locator(".el-message-box")
            for i in range(boxes.count()):
                b = boxes.nth(i)
                if b.is_visible():
                    btns = b.locator("button").all()
                    if btns:
                        btns[-1].click()
                        self.page.wait_for_timeout(600)
                        cleaned = True
            if boxes.count() and cleaned:
                continue
            # 2) Element UI 对话框关闭按钮
            for sel in (".el-dialog__headerbtn", ".el-dialog__close", ".el-dialog__header-close"):
                loc = self.page.locator(sel)
                for i in range(loc.count()):
                    el = loc.nth(i)
                    if el.is_visible():
                        el.click()
                        self.page.wait_for_timeout(500)
                        cleaned = True
            if cleaned:
                continue
            # 3) Element UI message 提示（右上角小气泡）关闭
            for sel in (".el-message__closeBtn", ".el-notification__closeBtn"):
                loc = self.page.locator(sel)
                for i in range(loc.count()):
                    el = loc.nth(i)
                    if el.is_visible():
                        el.click()
                        self.page.wait_for_timeout(300)
                        cleaned = True
            if cleaned:
                continue
            # 4) 兜底：Escape 关闭
            any_visible = any(
                self.page.locator(sel).count() and self.page.locator(sel).first.is_visible()
                for sel in (".el-message-box", ".el-dialog", ".el-message", ".modal_mask", ".ui-dialog")
            )
            if any_visible:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
                cleaned = True
            if not cleaned:
                break
        self.page.wait_for_timeout(500)
        return True

    def _find_wan_table(self):
        """定位 WAN 列表数据表格（兼容老 UI 多页版与 SPA 新 UI）。
        SPA 新 UI 用 #fhId_wanTable；老 UI 多页版是两个独立 table，数据表含
        INTERNET/TR069/VOIP 行且行末有 checkbox。"""
        page = self.page
        table = page.locator("#fhId_wanTable")
        if table.count() and table.first.is_visible():
            return table.first
        best = None
        best_score = -1
        all_tables = page.locator("table")
        for i in range(all_tables.count()):
            t = all_tables.nth(i)
            try:
                if not t.is_visible():
                    continue
            except Exception:
                continue
            rows = t.locator("tr")
            score = 0
            for j in range(rows.count()):
                try:
                    r = rows.nth(j)
                    txt = (r.inner_text() or "").replace("\n", " ")
                except Exception:
                    continue
                if any(k in txt for k in ("INTERNET", "TR069", "VOIP")):
                    score += 10
                if r.locator("input[type=checkbox]").count():
                    score += 1
            if score > best_score:
                best_score = score
                best = t
        return best

    # ---------- WAN 列表行删除（老 UI 表格） ----------
    def delete_wan_row(self):
        """老 UI（HTML 多页版）WAN 表格行删除：
        勾选列表第一行（checkbox/radio 优先，其次点击行本身），再点击表格 Delete 按钮。
        用例前置已创建目标 WAN 并处于宽带设置页；删除确认框由后续
        assert_confirm_visible / click_confirm 步骤处理。"""
        page = self.page
        # 确保在宽带设置页
        try:
            if page.locator("#fhId_broadBandSettings_L2").count() == 0:
                page.click("#fhId_network_L1", timeout=8000)
                page.wait_for_timeout(1200)
                page.click("#fhId_broadBandSettings_L2", timeout=8000)
                page.wait_for_timeout(2500)
        except Exception:
            pass
        # 先关闭残留弹窗，避免模态遮罩拦截勾选/删除点击
        self.close_boxes()
        # 1) 定位 WAN 列表数据表格（老 UI 多页版 table 不含 id，按内容打分）
        table = self._find_wan_table()
        if not table:
            raise AssertionError("delete_wan_row: 未找到 WAN 表格")
        # 2) 勾选第一行：行内 checkbox/radio 优先，其次点击行本身
        picked = False
        if table.count() and table.is_visible():
            rows = table.locator("tbody tr")
            if rows.count() == 0:
                rows = table.locator("tr")
            if rows.count():
                row = rows.first
                # 行内单选/复选控件（Element UI 老 UI 隐藏 input，优先点击 label）
                for sel in (".el-checkbox", ".el-radio", ".el-checkbox__input", ".el-radio__input"):
                    cb = row.locator(sel)
                    if cb.count() and cb.first.is_visible():
                        try:
                            cb.first.click()
                        except Exception:
                            cb.first.click(force=True)
                        page.wait_for_timeout(500)
                        picked = True
                        break
                if not picked:
                    for sel in ("input[type=checkbox]", "input[type=radio]"):
                        cb = row.locator(sel)
                        if cb.count() and cb.first.is_visible():
                            try:
                                cb.first.check()
                            except Exception:
                                cb.first.click(force=True)
                            page.wait_for_timeout(500)
                            picked = True
                            break
                if not picked:
                    # 兜底：JS 勾选隐藏 input 并触发 change 事件
                    hidden = row.locator("input[type=checkbox]").first
                    if hidden.count():
                        hidden.evaluate(
                            "el => { el.checked = true; "
                            "el.dispatchEvent(new Event('change', { bubbles: true })); }"
                        )
                        page.wait_for_timeout(500)
                        picked = True
                if not picked:
                    row.click()
                    page.wait_for_timeout(500)
                    picked = True
        if not picked:
            # 3) 兜底：li 列表结构（与 cleanup_wan 一致的旧容器）
            items = page.locator("li[id^='fhId_Wan']").all()
            if not items:
                items = page.locator("li:has(.del_wan_icon)").all()
            if items:
                items[0].click()
                page.wait_for_timeout(500)
                picked = True
        if not picked:
            raise AssertionError("delete_wan_row: 未找到可勾选的 WAN 行")
        # 4) 点击表格 Delete 按钮
        del_btn = page.locator("#fhId_Delete")
        if del_btn.count() == 0 or not del_btn.first.is_visible():
            # 容错：未勾选时点 Delete 会弹"未选择"提示——此处已勾选，理论上不会走到
            raise AssertionError("delete_wan_row: 未找到 Delete 按钮 #fhId_Delete")
        del_btn.first.click(timeout=5000)
        page.wait_for_timeout(1200)
        return True

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
    "real.close_dialog": lambda s, a: s.close_dialog(),
    "real.close_boxes": lambda s, a: s.close_boxes(),
    "real.delete_wan_row": lambda s, a: s.delete_wan_row(),
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
    ap.add_argument("--out", default=None)
    # 访问协议：支持自然语言描述（"https加密"/"http明文"/"自动探测"），默认 auto=HTTPS 优先自动探测
    ap.add_argument("--scheme", default="auto",
                    help='访问协议，支持自然语言: "https加密"/"http明文"/"自动探测"，默认 auto')
    args = ap.parse_args()

    # new_ui（SPA 新 UI）套件在 operators/intl/cases/real/new_ui/（24 套件）
    cases_dir = os.path.join(ROOT, "operators", "intl", "cases", "real", "new_ui")
    default_out = os.path.join(ROOT, "reports", "intl_real")
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
    resolve_base_url(args.scheme)
    args.out = args.out or default_out
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
        # HTTPS 自签证书场景需忽略校验；纯 HTTP 场景该参数无副作用
        browser = p.chromium.launch(headless=not args.headful,
                                    args=["--ignore-certificate-errors"])
        for case in all_cases:
            summary["total"] += 1
            t0 = datetime.now()
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
            # 每条用例耗时统计（秒，保留 1 位小数）
            res["duration_s"] = round((datetime.now() - t0).total_seconds(), 1)
            res["start"] = t0.isoformat()
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
    summary["duration_s"] = round((datetime.now() - datetime.fromisoformat(summary["start"])).total_seconds(), 1)
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
