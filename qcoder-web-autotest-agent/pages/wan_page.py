# -*- coding: utf-8 -*-
"""WAN 页 Page Object（含连接管理 CRUD，对齐真机 networkConn 页交互）。"""
from pages.base_page import BasePage

# 表单字段名 -> selector key
WAN_FORM_FIELDS = ("name", "type", "service", "username", "password",
                   "trigger", "idle", "mtu", "vlan")


class WanPage(BasePage):
    PAGE = "wan"

    def goto_wan(self):
        self.goto(self.profile["routes"]["wan"])

    def wait_loaded(self):
        """等待状态数据与连接列表均加载完成。"""
        self.page.wait_for_function(
            "() => { const el = document.querySelector('#wan_status');"
            " return el && el.textContent.trim() !== '-' && el.textContent.trim() !== ''; }",
            timeout=self.element_wait_ms)
        self.wait_visible("wan_conn_list")

    # ------------------------------------------------------------ CRUD 动作
    def select_connection(self, conn_id):
        """下拉选择要编辑的连接。"""
        self.select("wan_select", str(conn_id))

    def click_new_connection(self):
        """点击新增：清空表单进入新建态。"""
        self.click("wan_new_btn")

    def fill_form(self, data: dict):
        """按字段名填写表单（仅填提供的字段）。"""
        if "name" in data:
            self.fill("wan_name", str(data["name"]))
        if "type" in data:
            self.select("wan_type_select", str(data["type"]))
        if "service" in data:
            self.fill("wan_service", str(data["service"]))
        if "username" in data:
            self.fill("wan_username", str(data["username"]))
        if "password" in data:
            self.fill("wan_password", str(data["password"]))
        if "trigger" in data:
            self.select("wan_trigger", str(data["trigger"]))
        if "idle" in data:
            self.fill("wan_idle", str(data["idle"]))
        if "mtu" in data:
            self.fill("wan_mtu", str(data["mtu"]))
        if "vlan" in data:
            self.fill("wan_vlan", str(data["vlan"]))

    def get_form(self) -> dict:
        """读回表单当前值。"""
        return {
            "name": self.input_value("wan_name"),
            "type": self.input_value("wan_type_select"),
            "service": self.input_value("wan_service"),
            "username": self.input_value("wan_username"),
            "password": self.input_value("wan_password"),
            "trigger": self.input_value("wan_trigger"),
            "idle": self.input_value("wan_idle"),
            "mtu": self.input_value("wan_mtu"),
            "vlan": self.input_value("wan_vlan"),
        }

    def click_save(self):
        """点击保存并等待后端处理完成（wan_msg 文本发生变化）。"""
        before = self.msg_text()
        self.click("wan_save_btn")
        self.page.wait_for_function(
            "(prev) => { const el = document.querySelector('#wan_msg');"
            " return el && el.textContent.trim() !== '' && el.textContent.trim() !== prev; }",
            arg=before, timeout=self.element_wait_ms)

    def click_delete(self, accept: bool = False):
        """点击删除。mock 页为原生 confirm：accept=True 接受（真正删除），
        accept=False 取消（零风险校验，模拟真机 fh_confirm 取消场景）。
        返回是否捕获到确认框；未选中连接（无确认框）时 handler 会被移除不残留。"""
        handled = {"ok": False}

        def on_dialog(dialog):
            handled["ok"] = True
            if accept:
                dialog.accept()
            else:
                dialog.dismiss()

        self.page.on("dialog", on_dialog)
        try:
            self.click("wan_del_btn")
            self.page.wait_for_timeout(400)
            if not handled["ok"]:
                self.page.wait_for_timeout(1000)
        finally:
            self.page.remove_listener("dialog", on_dialog)
        return handled["ok"]

    # ------------------------------------------------------------ 读取断言
    def msg_text(self) -> str:
        return self.text_of("wan_msg")

    def get_rows(self) -> list:
        """连接列表每行 -> [id, name, type, service, username, status, mtu, vlan]。"""
        tds = self.locator("wan_conn_list").locator("tr td")
        count = tds.count()
        rows = []
        for i in range(0, count, 8):
            rows.append([tds.nth(j).inner_text().strip() for j in range(i, min(i + 8, count))])
        return rows

    def find_row(self, name: str):
        """按连接名查找列表行，未找到返回 None。"""
        for row in self.get_rows():
            if len(row) >= 2 and row[1] == name:
                return row
        return None
