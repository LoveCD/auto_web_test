# -*- coding: utf-8 -*-
"""INTL 老 UI（html 变体）真机回归结果分析。

用法:
    python tools/analyze_intl_html_result.py <run_id>
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT_DIR = os.path.join(ROOT, "reports", "intl_real_html")


def classify(error):
    if not error:
        return "未捕获异常"
    e = error
    if "click_menu" in e:
        return "菜单点击超时（菜单 id 不匹配）"
    if "Timeout" in e and ("real.fill" in e or "real.click" in e or "fill" in e or "click" in e):
        return "fill/click 超时（元素不匹配）"
    if "assert_text_contains" in e or "assert_text_not_contains" in e:
        return "文本断言不成立"
    if "assert_visible" in e or "assert_url_contains" in e:
        return "可见性/URL 断言超时"
    if "assert_unauth_redirect" in e:
        return "未授权跳转断言（会话残留）"
    if "assert_option_present" in e or "select_option" in e:
        return "下拉选项断言/选择失败"
    if "assert_login_error" in e or "assert_login_stays" in e:
        return "登录错误提示断言失败"
    if "assert_confirm" in e:
        return "确认框断言失败"
    if "AssertionError" in e:
        return "断言不成立（实际行为与预期不符）"
    return "执行异常"


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not run_id:
        dirs = sorted(os.listdir(RESULT_DIR), reverse=True)
        run_id = dirs[0]
    d = json.load(open(os.path.join(RESULT_DIR, run_id, "result.json"), encoding="utf-8"))
    print(f"run_id: {run_id}")
    print(f"total={d['total']} pass={d['pass']} fail={d['fail']} skip={d.get('skip', 0)} "
          f"rate={d['pass_rate']}% "
          f"duration_s={d['duration_s']} ({d['duration_s']/60:.1f} min)")
    print(f"start={d['start'][:19]} end={d['end'][:19]}")

    print("\n== 分套件统计 ==")
    stats = {}
    for c in d["cases"]:
        k = c["id"].split("-")[1] if "-" in c["id"] else "?"
        s = stats.setdefault(k, {"total": 0, "pass": 0, "skip": 0, "dur": 0.0})
        s["total"] += 1
        s["pass"] += c["status"] == "PASS"
        s["skip"] += c["status"] == "SKIP"
        s["dur"] += c.get("duration_s") or 0
    for k, s in sorted(stats.items()):
        print(f"  {k:<8} total={s['total']:<3} pass={s['pass']:<3} "
              f"skip={s['skip']:<3} fail={s['total']-s['pass']-s['skip']:<3} dur={s['dur']:.1f}s")

    print("\n== 失败分类 ==")
    cat = {}
    for c in d["cases"]:
        if c["status"] in ("PASS", "SKIP"):
            continue
        k = classify(c.get("error") or "")
        cat[k] = cat.get(k, 0) + 1
    for k, v in sorted(cat.items(), key=lambda x: -x[1]):
        print(f"  {v:>2}  {k}")

    print("\n== 失败用例明细 ==")
    for c in d["cases"]:
        if c["status"] in ("PASS", "SKIP"):
            continue
        err = (c.get("error") or "").split("\n")[0]
        step_desc = ""
        for st in c.get("steps", []):
            if st.get("status") != "PASS":
                step_desc = f"step{st.get('index')} {st.get('desc','')}"
                break
        print(f"  [{c['id']}] {c['title'][:42]}")
        print(f"      {step_desc or '-'} | {classify(c.get('error'))} | {err[:110]}")

    print("\n== 耗时统计 ==")
    durs = [c["duration_s"] for c in d["cases"] if c.get("duration_s") is not None]
    if durs:
        print(f"  平均 {sum(durs)/len(durs):.1f}s  最短 {min(durs)}s  最长 {max(durs)}s")
        top = sorted(d["cases"], key=lambda c: c.get("duration_s") or 0, reverse=True)[:5]
        for c in top:
            print(f"    {c['duration_s']:>6.1f}s  {c['id']}  {c['title'][:44]}")


if __name__ == "__main__":
    main()
