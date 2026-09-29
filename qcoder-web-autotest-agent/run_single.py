#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单独运行指定用例 ID，用于排查套件中的偶发失败

按用例所在 UI 形态自动选择执行器：
  - real/new_ui/ 与旧 real/ 目录 → runner/run_intl_real.py（SPA 新 UI）
  - real/html/ 目录（老 UI 多页版）→ runner/run_intl_real_html.py
"""
import json, os, sys, importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))

case_id = sys.argv[1] if len(sys.argv) > 1 else "INTL-WAN-CRUD-008"
suite_file = sys.argv[2] if len(sys.argv) > 2 else "wan.json"
# 套件定位：new_ui（SPA 新 UI）优先，其次 html（老 UI 多页版），最后旧 real/ 兜底
candidates = [
    os.path.join(ROOT, "operators", "intl", "cases", "real", "new_ui", suite_file),
    os.path.join(ROOT, "operators", "intl", "cases", "real", "html", suite_file),
    os.path.join(ROOT, "operators", "intl", "cases", "real", suite_file),
]
case_path = next((p for p in candidates if os.path.exists(p)), None)
if not case_path:
    print("套件文件不存在:", suite_file)
    sys.exit(1)

# html（老 UI 多页版）用例须用专用执行器（SKIP/delete_wan_row(row_text) 等老 UI 语义）
if case_path.endswith(os.path.join("html", suite_file)):
    runner_name = "run_intl_real_html.py"
else:
    runner_name = "run_intl_real.py"
spec = importlib.util.spec_from_file_location("runner_mod", os.path.join(ROOT, "runner", runner_name))
mod = importlib.util.module_from_spec(spec)
sys.modules["runner_mod"] = mod
spec.loader.exec_module(mod)
IntlSession = mod.IntlSession
run_case = mod.run_case

cases = json.load(open(case_path, encoding="utf-8"))
case = next((c for c in cases if c["id"] == case_id), None)
if not case:
    print("用例不存在:", case_id)
    sys.exit(1)

out_dir = os.path.join(ROOT, "reports", "intl_real", "single_" + case_id)
os.makedirs(out_dir, exist_ok=True)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1600, "height": 900})
    page = context.new_page()
    session = IntlSession(page, out_dir)
    try:
        res = run_case(session, case, out_dir)
    except Exception as e:
        res = {"id": case.get("id"), "title": case.get("title"), "status": "ERROR", "error": str(e)[:300], "steps": []}
    if res["status"] == "PASS":
        has_shot = any(st.get("detail") for st in res.get("steps", []))
        if not has_shot:
            try:
                shot = session.screenshot(f"OK_{case.get('id','case')}")
                res.setdefault("steps", []).append({"index": len(res.get("steps", [])) + 1, "action": "real.screenshot", "desc": "用例成果截图", "status": "PASS", "detail": shot})
            except Exception:
                pass
    context.close()
    browser.close()

print(f"[{res['status']}] {res['id']} - {res['title']}")
if res.get("error"):
    print("  ERROR:", res["error"])
for st in res.get("steps", []):
    if st.get("status") != "PASS":
        print(f"  step {st.get('index')} [{st.get('action')}] {st.get('desc')} -> {st.get('status')} {st.get('error') or ''}")
json.dump(res, open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("结果:", os.path.join(out_dir, "result.json"))
