# -*- coding: utf-8 -*-
"""LAN 页 Page Object。"""
from pages.base_page import BasePage


class LanPage(BasePage):
    PAGE = "lan"

    def goto_lan(self):
        self.goto(self.profile["routes"]["lan"])

    def wait_loaded(self):
        self.wait_visible("lan_ip")
        self.page.wait_for_function(
            "() => { const el = document.querySelector('#lan_ip');"
            " return el && el.value !== ''; }",
            timeout=self.element_wait_ms)

    def set_lan(self, ip: str, mask: str, dhcp_enabled: bool = None):
        self.wait_loaded()
        self.fill("lan_ip", ip)
        self.fill("lan_mask", mask)
        if dhcp_enabled is not None:
            self.check("dhcp_enabled", dhcp_enabled)
        self.click("save_lan")
        self.wait_visible("lan_msg")
