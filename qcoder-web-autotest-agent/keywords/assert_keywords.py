# -*- coding: utf-8 -*-
"""页面断言引擎：将用例 expect 字典翻译为具体断言。

支持的 expect 键：
  url_contains    str           当前 URL 包含子串
  title_contains  str           页面标题包含子串
  text            {key: str}    元素文本 == 期望（strip 后精确匹配）
  text_contains   {key: str}    元素文本包含子串
  input_value     {key: str}    输入框值 == 期望
  visible         [key...]      元素可见
  hidden          [key...]      元素不可见
  checked         {key: bool}   复选框勾选状态
  non_empty       [key...]      元素文本/输入框值非空
  toast_success   bool          toast 为 success 样式
  toast_error     bool          toast 为 error 样式
"""
import re


def _first_failure(label, check):
    try:
        ok, detail = check()
    except Exception as exc:  # noqa: BLE001
        return f"{label}: error {exc}"
    if not ok:
        return f"{label}: {detail}"
    return None


def _element_text(session, key):
    """优先取文本；输入框则取 value。"""
    page_obj = session.page_obj
    try:
        if page_obj.locator(key).count() == 0:
            return ""
        tag = page_obj.locator(key).first.evaluate("el => el.tagName")
        if tag in ("INPUT", "SELECT", "TEXTAREA"):
            return page_obj.input_value(key)
        return page_obj.text_of(key)
    except Exception:
        return ""


def _toast_key(session):
    """当前页的 toast 元素 key（元素名以 _msg 或 msg 结尾）。"""
    page_obj = session.page_obj
    cfg = session.selectors["pages"].get(page_obj.PAGE, {}).get("elements", {})
    for key in cfg:
        if key.endswith("_msg") or key == "msg":
            return key
    # 兜底：任意页面里的 _msg
    for _name, _cfg in session.selectors["pages"].items():
        for key in _cfg.get("elements", {}):
            if key.endswith("_msg"):
                return key
    raise KeyError("no toast element found for current page")


def _check_toast(session, style):
    key = _toast_key(session)
    page_obj = session.page_obj
    loc = page_obj.locator(key)
    if not loc.is_visible():
        return False, f"toast({key}) not visible"
    cls = loc.get_attribute("class") or ""
    if style == "success":
        return "success" in cls, f"toast class={cls!r}, expected success"
    return "error" in cls, f"toast class={cls!r}, expected error"


def assert_expect(session, expect: dict) -> list:
    """执行所有断言，返回失败信息列表（空 = 全部通过）。"""
    failures = []
    if not expect:
        return failures

    page_obj = session.page_obj

    if "url_contains" in expect:
        sub = expect["url_contains"]
        failures.append(_first_failure(
            f"url_contains {sub!r}",
            lambda: (sub in session.page.url, f"got url {session.page.url!r}")))

    if "title_contains" in expect:
        sub = expect["title_contains"]
        title = session.page.title()
        failures.append(_first_failure(
            f"title_contains {sub!r}",
            lambda: (sub in title, f"got title {title!r}")))

    if "text" in expect:
        for key, expected in expect["text"].items():
            def _check(key=key, expected=expected):
                actual = _element_text(session, key)
                return actual == expected, f"got {actual!r}"
            failures.append(_first_failure(f"text {key}", _check))

    if "text_contains" in expect:
        for key, sub in expect["text_contains"].items():
            def _check(key=key, sub=sub):
                actual = _element_text(session, key)
                return sub in actual, f"got {actual!r}"
            failures.append(_first_failure(f"text_contains {key}", _check))

    if "input_value" in expect:
        for key, expected in expect["input_value"].items():
            def _check(key=key, expected=expected):
                actual = page_obj.input_value(key)
                return actual == expected, f"got {actual!r}"
            failures.append(_first_failure(f"input_value {key}", _check))

    if "visible" in expect:
        for key in expect["visible"]:
            def _check(key=key):
                page_obj.locator(key).wait_for(state="visible", timeout=page_obj.element_wait_ms)
                return True, ""
            failures.append(_first_failure(f"visible {key}", _check))

    if "hidden" in expect:
        for key in expect["hidden"]:
            def _check(key=key):
                page_obj.locator(key).wait_for(state="hidden", timeout=page_obj.element_wait_ms)
                return True, ""
            failures.append(_first_failure(f"hidden {key}", _check))

    if "checked" in expect:
        for key, expected in expect["checked"].items():
            def _check(key=key, expected=expected):
                actual = page_obj.is_checked(key)
                return actual == expected, f"got checked={actual}"
            failures.append(_first_failure(f"checked {key}", _check))

    if "non_empty" in expect:
        for key in expect["non_empty"]:
            def _check(key=key):
                actual = _element_text(session, key)
                return bool(actual and actual.strip() and actual != "-"), f"got {actual!r}"
            failures.append(_first_failure(f"non_empty {key}", _check))

    if "toast_success" in expect:
        failures.append(_first_failure("toast_success", lambda: _check_toast(session, "success")))

    if "toast_error" in expect:
        failures.append(_first_failure("toast_error", lambda: _check_toast(session, "error")))

    return [f for f in failures if f]
