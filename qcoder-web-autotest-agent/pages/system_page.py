# -*- coding: utf-8 -*-
"""系统维护页 Page Object。"""
from pages.base_page import BasePage


class SystemPage(BasePage):
    PAGE = "system"

    def goto_system(self):
        self.goto(self.profile["routes"]["system"])

    def wait_loaded(self):
        self.page.wait_for_function(
            "() => { const el = document.querySelector('#sys_model');"
            " return el && el.textContent.trim() !== '-' && el.textContent.trim() !== ''; }",
            timeout=self.element_wait_ms)

    def reboot(self):
        """点击重启并自动接受确认对话框。"""
        self.wait_loaded()
        # 注册一次性 dialog handler：接受确认
        dialog_accepted = {"ok": False}

        def on_dialog(dialog):
            dialog.accept()
            dialog_accepted["ok"] = True

        self.page.once("dialog", on_dialog)
        self.click("reboot_btn")
        # 等待对话框被处理（最多 5s）
        self.page.wait_for_timeout(500)
        if not dialog_accepted["ok"]:
            # 部分浏览器下 dialog 事件可能延迟，再等一次
            try:
                self.page.wait_for_timeout(1000)
            except Exception:
                pass
        self.wait_reboot_msg()

    def wait_reboot_msg(self):
        self.wait_visible("reboot_msg")
