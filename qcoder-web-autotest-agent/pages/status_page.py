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

    # ------------------------------------------------------------ LAN hosts
    def wait_lan_hosts_loaded(self):
        """等待 LAN 侧动态地址表加载（至少 1 行主机）。"""
        self.page.wait_for_function(
            "() => { const t = document.querySelector('#lan_hosts_table');"
            " return t && t.querySelectorAll('tr').length > 0; }",
            timeout=self.element_wait_ms)

    def click_refresh_lan(self):
        self.click("lan_refresh_btn")

    def lan_msg_text(self) -> str:
        return self.text_of("lan_msg")

    def get_lan_host_rows(self) -> list:
        """LAN 主机表每行 -> [ip, ipv6, mac, hostname, type, port, lease, active]。"""
        tds = self.locator("lan_hosts_table").locator("tr td")
        count = tds.count()
        rows = []
        for i in range(0, count, 8):
            rows.append([tds.nth(j).inner_text().strip() for j in range(i, min(i + 8, count))])
        return rows

    def find_host(self, mac: str):
        """按 MAC 查找主机行，未找到返回 None。"""
        for row in self.get_lan_host_rows():
            if len(row) >= 3 and row[2].upper() == mac.upper():
                return row
        return None
