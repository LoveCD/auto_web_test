# -*- coding: utf-8 -*-
"""真机 Web UI 关键字执行层（面向 SPA 架构）。"""
import os, time, json, base64
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


class RealWebSession:
    """用于真机设备的 Playwright 会话，支持 SPA hash 路由、菜单点击、截图。"""

    def __init__(self, profile, selectors, report_dir=None):
        self.profile = profile
        self.selectors = selectors
        self.env_cfg = profile["env"][profile.get("active_env", "real")]
        self.base_url = self.env_cfg["base_url"].rstrip("/")
        self.report_dir = report_dir or os.path.join(os.getcwd(), "reports")
        self.screenshot_dir = os.path.join(self.report_dir, "screenshots")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._logged_in = False

    # ------------------------------------------------------------------ helpers
    def _resolve_selector(self, key):
        """把 login.username 这类 key 解析成真实 CSS selector。
        兼容两种结构：selectors['login']['username'] 或 selectors['login']['selectors']['username']。"""
        parts = key.split(".")
        node = self.selectors
        for p in parts:
            if isinstance(node, dict):
                # 优先进入 'selectors' 子容器
                if "selectors" in node and p in node.get("selectors", {}):
                    node = node["selectors"][p]
                elif p in node:
                    node = node[p]
                else:
                    return None
            else:
                return None
        return node if isinstance(node, str) else None

    def _resolve_text(self, key):
        """解析 expected_text 节点，兼容 selectors 嵌套。"""
        parts = key.split(".")
        node = self.selectors
        for p in parts:
            if isinstance(node, dict):
                if "expected_text" in node and p in node.get("expected_text", {}):
                    node = node["expected_text"][p]
                elif "selectors" in node and p in node.get("selectors", {}):
                    node = node["selectors"][p]
                elif p in node:
                    node = node[p]
                else:
                    return None
            else:
                return None
        return node if isinstance(node, str) else None

    def start(self, headed=False, browser_type="chromium"):
        self.playwright = sync_playwright().start()
        browser_launcher = getattr(self.playwright, browser_type)
        viewport = self.profile.get("browser", {}).get("viewport", {"width": 1440, "height": 900})
        self.browser = browser_launcher.launch(headless=not headed)
        self.context = self.browser.new_context(viewport=viewport)
        self.page = self.context.new_page()
        # 捕获 JS 弹窗（alert/confirm）。设备登录失败等场景使用 alert 提示，
        # 弹窗会阻塞页面，统一自动关闭并记录消息供断言使用。
        self.dialogs = []
        self.page.on("dialog", self._on_dialog)

    def _on_dialog(self, dialog):
        """记录弹窗消息并自动关闭，避免阻塞后续操作。"""
        try:
            self.dialogs.append({"type": dialog.type, "message": dialog.message})
        except Exception:
            pass
        try:
            dialog.dismiss()
        except Exception:
            pass

    def stop(self):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def close(self):
        self.stop()

    # ------------------------------------------------------------------ actions
    RAW_SELECTOR_PREFIXES = ("#", ".", "[", "text=", "xpath=", "css=", "label=", "role=")

    def _to_selector(self, key):
        """key 既可以是 selectors.json 中的键（如 login.username），也可以是原始 CSS 选择器（如 #fhId_SSID）。

        对于登录页元素，普通版（#user_name）与 AP 版（#user_name_ap）可能同时存在且仅一套生效，
        因此统一选择当前完整可见的表单版本。
        """
        if key and key.startswith(self.RAW_SELECTOR_PREFIXES):
            return key
        # 登录元素：整套选择当前激活版本
        if key and key.startswith("login.") and not key.startswith("login.alt_"):
            field = key.split(".", 1)[1]
            primary = self._resolve_selector(key)
            alt = self._resolve_selector(f"login.alt_{field}")
            try:
                wrap_active = self.page.evaluate("""() => {
                    const el = document.getElementById('wraplogin_CM');
                    return el && el.offsetParent !== null;
                }""")
                ap_active = self.page.evaluate("""() => {
                    const el = document.getElementById('fh_login_container');
                    return el && el.offsetParent !== null;
                }""")
                if ap_active and not wrap_active and alt:
                    return alt
            except Exception:
                pass
            return primary or alt
        sel = self._resolve_selector(key)
        if not sel:
            raise ValueError(f"selector not found: {key}")
        return sel

    def navigate(self, path=""):
        login_path = self.env_cfg.get("login_path", "/login.html")
        url = self.base_url + ("/" + path.lstrip("/") if path else "")
        self.page.goto(url, timeout=self.profile["timeouts"]["goto"])
        self.page.wait_for_load_state("networkidle", timeout=self.profile["timeouts"]["networkidle"])
        # 目标是登录页但被重定向到主页面：设备仍保留上一会话，先退出再重试
        if path == login_path and not self.is_login_page():
            try:
                self.logout()
                self.page.goto(url, timeout=self.profile["timeouts"]["goto"])
                self.page.wait_for_load_state("networkidle", timeout=self.profile["timeouts"]["networkidle"])
            except Exception:
                pass
        # 等待登录表单容器稳定（普通/AP 二选一可见）
        if path == login_path:
            try:
                self.page.wait_for_function(
                    """() => {
                        const wrap = document.getElementById('wraplogin_CM');
                        const ap = document.getElementById('fh_login_container');
                        return (wrap && wrap.offsetParent !== null) || (ap && ap.offsetParent !== null);
                    }""",
                    timeout=self.profile["timeouts"]["element"]
                )
                # 统一使用普通版登录容器。设备 JS 以 style.display == "" 表示"显示"，
                # 因此置为空字符串而非 'block'，避免破坏其 onkeydown/容器判断逻辑。
                self.page.evaluate("""() => {
                    const wrap = document.getElementById('wraplogin_CM');
                    const ap = document.getElementById('fh_login_container');
                    if (wrap) wrap.style.display = '';
                    if (ap) ap.style.display = 'none';
                }""")
                self.page.wait_for_timeout(300)
            except Exception:
                pass

    def is_login_page(self):
        return "login.html" in self.page.url

    def login(self, role="admin"):
        """登录。若当前不在登录页则先跳转；登录后断言已离开登录页。"""
        if not self.is_login_page():
            self.navigate(self.env_cfg.get("login_path", "/login.html"))
        auth = self.env_cfg["auth"][role]
        username_sel = self._resolve_selector("login.username")
        password_sel = self._resolve_selector("login.password")
        submit_sel = self._resolve_selector("login.submit")
        # 兼容 AP 风格登录容器（同时存在两套 id）
        if self.page.locator(username_sel).count() == 0:
            username_sel = self._resolve_selector("login.alt_username")
            password_sel = self._resolve_selector("login.alt_password")
            submit_sel = self._resolve_selector("login.alt_submit")
        self.page.fill(username_sel, auth["username"])
        self.page.fill(password_sel, auth["password"])
        self.page.click(submit_sel)
        self.page.wait_for_load_state("networkidle", timeout=self.profile["timeouts"]["networkidle"])
        self.page.wait_for_timeout(self.profile["timeouts"].get("page_load_extra", 2500))
        if self.is_login_page():
            err = ""
            try:
                err = self.page.locator(self._resolve_selector("login.error_hint")).inner_text(timeout=2000)
            except Exception:
                pass
            raise AssertionError(f"login failed (still on login page). error: {err}")
        self._logged_in = True

    def logout(self):
        """退出登录并处理确认弹窗。"""
        if self.is_login_page():
            return
        self.page.locator(self._resolve_selector("main.logout_btn")).click()
        self.page.wait_for_timeout(800)
        confirm_sel = self._resolve_selector("main.logout_confirm_btn")
        if confirm_sel and self.page.locator(confirm_sel).count() > 0:
            self.page.locator(confirm_sel).click()
        self.page.wait_for_load_state("networkidle", timeout=self.profile["timeouts"]["networkidle"])
        self.page.wait_for_timeout(self.profile["timeouts"].get("page_load_extra", 2500))
        self._logged_in = False

    def navigate_spa(self, route=""):
        """智能 SPA 导航：优先通过菜单点击逐级展开，若不可行再回退到 hash。"""
        parts = [p for p in route.split("/") if p]
        if len(parts) >= 3:
            l1, l2, comp = parts[0], parts[1], parts[2]
            try:
                self.click_menu(1, l1)
                self.click_menu(2, l2)
                # 在展开的 L3 中找最匹配的项
                l3s = self.page.evaluate("""() => [...document.querySelectorAll('#panel_sidebar > ul > li[id^=\"fhId_\"]')].map(el => ({id: el.id, text: el.innerText.trim()}))""")
                best = None
                for item in l3s:
                    item_id_lower = item['id'].lower()
                    if comp.lower() in item_id_lower or item_id_lower.replace('_', '').replace('-', '') in comp.lower():
                        best = item
                        break
                if not best and l3s:
                    # fallback：匹配文本
                    for item in l3s:
                        if comp.lower() in item['text'].lower():
                            best = item
                            break
                if best:
                    self.page.locator(f"#{best['id']}").click()
                    self.page.wait_for_timeout(self.profile["timeouts"].get("page_load_extra", 6000))
                    return
            except Exception:
                pass
        # 回退：直接改 hash
        prefix = self.profile.get("spa", {}).get("route_prefix", "main.html#")
        url = f"{self.base_url}/{prefix}{route}"
        self.page.goto(url, timeout=self.profile["timeouts"]["goto"])
        self.page.wait_for_load_state("networkidle", timeout=self.profile["timeouts"]["networkidle"])
        self.page.wait_for_timeout(self.profile["timeouts"].get("page_load_extra", 2500))

    def click(self, selector_key):
        sel = self._to_selector(selector_key)
        # 支持 text=... 选择器
        if sel.startswith("text="):
            self.page.get_by_text(sel.split("=", 1)[1]).click()
        else:
            self.page.locator(sel).click()

    def fill(self, selector_key, value):
        sel = self._to_selector(selector_key)
        loc = self.page.locator(sel).first
        loc.scroll_into_view_if_needed(timeout=self.profile["timeouts"]["element"])
        # el-input 的 id 通常挂在组件根 div 上，实际可 fill 的是内部 input
        tag = loc.evaluate("el => el.tagName.toLowerCase()")
        if tag != "input":
            inner = loc.locator("input").first
            if inner.count() > 0:
                loc = inner
        loc.fill(str(value))

    def reload(self):
        """强制刷新当前页面（用于真机共享 session 中恢复干净表单状态）。"""
        self.page.reload(wait_until="networkidle", timeout=self.profile["timeouts"]["goto"])
        self.page.wait_for_timeout(self.profile["timeouts"].get("page_load_extra", 2500))

    def evaluate(self, script="", arg=None):
        """执行一段页面 JS（如清除 localStorage/sessionStorage，绕过组件 keep-alive/草稿缓存）。"""
        return self.page.evaluate(script, arg)

    def wait(self, ms=1000):
        self.page.wait_for_timeout(int(ms))

    def wait_url(self, contains=""):
        self.page.wait_for_url(f"**{contains}*", timeout=self.profile["timeouts"]["goto"])

    def click_menu(self, level=1, title=""):
        spa = self.profile.get("spa", {})
        item_prefix = spa.get("menu_id_prefix", "fhId_") + "{title}" + spa.get("menu_id_suffix", "_L{level}")
        item_id = item_prefix.format(title=title, level=level)
        sel = f"#{item_id}"
        self.page.locator(sel).wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        self.page.locator(sel).click()
        self.page.wait_for_timeout(self.profile["timeouts"].get("page_load_extra", 2500))

    def screenshot(self, name="screenshot"):
        ts = time.strftime("%H%M%S")
        safe = name.replace("/", "_").replace("\\", "_")
        path = os.path.join(self.screenshot_dir, f"{ts}_{safe}.png")
        capture_full = self.selectors.get("screenshot", {}).get("capture_full_page", False)
        self.page.screenshot(path=path, full_page=capture_full)
        return path

    # ------------------------------------------------------------------ element-level actions (ElementUI)
    def assert_element(self, selector):
        """断言元素可见。selector 可为原始 CSS（#fhId_xxx）或 selectors 键。"""
        sel = self._to_selector(selector)
        self.page.locator(sel).first.wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        return True

    def _open_dropdown(self, selector):
        """展开 ElementUI el-select 下拉。selector 指向带 id 的组件根/input。"""
        sel = self._to_selector(selector)
        loc = self.page.locator(sel).first
        loc.scroll_into_view_if_needed(timeout=self.profile["timeouts"]["element"])
        # id 挂在组件根 div 上时，实际可点击的是内部 input
        tag = loc.evaluate("el => el.tagName.toLowerCase()")
        if tag != "input":
            inner = loc.locator("input").first
            if inner.count() > 0:
                loc = inner
        loc.click()
        self.page.wait_for_timeout(600)

    def _dropdown_items(self, option_text):
        """当前可见下拉面板中可见的、包含指定文本的选项。

        用 filter(visible=True) 基于 is_visible() 精确过滤，避免多下拉框页面
        （如日志页 LogLevel/LogViewLevel 两个 el-select 共用下拉面板）
        匹配到隐藏面板中的同名选项（:visible 伪类在 wait_for 中可能不生效）。
        """
        return self.page.locator(
            ".el-select-dropdown__item",
        ).filter(has_text=option_text).filter(visible=True)

    def select_option(self, selector, option_text):
        """在下拉框中选择指定文本的选项。"""
        self._open_dropdown(selector)
        item = self._dropdown_items(option_text).first
        item.click(timeout=self.profile["timeouts"]["element"])
        self.page.wait_for_timeout(500)
        return True

    def assert_option_present(self, selector, option_text):
        """断言下拉框中存在指定选项。"""
        self._open_dropdown(selector)
        try:
            found = False
            for _ in range(3):
                if self._dropdown_items(option_text).count() > 0:
                    found = True
                    break
                self.page.wait_for_timeout(500)
            if not found:
                raise AssertionError(f"option '{option_text}' not found in dropdown {selector}")
        finally:
            self.page.keyboard.press("Escape")
        return True

    def assert_option_absent(self, selector, option_text):
        """断言下拉框中不存在指定选项（需求差距验证）。"""
        self._open_dropdown(selector)
        try:
            found = False
            for _ in range(3):
                if self._dropdown_items(option_text).count() > 0:
                    found = True
                    break
                self.page.wait_for_timeout(500)
            if found:
                raise AssertionError(f"option '{option_text}' unexpectedly present in dropdown {selector}")
        finally:
            self.page.keyboard.press("Escape")
        return True

    # ------------------------------------------------------------------ assertions
    def assert_page(self, component):
        """断言 SPA 页面已渲染：el_main 可见且内部有内容（文本/子元素/HTML 任一）。

        对慢渲染页面做短轮询，避免单次检测时机问题。
        """
        self.page.locator("#el_main").wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        for _ in range(6):
            info = self.page.evaluate("""() => {
                const el = document.getElementById('el_main');
                if (!el) return {textLen: 0, htmlLen: 0, childCount: 0};
                return {
                    textLen: el.innerText.trim().length,
                    htmlLen: el.innerHTML.length,
                    childCount: el.children.length
                };
            }""")
            if info["textLen"] >= 5 or info["htmlLen"] >= 200 or info["childCount"] > 0:
                return True
            self.page.wait_for_timeout(500)
        raise AssertionError(
            f"page {component} not rendered (#el_main empty: text={info['textLen']}, html={info['htmlLen']}, children={info['childCount']})"
        )

    def assert_login_error(self):
        """断言登录错误提示已出现。

        CM 真机在密码错误等场景下使用 alert 弹窗提示（如"用户名或密码错误，请重试"），
        而不是显示 #login_error_hint（该节点为静态隐藏文本）。因此：
        1) 优先检查已捕获的 dialog 消息（点击登录后 120ms 内弹窗）；
        2) 兜底检查页面 body 文本是否包含常见错误关键词。
        """
        hints = ["用户名或密码", "输入错误", "请重新输入", "用户名和密码不匹配",
                 "用户名或密码错误", "错误", "不能为空", "不允许"]
        # 等待弹窗出现（登录失败弹窗有 120ms 延迟 + 网络往返）
        for _ in range(12):
            if self.dialogs:
                break
            self.page.wait_for_timeout(250)
        msgs = [d.get("message", "") for d in self.dialogs]
        if any(any(h in m for h in hints) for m in msgs):
            return True
        body = self.page.locator("body").inner_text(timeout=5000)
        if any(h in body for h in hints):
            return True
        raise AssertionError(f"login error hint not detected. dialogs={msgs}")

    def assert_visible(self, selector_key):
        sel = self._resolve_selector(selector_key)
        self.page.locator(sel).wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        return True

    def assert_text_contains(self, selector_key, text=None):
        if text is None:
            text = self._resolve_text(selector_key)
            if text is None:
                raise ValueError(f"text not found for key: {selector_key}")
        sel = text if text.startswith(("text=", "css=", "#", ".", "[")) else f"text={text}"
        self.page.wait_for_selector(sel, timeout=self.profile["timeouts"]["element"])
        return True

    def assert_url_contains(self, substring):
        if substring not in self.page.url:
            raise AssertionError(f"url '{self.page.url}' does not contain '{substring}'")
        return True

    # ------------------------------------------------------------------ switch / form 控件级关键字（ElementUI）
    def _switch_checked(self, selector):
        """读取 el-switch 是否处于开启状态（is-checked 类或内部 checkbox）。"""
        sel = self._to_selector(selector)
        return self.page.evaluate("""(s) => {
            const el = document.querySelector(s);
            if (!el) return null;
            if (el.classList.contains('is-checked')) return true;
            if (el.classList.contains('is-unchecked')) return false;
            const input = el.querySelector('input');
            if (input) return input.checked;
            return null;
        }""", sel)

    def assert_switch_checked(self, selector, checked=True):
        """断言 el-switch 的开启状态与期望一致。"""
        sel = self._to_selector(selector)
        self.page.locator(sel).first.wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        expect = bool(checked)
        for _ in range(6):
            state = self._switch_checked(sel)
            if state == expect:
                return True
            self.page.wait_for_timeout(500)
        raise AssertionError(f"switch {sel} checked={state}, expected {expect}")

    def ensure_switch(self, selector, checked=True):
        """确保 el-switch 处于目标状态（不同则点击切换）。用于用例前置归一化，幂等可重复执行。"""
        sel = self._to_selector(selector)
        self.page.locator(sel).first.wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        expect = bool(checked)
        state = self._switch_checked(sel)
        if state is None:
            raise AssertionError(f"switch state not readable: {sel}")
        if state != expect:
            self.page.locator(sel).first.click()
            self.page.wait_for_timeout(600)
            for _ in range(6):
                if self._switch_checked(sel) == expect:
                    return True
                self.page.wait_for_timeout(500)
            raise AssertionError(f"switch {sel} failed to toggle to {expect}")
        return True

    def assert_element_hidden(self, selector):
        """断言元素不存在或不可见（v-if 移除 / display:none 均视为隐藏）。"""
        sel = self._to_selector(selector)
        loc = self.page.locator(sel)
        for _ in range(6):
            if loc.count() == 0:
                return True
            try:
                visible = loc.first.is_visible()
            except Exception:
                visible = False
            if not visible:
                return True
            self.page.wait_for_timeout(500)
        raise AssertionError(f"element {sel} still visible (expected hidden)")

    def assert_input_value(self, selector, value):
        """断言 el-input 当前值等于期望值。"""
        sel = self._to_selector(selector)
        loc = self.page.locator(sel).first
        loc.wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        # el-input 的 id 挂在组件根 div 上，实际输入框是内部 input
        inner = loc.locator("input").first if loc.evaluate("el => el.tagName.toLowerCase()") != "input" else loc
        for _ in range(6):
            try:
                if inner.input_value() == str(value):
                    return True
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        raise AssertionError(f"input {sel} value={inner.input_value()}, expected {value}")

    def assert_input_value_not(self, selector, value):
        """断言 el-input 当前值不等于指定值（修改未保存后应恢复原始值，非修改值）。"""
        sel = self._to_selector(selector)
        loc = self.page.locator(sel).first
        loc.wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        inner = loc.locator("input").first if loc.evaluate("el => el.tagName.toLowerCase()") != "input" else loc
        if inner.input_value() == str(value):
            raise AssertionError(f"input {sel} value={inner.input_value()}, should NOT be {value}")
        return True

    def click_button(self, text):
        """按按钮文本点击（兼容无 id 的保存/应用按钮，如 wificonfig 的"保存"）。"""
        self.page.get_by_role("button", name=text).first.click()
        self.page.wait_for_timeout(500)
        return True

    # ------------------------------------------------------------------ 确认框（fh_confirm = Element UI MessageBox，DOM 弹窗）
    # 真机 fh_confirm() 基于 Element UI $confirm（dangerouslyUseHTMLString: true），
    # 渲染为 body 下的 .el-message-box DOM，不走原生 confirm -> Playwright dialog 事件不触发。
    # 危险操作（删除/重启/恢厂）确认框验证必须用 DOM 断言 + 文本按钮点击。
    CONFIRM_BOX = ".el-message-box"
    CONFIRM_MSG = ".el-message-box__message, .el-message-box__content"

    def _confirm_box(self):
        return self.page.locator(self.CONFIRM_BOX).first

    def assert_confirm_visible(self, message_keyword=None):
        """断言 fh_confirm 确认框可见；message_keyword 非空时校验消息文本包含关键字。"""
        box = self._confirm_box()
        box.wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        if message_keyword:
            for _ in range(6):
                try:
                    text = box.inner_text()
                except Exception:
                    text = ""
                if message_keyword in text:
                    return True
                self.page.wait_for_timeout(500)
            raise AssertionError(f"confirm box text {text!r} does not contain {message_keyword!r}")
        return True

    def assert_confirm_hidden(self):
        """断言 fh_confirm 确认框已消失（取消/确定后弹窗关闭）。"""
        self._confirm_box().wait_for(state="hidden", timeout=self.profile["timeouts"]["element"])
        return True

    def click_confirm(self, accept=True):
        """点击确认框按钮：accept=True 点"确定/Confirm"（执行操作），accept=False 点"取消/Cancel"（零风险）。

        真机为英文 locale（fg_confirm 按钮显示 "Confirm"/"Cancel"），
        同时兼容中文 "确定"/"取消"，按按钮文本精确匹配，避免 get_by_role 子串误配。
        """
        if accept:
            labels = ["确定", "Confirm", "OK"]
        else:
            labels = ["取消", "Cancel"]
        box = self._confirm_box()
        for label in labels:
            btn = box.get_by_role("button", name=label, exact=True)
            if btn.count() > 0:
                btn.first.click()
                self.page.wait_for_timeout(500)
                return True
        # 兜底：确认框内最后一个按钮通常为主操作（Confirm），第一个为取消
        btns = box.locator("button")
        (btns.last if accept else btns.first).click()
        self.page.wait_for_timeout(500)
        return True

    # ------------------------------------------------------------------ XSS 安全断言
    def assert_no_dialog(self, wait_ms=2000):
        """等待 wait_ms 毫秒，断言期间无新增原生 JS 弹窗（alert/confirm）。

        XSS payload（如 <script>alert(1)</script>）若被执行会触发原生 alert，
        会被 start() 中的 dialog 监听捕获并自动关闭。
        """
        before = len(self.dialogs)
        self.page.wait_for_timeout(wait_ms)
        if len(self.dialogs) > before:
            raise AssertionError(f"XSS dialog detected: {self.dialogs[before:]}")
        return True

    def assert_no_dialog_containing(self, keyword):
        """断言已捕获的所有 dialog 消息均不含指定关键字。

        XSS 场景：注入 payload 后断言没有任何弹窗消息携带 payload 片段
        （即 payload 未被拼接/渲染进任何提示）。
        """
        hits = [d for d in self.dialogs if keyword in d.get("message", "")]
        if hits:
            raise AssertionError(f"dialog contains payload {keyword!r}: {hits}")
        return True

    def assert_response_header(self, header, value_contains=None, path="/"):
        """重新请求页面并断言响应头存在（或包含指定值）。

        安全测试：检查 X-Frame-Options / Content-Security-Policy 等安全头。
        若设备缺失安全头，断言失败即反映真实安全差距。
        """
        url = self.base_url + ("/" + path.lstrip("/") if path else "/")
        resp = self.page.goto(url, timeout=self.profile["timeouts"]["goto"])
        headers = {k.lower(): v for k, v in (resp.headers or {}).items()}
        key = header.lower()
        if key not in headers:
            raise AssertionError(f"response header '{header}' missing on {url}")
        if value_contains and value_contains.lower() not in headers[key].lower():
            raise AssertionError(
                f"header {header}={headers[key]!r} does not contain {value_contains!r}")
        return True

    def assert_text_escaped(self, selector, payload):
        """断言元素以纯文本形式显示 payload（未被 HTML 解析执行）。

        用于区分 Vue {{ }} / v-text（转义，安全）与 v-html（渲染执行，危险）。
        """
        sel = self._to_selector(selector)
        el = self.page.locator(sel).first
        el.wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        text = el.inner_text()
        if text.strip() != str(payload).strip():
            raise AssertionError(f"element text {text!r} != payload {payload!r} (可能被 HTML 解析)")
        return True

    def assert_no_element(self, selector):
        """断言元素不存在（未渲染 / v-if 移除）。

        XSS 场景：注入 <img src=x onerror=...> 后断言该 img 未出现在 DOM 中。
        """
        sel = self._to_selector(selector)
        for _ in range(6):
            if self.page.locator(sel).count() == 0:
                return True
            self.page.wait_for_timeout(500)
        raise AssertionError(f"element {sel} still exists (XSS 注入疑似执行)")

    # ------------------------------------------------------------------ 表格断言（el-table，LAN 地址表等）
    def assert_table_rows(self, selector, min_rows=1):
        """断言 el-table 行数 >= min_rows（等待异步数据加载）。

        el-table 渲染为 .el-table__row 行；空数据时无行。
        """
        sel = self._to_selector(selector)
        loc = self.page.locator(sel)
        loc.first.wait_for(state="visible", timeout=self.profile["timeouts"]["element"])
        for _ in range(8):
            count = loc.locator(".el-table__row").count()
            if count >= min_rows:
                return True
            self.page.wait_for_timeout(500)
        raise AssertionError(f"table {sel} rows={count}, expected >= {min_rows}")
