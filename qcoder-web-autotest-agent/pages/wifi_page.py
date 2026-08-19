# -*- coding: utf-8 -*-
"""Wi-Fi 页 Page Object。"""
from pages.base_page import BasePage


class WifiPage(BasePage):
    PAGE = "wifi"

    def goto_wifi(self):
        self.goto(self.profile["routes"]["wifi"])

    def set_wifi(self, ssid: str, password: str, enabled: bool = None,
                 security: str = None):
        """填写 Wi-Fi 配置并点击 Apply；等待 toast 出现（不预设成败）。"""
        self.wait_visible("ssid")
        self.fill("ssid", ssid)
        self.fill("wifi_password", password)
        if enabled is not None:
            self.check("wifi_enabled", enabled)
        if security:
            self.select("security_mode", security)
        self.click("save_wifi")
        self.wait_visible("wifi_msg")

    def wait_loaded(self):
        self.wait_visible("ssid")
