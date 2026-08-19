# -*- coding: utf-8 -*-
"""导航栏 Page Object：左侧菜单跳转与登出。"""
from pages.base_page import BasePage

PAGE_MENU_MAP = {
    "status": "menu_status",
    "wifi": "menu_wifi",
    "wan": "menu_wan",
    "lan": "menu_lan",
    "system": "menu_system",
    "upgrade": "menu_upgrade",
}


class NavBar(BasePage):
    PAGE = "nav"

    def goto_page(self, page_name: str):
        menu_key = PAGE_MENU_MAP[page_name]
        self.click(menu_key)
        routes = self.profile["routes"]
        self.wait_url(routes[page_name])

    def logout(self):
        self.click("logout_link")
        self.wait_url("/login.html")
