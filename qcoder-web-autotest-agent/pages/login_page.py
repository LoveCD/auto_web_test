# -*- coding: utf-8 -*-
"""登录页 Page Object。DOM 结构对照真实设备 login.html（#user_name / #loginpp / #login_btn / #login_error_hint）。"""
from pages.base_page import BasePage


class LoginPage(BasePage):
    PAGE = "login"

    def goto_login(self):
        self.goto(self.profile["routes"]["login"])

    def submit(self, username: str = None, password: str = None):
        """填写并点击登录（不等待结果，供负向用例使用）。"""
        username = username if username is not None else self.profile["auth"]["username"]
        password = password if password is not None else self.profile["auth"]["password"]
        self.fill("username", username)
        self.fill("password", password)
        self.click("login_btn")

    def login(self, username: str = None, password: str = None) -> bool:
        """正向登录：等待跳转到受保护页面，返回是否成功。"""
        self.goto_login()
        self.submit(username, password)
        try:
            self.page.wait_for_url(
                lambda u: "/login.html" not in u,
                timeout=self.element_wait_ms)
            return True
        except Exception:
            return False

    def is_on_login_page(self) -> bool:
        return "/login.html" in self.page.url

    def wait_login_page(self):
        self.wait_url("/login.html")
        self.wait_visible("login_btn")

    def error_text(self) -> str:
        return self.text_of("error_hint")
