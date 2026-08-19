# -*- coding: utf-8 -*-
"""WAN 页 Page Object。"""
from pages.base_page import BasePage


class WanPage(BasePage):
    PAGE = "wan"

    def goto_wan(self):
        self.goto(self.profile["routes"]["wan"])

    def wait_loaded(self):
        self.page.wait_for_function(
            "() => { const el = document.querySelector('#wan_status');"
            " return el && el.textContent.trim() !== '-' && el.textContent.trim() !== ''; }",
            timeout=self.element_wait_ms)
