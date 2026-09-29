#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把用例里逐条重复的「登录四步」收敛为「一个页面只登录一次，其余用例复用会话」。

背景
----
老 UI 用例的几乎每条都以「访问登录页 → 输入用户名 → 输入密码 → 点击登录」开头，
而执行器为每条用例新建独立 context（会话隔离），因此 N 条用例就要登录 N 次
（wifi 4 页 103 条用例 ≈ 102 次登录，纯浪费约 8 分钟）。

本工具把「标准登录四步」替换为单步 `real.ensure_login`：
  - 执行器（runner/run_intl_real_html.py）在 run 开始时登录一次并保存
    storage_state；以 ensure_login / open_page 开头的用例建 context 时注入该存档
    → 整个 run 只登录一次（按页单独执行时即「每页一次」）；
  - 某条用例把会话登出销毁后，下一条的 ensure_login 会自动重登并刷新存档；
  - 未声明复用语义的用例（未登录拦截、登录流程、错误密码等）不注入会话，
    行为与改动前完全一致。

幂等：已以 ensure_login 开头的用例自动跳过，重复执行不会叠加改动。

安全护栏（2026-09-18 加固，批量应用前的必要保护）
-----------------------------------------------
「标准登录四步」必须是**纯前置条件**才会被收敛，判据三重：
1. 动作/选择器序列完全一致（navigate /login.html → fill #user_name → fill #loginpp → click #login_btn）；
2. **两个 fill 的取值严格等于** ``${QCT_INTL_ADMIN_USER}`` / ``${QCT_INTL_ADMIN_PASS}``
   （否则说明登录/输入本身即被测点，如错误密码、空用户名、登录框 XSS 注入）；
3. 用例尾部不含登录失败/锁定类断言（``assert_login_error`` / ``assert_login_stays`` / ``.login_error_hint``）。
另外 ``login.json`` / ``security.json`` 整个文件默认跳过——收敛后执行器会给它们注入会话，
「未登录态」「锁定态」的断言落点会变（可用 ``--force-files`` 强制）。

用法
----
    python tools/apply_single_login.py operators/intl/cases/real/html/wifi_advanced.json
    python tools/apply_single_login.py --dry-run operators/intl/cases/real/html/wifi*.json
    python tools/apply_single_login.py --glob "operators/intl/cases/real/html/wifi*.json"
    # 批量收敛全部页面（推荐先 --dry-run 复核）
    python tools/apply_single_login.py --glob "operators/intl/cases/real/html/*.json"
"""
import argparse
import glob as _glob
import json
import os

STD_LOGIN_DESC = "确保已登录（会话复用：整个 run 只登录一次；会话失效自动重登）"

# 「标准登录四步」的前置条件取值：必须严格等于这两个占位符，才算「登录前置」。
# 反例（值非常规 → 登录/输入本身即被测点，绝不能收敛）：
#   INTL-LOGIN-002 用 WrongPass123 测错误密码提示
#   INTL-LOGIN-003 用 '' 测空用户名/空密码前端拦截
#   INTL-STATUS-004 用 '<img src=x onerror=alert(1)>' 测登录框 XSS 注入
STD_USER_VALUE = "${QCT_INTL_ADMIN_USER}"
STD_PASS_VALUE = "${QCT_INTL_ADMIN_PASS}"

# 用例尾部出现这些动作/选择器，说明「登录失败/锁定」是被测点，收敛会改变断言落点
LOGIN_FAIL_ACTIONS = {"real.assert_login_error", "real.assert_login_stays"}
LOGIN_FAIL_SELECTORS = ("login_error_hint",)

# 整个文件跳过：登录 / 安全域的用例本身就是「登录行为」的验证对象，
# 收敛成 ensure_login 后执行器会注入会话，语义与改动前不一致。
SKIP_FILES = {"login.json", "security.json"}


def is_std_login_block(steps):
    """是否为用例开头的「标准登录四步」：访问登录页 → 填用户名 → 填密码 → 点登录。

    双重判据（2026-09-18 加固）：除动作/选择器外，还要求两个 fill 的取值严格等于
    ``${QCT_INTL_ADMIN_USER}`` / ``${QCT_INTL_ADMIN_PASS}``。仅匹配动作会让
    「错误密码」「空用户名」「登录框 XSS」这类以登录为被测点的用例被误收敛。
    """
    h = steps[:4]
    return bool(len(h) == 4
                and h[0].get("action") == "real.navigate" and h[0].get("path") == "/login.html"
                and h[1].get("action") == "real.fill" and h[1].get("selector") == "#user_name"
                and h[1].get("value") == STD_USER_VALUE
                and h[2].get("action") == "real.fill" and h[2].get("selector") == "#loginpp"
                and h[2].get("value") == STD_PASS_VALUE
                and h[3].get("action") == "real.click" and h[3].get("selector") == "#login_btn")


def _has_login_failure_semantics(case):
    """尾部断言是否指向「登录失败/账号锁定」——是则登录是被测点，保留原样。"""
    for s in (case.get("steps") or [])[4:]:
        if s.get("action") in LOGIN_FAIL_ACTIONS:
            return True
        sel = str(s.get("selector", ""))
        if any(x in sel for x in LOGIN_FAIL_SELECTORS):
            return True
    return False



def collapse_login_steps(cases):
    """把每条用例开头的标准登录四步合并为单步 real.ensure_login。

    返回 (新用例列表, 被改写的用例 ID 列表, 仍保留原样的用例 ID 列表,
          改写后用例内部仍有中途登录的用例 ID 列表)。

    用例内**中途**的登出/重登（如「重登后持久化」「未登录访问拦截」）不受影响：
    这类用例仍会在中途按自身需要登录一次——那是被测点，不能省。

    「保留原样」= 开头不是标准登录前置（未登录拦截 / 登录流程 / 错误密码 / 登录框 XSS），
    或尾部断言登录失败/锁定（收敛后执行器会注入会话，断言落点会变）。
    """
    out, changed, kept, mid = [], [], [], []
    for case in cases:
        steps = case.get("steps") or []
        has_mid_login = any(s.get("selector") in ("#user_name", "#loginpp")
                            or s.get("action") == "real.login" for s in steps[4:])
        if is_std_login_block(steps) and not _has_login_failure_semantics(case):
            new_case = dict(case)
            new_case["steps"] = [{"action": "real.ensure_login", "desc": STD_LOGIN_DESC}] + steps[4:]
            out.append(new_case)
            changed.append(case.get("id"))
            if has_mid_login:
                mid.append(case.get("id"))
        else:
            out.append(case)
            if (has_mid_login or _has_login_failure_semantics(case)
                    or any(s.get("selector") in ("#user_name", "#loginpp")
                           or s.get("action") == "real.login" for s in steps)):
                kept.append(case.get("id"))
    return out, changed, kept, mid


def apply_file(path, dry_run=False):
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list):
        raise SystemExit(f"[err] {path} 不是用例列表（list）格式，已跳过")
    new_cases, changed, kept, mid = collapse_login_steps(cases)
    print(f"=== {os.path.basename(path)}: 共 {len(cases)} 条，改写 {len(changed)} 条 -> ensure_login")
    if kept:
        print(f"    完全保留原样的用例（登录流程/未登录拦截，登录即被测点）：{kept}")
    if mid:
        print(f"    用例内部仍有「登出后重登」的用例（重登即被测点，保留）：{mid}")
    if changed and not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new_cases, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("    已写回")
    elif changed:
        print("    （--dry-run，未写回）")
    return len(changed)


def main():
    ap = argparse.ArgumentParser(description="把逐条重复的登录四步收敛为「每页登录一次 + 其余复用会话」")
    ap.add_argument("files", nargs="*", help="用例 JSON 文件路径")
    ap.add_argument("--glob", dest="pattern", default=None, help="按通配符批量指定（如 'operators/intl/cases/real/html/wifi*.json'）")
    ap.add_argument("--dry-run", action="store_true", help="只预览改动，不写回文件")
    ap.add_argument("--force-files", action="store_true",
                    help="连 SKIP_FILES（login.json/security.json）一并处理，慎用")
    args = ap.parse_args()

    if args.force_files:
        SKIP_FILES.clear()

    paths = list(args.files)
    if args.pattern:
        paths += sorted(_glob.glob(args.pattern))
    if not paths:
        ap.error("请至少指定一个用例文件（或 --glob）")
    total = 0
    for p in paths:
        if not os.path.isfile(p):
            print(f"[skip] 文件不存在: {p}")
            continue
        if os.path.basename(p) in SKIP_FILES:
            print(f"[skip] {os.path.basename(p)}：登录/安全域用例——登录行为本身即被测点，"
                  f"收敛会在执行器注入会话、改变语义（用 --force-files 可强制处理）")
            continue
        total += apply_file(p, dry_run=args.dry_run)
    print(f"\n合计改写 {total} 条用例{'（未写回）' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
