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

    def reboot(self, accept: bool = True):
        """点击重启。accept=True 接受确认并等待消息（mock 真正执行），
        accept=False 取消（零风险校验，模拟真机 fh_confirm 取消场景）。"""
        self.wait_loaded()
        handled = self._click_with_dialog("reboot_btn", accept=accept)
        if accept and handled:
            self.wait_reboot_msg()

    def wait_reboot_msg(self):
        self.wait_visible("reboot_msg")

    # ------------------------------------------------------------ 恢复配置
    def restore_default(self, accept: bool = True):
        """恢复默认配置。accept=True 接受确认（mock 真正执行），
        accept=False 取消（零风险校验，模拟真机 fh_confirm 取消场景）。"""
        self.wait_loaded()
        handled = self._click_with_dialog("restore_btn", accept=accept)
        if accept and handled:
            self.wait_restore_msg()

    def factory_reset(self, accept: bool = True):
        """恢复出厂。accept=True 接受（mock 重置内存态 + 会话失效），
        accept=False 取消（零风险校验）。"""
        self.wait_loaded()
        handled = self._click_with_dialog("factory_btn", accept=accept)
        if accept and handled:
            self.wait_restore_msg()

    def wait_restore_msg(self):
        self.wait_visible("restore_msg")

    def restore_msg_text(self) -> str:
        return self.text_of("restore_msg")

    # ------------------------------------------------------------ 辅助
    def _click_with_dialog(self, key: str, accept: bool = True) -> bool:
        """点击按钮并处理原生 confirm 对话框。返回是否捕获到 dialog。
        未弹出 dialog 时 handler 会被移除，避免残留污染后续步骤。"""
        handled = {"ok": False}

        def on_dialog(dialog):
            handled["ok"] = True
            if accept:
                dialog.accept()
            else:
                dialog.dismiss()

        self.page.on("dialog", on_dialog)
        try:
            self.click(key)
            self.page.wait_for_timeout(400)
            if not handled["ok"]:
                self.page.wait_for_timeout(1000)
        finally:
            self.page.remove_listener("dialog", on_dialog)
        return handled["ok"]
