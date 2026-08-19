# -*- coding: utf-8 -*-
"""Page Object 基类：浏览器/页面生命周期、选择器解析、公共交互。

遵循 E2E 技能规范：
- 稳定选择器（优先 ID / role / label，不依赖 CSS class 与 DOM 层级）
- 确定性等待（等待条件而非固定超时）
- 测试行为而非实现
"""
from playwright.sync_api import Page, expect


class BasePage:
    """所有页面对象的基类。"""

    # 子类覆盖：对应 profiles/selectors 中的页面 key
    PAGE = "base"

    def __init__(self, page: Page, selectors: dict, profile: dict):
        self.page = page
        self.selectors = selectors
        self.profile = profile
        self.base_url = profile["base_url"].rstrip("/")
        self.timeouts = profile.get("timeouts", {})
        self.element_wait_ms = int(self.timeouts.get("element_wait_seconds", 10) * 1000)

    # ------------------------------------------------------------------ 选择器
    def sel(self, key: str) -> str:
        """解析逻辑元素名 -> CSS 选择器（当前页优先，其次 nav，再全库兜底）。"""
        pages = self.selectors.get("pages", {})
        cur = pages.get(self.PAGE, {}).get("elements", {})
        if key in cur:
            return cur[key]
        nav = pages.get("nav", {}).get("elements", {})
        if key in nav:
            return nav[key]
        for name, cfg in pages.items():
            els = cfg.get("elements", {})
            if key in els:
                return els[key]
        raise KeyError(f"selector key not found: {self.PAGE}.{key}")

    def url(self, path: str) -> str:
        return self.base_url + path

    def page_route(self) -> str:
        routes = self.profile.get("routes", {})
        return routes.get(self.PAGE, f"/{self.PAGE}.html")

    # ------------------------------------------------------------------ 导航
    def goto(self, path: str = None):
        target = self.url(path or self.page_route())
        self.page.goto(target, wait_until="domcontentloaded", timeout=self.element_wait_ms)
        self.page.wait_for_load_state("networkidle", timeout=self.element_wait_ms)

    def locator(self, key: str):
        return self.page.locator(self.sel(key))

    def click(self, key: str):
        self.locator(key).click(timeout=self.element_wait_ms)

    def fill(self, key: str, value: str):
        self.locator(key).fill(value, timeout=self.element_wait_ms)

    def check(self, key: str, state: bool = True):
        if state:
            self.locator(key).check(timeout=self.element_wait_ms)
        else:
            self.locator(key).uncheck(timeout=self.element_wait_ms)

    def select(self, key: str, value: str):
        self.locator(key).select_option(value)

    def text_of(self, key: str) -> str:
        return self.locator(key).inner_text(timeout=self.element_wait_ms).strip()

    def input_value(self, key: str) -> str:
        return self.locator(key).input_value(timeout=self.element_wait_ms)

    def is_checked(self, key: str) -> bool:
        return self.locator(key).is_checked()

    def is_visible(self, key: str) -> bool:
        return self.locator(key).is_visible(timeout=self.element_wait_ms)

    def wait_visible(self, key: str):
        self.locator(key).wait_for(state="visible", timeout=self.element_wait_ms)

    def expect_visible(self, key: str):
        expect(self.locator(key)).to_be_visible(timeout=self.element_wait_ms)

    def expect_hidden(self, key: str):
        expect(self.locator(key)).to_be_hidden(timeout=self.element_wait_ms)

    def wait_url(self, substring: str):
        self.page.wait_for_url(lambda u: substring in u, timeout=self.element_wait_ms)

    def toast_locator(self, key: str = "wifi_msg"):
        """toast 元素：display:none -> block 后可见，等待其出现。"""
        self.wait_visible(key)
