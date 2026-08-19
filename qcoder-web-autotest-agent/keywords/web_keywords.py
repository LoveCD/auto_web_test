# -*- coding: utf-8 -*-
"""Web 关键字执行层：将用例中的 page.* 动作翻译为 Page Object 调用。

动作清单（与 cases/**/*.json 中 action 一一对应）：
  page.login          正向登录（默认凭证取 profile.auth）
  page.submit_login   填写并提交登录（不等待结果，供负向用例）
  page.wait_login     等待回到登录页
  page.goto_status/wifi/wan/lan/system/upgrade   直达页面
  page.wait_*_data    等待页面异步数据加载完成
  page.set_wifi       填写 Wi-Fi 并 Apply
  page.set_lan        填写 LAN 并 Apply
  page.reboot         点击重启（自动接受确认对话框）
  page.wait_reboot_msg 等待重启结果提示
  page.upgrade        填写固件 URL 并触发升级
  page.reload         刷新当前页
  page.nav_to         通过左侧菜单跳转 {page}
  page.logout         登出
  page.goto           直接导航 {page}（用于未登录访问测试）
"""
import urllib.request

from playwright.sync_api import sync_playwright

from pages import (LoginPage, StatusPage, WifiPage, WanPage, LanPage,
                   SystemPage, UpgradePage, NavBar)
from keywords.assert_keywords import assert_expect

PAGE_OBJECT_MAP = {
    "login": "login_page",
    "status": "status_page",
    "wifi": "wifi_page",
    "wan": "wan_page",
    "lan": "lan_page",
    "system": "system_page",
    "upgrade": "upgrade_page",
}


class WebSession:
    """一个浏览器会话 = 一个用例的执行环境（用例间状态隔离）。"""

    def __init__(self, profile: dict, selectors: dict):
        self.profile = profile
        self.selectors = selectors
        self.base_url = profile["base_url"].rstrip("/")
        self.current_page_name = "login"

        browser_cfg = profile.get("browser", {})
        self._playwright = sync_playwright().start()
        browser_type = getattr(self._playwright, browser_cfg.get("browser_type", "chromium"))
        self.browser = browser_type.launch(headless=browser_cfg.get("headless", True))
        self.context = self.browser.new_context(
            viewport=browser_cfg.get("viewport", {"width": 1440, "height": 900}),
            locale=browser_cfg.get("locale", "en-US"),
        )
        self.page = self.context.new_page()

        # Page Object 实例
        self.login_page = LoginPage(self.page, selectors, profile)
        self.status_page = StatusPage(self.page, selectors, profile)
        self.wifi_page = WifiPage(self.page, selectors, profile)
        self.wan_page = WanPage(self.page, selectors, profile)
        self.lan_page = LanPage(self.page, selectors, profile)
        self.system_page = SystemPage(self.page, selectors, profile)
        self.upgrade_page = UpgradePage(self.page, selectors, profile)
        self.nav_bar = NavBar(self.page, selectors, profile)

        self.http_evidence = []  # 关键 HTTP 证据（供失败分析）

    # ------------------------------------------------------------- 生命周期
    @property
    def page_obj(self):
        return getattr(self, PAGE_OBJECT_MAP.get(self.current_page_name, "status_page"))

    def set_page(self, name: str):
        if name in PAGE_OBJECT_MAP:
            self.current_page_name = name

    def reset_device_state(self):
        """用例前置：通过 HTTP 直接重置 mock 设备状态（测试支持端点）。"""
        try:
            req = urllib.request.Request(self.base_url + "/api/reset", method="POST",
                                         data=b"{}")
            urllib.request.urlopen(req, timeout=5)
        except Exception as exc:  # noqa: BLE001
            self.http_evidence.append({"note": "device reset failed", "error": str(exc)})

    def screenshot(self, path: str):
        try:
            self.page.screenshot(path=path, full_page=False)
            return True
        except Exception:
            return False

    def close(self):
        try:
            self.context.close()
        except Exception:
            pass
        try:
            self.browser.close()
        except Exception:
            pass
        try:
            self._playwright.stop()
        except Exception:
            pass

    # ------------------------------------------------------------- 动作执行
    def execute_step(self, step: dict) -> dict:
        """执行单个步骤，返回 {action, status, failures, detail}。"""
        action = step.get("action", "")
        params = step.get("params", {}) or {}
        expect = step.get("expect", {}) or {}
        failures = []

        try:
            self._dispatch(action, params)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"action {action} raised: {exc}")

        if not failures:
            failures = assert_expect(self, expect)

        status = "pass" if not failures else "fail"
        return {"action": action, "status": status, "failures": failures}

    def _dispatch(self, action: str, params: dict):
        p = params
        if action == "page.login":
            ok = self.login_page.login(p.get("username"), p.get("password"))
            if not ok:
                raise AssertionError("login did not reach a protected page")
            self.set_page("status")
        elif action == "page.submit_login":
            self.login_page.goto_login()
            self.login_page.submit(p.get("username"), p.get("password"))
            self.set_page("login")
        elif action == "page.wait_login":
            self.login_page.wait_login_page()
            self.set_page("login")
        elif action == "page.goto":
            name = p.get("page")
            po = getattr(self, PAGE_OBJECT_MAP.get(name, "status_page"))
            po.goto()
            self.set_page(name)
        elif action == "page.goto_status":
            self.status_page.goto_status(); self.set_page("status")
        elif action == "page.wait_status_data":
            self.status_page.wait_data_loaded(); self.set_page("status")
        elif action == "page.goto_wifi":
            self.wifi_page.goto_wifi(); self.set_page("wifi")
        elif action == "page.wait_wifi_loaded":
            self.wifi_page.wait_loaded(); self.set_page("wifi")
        elif action == "page.set_wifi":
            self.set_page("wifi")
            self.wifi_page.set_wifi(
                ssid=p.get("ssid", ""), password=p.get("password", ""),
                enabled=p.get("enabled"), security=p.get("security"))
        elif action == "page.goto_wan":
            self.wan_page.goto_wan(); self.set_page("wan")
        elif action == "page.wait_wan_data":
            self.wan_page.wait_loaded(); self.set_page("wan")
        elif action == "page.goto_lan":
            self.lan_page.goto_lan(); self.set_page("lan")
        elif action == "page.wait_lan_data":
            self.lan_page.wait_loaded(); self.set_page("lan")
        elif action == "page.set_lan":
            self.set_page("lan")
            self.lan_page.set_lan(ip=p.get("ip", ""), mask=p.get("mask", ""),
                                  dhcp_enabled=p.get("dhcp_enabled"))
        elif action == "page.goto_system":
            self.system_page.goto_system(); self.set_page("system")
        elif action == "page.wait_system_data":
            self.system_page.wait_loaded(); self.set_page("system")
        elif action == "page.reboot":
            self.set_page("system")
            self.system_page.reboot()
        elif action == "page.wait_reboot_msg":
            self.system_page.wait_reboot_msg(); self.set_page("system")
        elif action == "page.goto_upgrade":
            self.upgrade_page.goto_upgrade(); self.set_page("upgrade")
        elif action == "page.wait_upgrade_data":
            self.upgrade_page.wait_loaded(); self.set_page("upgrade")
        elif action == "page.upgrade":
            self.set_page("upgrade")
            self.upgrade_page.upgrade(url=p.get("url", ""))
        elif action == "page.reload":
            self.page.reload(wait_until="networkidle")
        elif action == "page.nav_to":
            name = p.get("page")
            self.nav_bar.goto_page(name)
            self.set_page(name)
        elif action == "page.logout":
            self.nav_bar.logout()
            self.set_page("login")
        elif action == "page.expect":
            pass  # 纯断言步骤
        else:
            raise ValueError(f"unknown action {action}")

    # ---------------- 兼容新 StepRunner 的统一接口 ----------------
    def execute_action(self, action: str, params: dict):
        """供 StepRunner 调用的统一 action 入口。"""
        self._dispatch(action, params)

    def assert_url_contains(self, substring: str):
        if substring not in self.page.url:
            raise AssertionError(f"url '{self.page.url}' does not contain '{substring}'")

    def assert_visible(self, key: str):
        sel = self._resolve_selector(key)
        self.page.locator(sel).wait_for(state="visible", timeout=self.profile["timeouts"]["element_wait_seconds"] * 1000)

    def assert_text_contains(self, key: str):
        # 旧 INTL selectors 结构没有统一 text 节点，先 fallback 到 page_obj
        node = self.selectors
        for p in key.split("."):
            if isinstance(node, dict) and p in node:
                node = node[p]
            else:
                node = None
                break
        text = node if isinstance(node, str) else ""
        if not text:
            raise AssertionError(f"text selector {key} not found")
        self.page.wait_for_selector(f"text={text}", timeout=self.profile["timeouts"]["element_wait_seconds"] * 1000)

    def _resolve_selector(self, key: str):
        parts = key.split(".")
        node = self.selectors
        for p in parts:
            if isinstance(node, dict):
                if "selectors" in node and p in node.get("selectors", {}):
                    node = node["selectors"][p]
                elif p in node:
                    node = node[p]
                else:
                    return None
            else:
                return None
        return node if isinstance(node, str) else None
