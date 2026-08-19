"""Web keyword dispatcher - maps YAML action names to Playwright Page Object operations."""

import sys
from pathlib import Path

# Ensure pages package is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pages.login_page import LoginPage
from pages.status_page import StatusPage
from pages.wifi_page import WiFiPage
from pages.wan_page import WanPage
from pages.system_page import SystemPage


class WebKeywords:
    """Action dispatcher that maps web.* action names from YAML test cases to Page Object operations."""

    PAGE_MAP = {
        "login": LoginPage,
        "status": StatusPage,
        "wifi": WiFiPage,
        "wan": WanPage,
        "system": SystemPage,
    }

    def __init__(self, page, profile):
        self.page = page
        self.profile = profile
        self.base_url = profile["base_url"]
        self.selectors = profile["selectors"]
        self.page_routes = profile.get("page_routes", {})
        self.auth = profile.get("auth", {})
        self._current_page_obj = None
        self._init_handlers()

    def _init_handlers(self):
        self._handlers = {
            "web.navigate": self._action_navigate,
            "web.login": self._action_login,
            "web.click": self._action_click,
            "web.fill": self._action_fill,
            "web.check": self._action_check,
            "web.assert_text": self._action_assert_text,
            "web.assert_visible": self._action_assert_visible,
            "web.assert_not_visible": self._action_assert_not_visible,
            "web.get_text": self._action_get_text,
            "web.screenshot": self._action_screenshot,
            "web.wait": self._action_wait,
            "web.save_wifi": self._action_save_wifi,
            "web.reboot": self._action_reboot,
        }

    def execute_step(self, step):
        """Execute a single step from a YAML test case.

        Returns a dict: {action, status, failures, details}
        """
        action = step["action"]
        params = step.get("params", {})
        expect = step.get("expect")

        handler = self._handlers.get(action)
        if not handler:
            return {
                "action": action,
                "status": "fail",
                "failures": [f"unknown action {action}"],
            }
        try:
            return handler(params, expect)
        except Exception as exc:
            return {
                "action": action,
                "status": "fail",
                "failures": [f"{type(exc).__name__}: {exc}"],
            }

    def _get_page_obj(self, page_name):
        """Get or create a page object for the given page name."""
        page_cls = self.PAGE_MAP.get(page_name)
        if not page_cls:
            raise ValueError(f"unknown page '{page_name}'")
        obj = page_cls(self.page, self.profile)
        return obj

    def _resolve_selector(self, params):
        """Resolve a selector from params, which may include page context."""
        selector_key = params["selector_key"]
        page_name = params.get("page")
        if page_name:
            page_selectors = self.selectors.get(page_name, {})
        elif self._current_page_obj:
            page_selectors = self.selectors.get(self._current_page_obj.page_key, {})
        else:
            page_selectors = {}
        if selector_key not in page_selectors:
            raise KeyError(f"selector '{selector_key}' not found in page '{page_name or 'current'}'")
        return page_selectors[selector_key]

    # --- Action handlers ---

    def _action_navigate(self, params, expect):
        page_name = params["page"]
        route = self.page_routes.get(page_name, f"/{page_name}.html")
        url = self.base_url + route
        self.page.goto(url)
        self._current_page_obj = self._get_page_obj(page_name)
        return {"action": "web.navigate", "status": "pass", "failures": [], "details": {"url": url}}

    def _action_login(self, params, expect):
        """Login action with explicit expectation.

        Expected result must be declared explicitly in the YAML case:
          - expect: true  (or "success") -> login must succeed
          - expect: false (or "error")   -> login must fail
        When ``expect`` is omitted, fall back to credential-based inference
        for backward compatibility with legacy cases (framework does not
        silently guess when the case author declared an expectation).
        """
        username = params.get("username", self.auth.get("username"))
        password = params.get("password", self.auth.get("password"))
        login_page = LoginPage(self.page, self.profile)
        self._current_page_obj = login_page

        if expect is None:
            # Backward-compatible inference for legacy cases without expect
            expect_success = (
                password == self.auth.get("password")
                and username == self.auth.get("username")
            )
        else:
            expect_success = expect in (True, "success", "Success")

        if expect_success:
            login_page.login(username, password)
            if login_page.is_dashboard_visible():
                return {"action": "web.login", "status": "pass", "failures": [], "details": {"result": "login_success", "expected": "success"}}
            # Check if error message is visible (login failed unexpectedly)
            error_msg = login_page.get_error_message()
            return {
                "action": "web.login",
                "status": "fail",
                "failures": [f"expected login success but failed: {error_msg}" if error_msg else "dashboard not visible after login"],
                "details": {"expected": "success"},
            }
        else:
            login_page.login_expect_error(username, password)
            # For invalid login, dashboard should not be visible
            if login_page.is_dashboard_visible():
                return {
                    "action": "web.login",
                    "status": "fail",
                    "failures": ["expected login failure but dashboard appeared"],
                    "details": {"expected": "error"},
                }
            return {"action": "web.login", "status": "pass", "failures": [], "details": {"result": "login_rejected", "expected": "error"}}

    def _action_click(self, params, expect):
        selector_key = params["selector_key"]
        page_name = params.get("page")
        if page_name:
            self._current_page_obj = self._get_page_obj(page_name)
        if not self._current_page_obj:
            raise ValueError("no page context; use web.navigate first")
        self._current_page_obj.click(selector_key)
        return {"action": "web.click", "status": "pass", "failures": []}

    def _action_fill(self, params, expect):
        selector_key = params["selector_key"]
        value = params["value"]
        page_name = params.get("page")
        if page_name:
            self._current_page_obj = self._get_page_obj(page_name)
        if not self._current_page_obj:
            raise ValueError("no page context; use web.navigate first")
        self._current_page_obj.fill(selector_key, value)
        return {"action": "web.fill", "status": "pass", "failures": [], "details": {"value": value}}

    def _action_check(self, params, expect):
        selector_key = params["selector_key"]
        checked = params.get("checked", True)
        page_name = params.get("page")
        if page_name:
            self._current_page_obj = self._get_page_obj(page_name)
        if not self._current_page_obj:
            raise ValueError("no page context; use web.navigate first")
        self._current_page_obj.check(selector_key, checked)
        return {"action": "web.check", "status": "pass", "failures": []}

    def _action_assert_text(self, params, expect):
        selector_key = params["selector_key"]
        expected = params.get("expected") or expect
        page_name = params.get("page")
        if page_name:
            self._current_page_obj = self._get_page_obj(page_name)
        if not self._current_page_obj:
            raise ValueError("no page context; use web.navigate first")
        actual = self._current_page_obj.get_text(selector_key)
        if actual == expected:
            return {"action": "web.assert_text", "status": "pass", "failures": [], "details": {"actual": actual}}
        return {
            "action": "web.assert_text",
            "status": "fail",
            "failures": [f"{selector_key}: expected '{expected}', got '{actual}'"],
            "details": {"actual": actual, "expected": expected},
        }

    def _action_assert_visible(self, params, expect):
        selector_key = params["selector_key"]
        should_be_visible = expect if expect is not None else True
        if should_be_visible is False:
            return self._action_assert_not_visible(params, expect)
        page_name = params.get("page")
        if page_name:
            self._current_page_obj = self._get_page_obj(page_name)
        if not self._current_page_obj:
            raise ValueError("no page context; use web.navigate first")
        visible = self._current_page_obj.is_visible(selector_key)
        if visible == should_be_visible:
            return {"action": "web.assert_visible", "status": "pass", "failures": []}
        return {
            "action": "web.assert_visible",
            "status": "fail",
            "failures": [f"{selector_key}: expected visible={should_be_visible}, got {visible}"],
        }

    def _action_assert_not_visible(self, params, expect):
        selector_key = params["selector_key"]
        page_name = params.get("page")
        if page_name:
            self._current_page_obj = self._get_page_obj(page_name)
        if not self._current_page_obj:
            raise ValueError("no page context; use web.navigate first")
        visible = self._current_page_obj.is_visible(selector_key)
        if not visible:
            return {"action": "web.assert_visible", "status": "pass", "failures": [], "details": {"expected": "not visible"}}
        return {
            "action": "web.assert_visible",
            "status": "fail",
            "failures": [f"{selector_key}: expected NOT visible, but was visible"],
        }

    def _action_get_text(self, params, expect):
        selector_key = params["selector_key"]
        page_name = params.get("page")
        if page_name:
            self._current_page_obj = self._get_page_obj(page_name)
        if not self._current_page_obj:
            raise ValueError("no page context; use web.navigate first")
        text = self._current_page_obj.get_text(selector_key)
        return {"action": "web.get_text", "status": "pass", "failures": [], "details": {"text": text}}

    def _action_screenshot(self, params, expect):
        path = params.get("path", "screenshot.png")
        self.page.screenshot(path=path)
        return {"action": "web.screenshot", "status": "pass", "failures": [], "details": {"path": path}}

    def _action_wait(self, params, expect):
        ms = params.get("ms", 1000)
        self.page.wait_for_timeout(ms)
        return {"action": "web.wait", "status": "pass", "failures": []}

    def _action_save_wifi(self, params, expect):
        ssid = params.get("ssid")
        password = params.get("password")
        wifi_page = WiFiPage(self.page, self.profile)
        self._current_page_obj = wifi_page
        wifi_page.save_wifi(ssid, password)
        return {"action": "web.save_wifi", "status": "pass", "failures": [], "details": {"ssid": ssid}}

    def _action_reboot(self, params, expect):
        system_page = SystemPage(self.page, self.profile)
        self._current_page_obj = system_page
        system_page.reboot_with_confirm()
        return {"action": "web.reboot", "status": "pass", "failures": []}
