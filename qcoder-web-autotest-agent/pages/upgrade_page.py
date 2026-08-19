# -*- coding: utf-8 -*-
"""固件升级页 Page Object。"""
from pages.base_page import BasePage


class UpgradePage(BasePage):
    PAGE = "upgrade"

    def goto_upgrade(self):
        self.goto(self.profile["routes"]["upgrade"])

    def wait_loaded(self):
        self.page.wait_for_function(
            "() => { const el = document.querySelector('#cur_version');"
            " return el && el.textContent.trim() !== '-' && el.textContent.trim() !== ''; }",
            timeout=self.element_wait_ms)

    def upgrade(self, url: str):
        self.wait_loaded()
        self.fill("firmware_url", url)
        self.click("upgrade_btn")
        self.wait_visible("upgrade_msg")
