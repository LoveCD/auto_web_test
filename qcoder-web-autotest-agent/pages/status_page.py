# -*- coding: utf-8 -*-
"""状态页 Page Object。"""
from pages.base_page import BasePage


class StatusPage(BasePage):
    PAGE = "status"

    def goto_status(self):
        self.goto(self.profile["routes"]["status"])

    def wait_data_loaded(self):
        """等待状态数据异步填充完成（软件版本非 '-'）。"""
        self.page.wait_for_function(
            "() => { const el = document.querySelector('#sw_version');"
            " return el && el.textContent.trim() !== '-' && el.textContent.trim() !== ''; }",
            timeout=self.element_wait_ms)
