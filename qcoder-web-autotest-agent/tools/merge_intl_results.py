"""合并结果集：以全量回归结果为基线，并入用例修订后重跑的结果，生成可出报告的合并 run 目录。

基线：reports/intl_real_html/20260910_183752/result.json（老 UI 全量，排除手机端，193 条）
覆盖：2026-09-11 修订后重跑的单条/单套件结果 reports/intl/html/<run_id>/result.json
"""
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.join(ROOT, "reports", "intl_real_html", "20260910_183752")
SINGLE_DIR = os.path.join(ROOT, "reports", "intl", "html")

# 覆盖来源（按用例取最新一次重跑结果）
OVERRIDES = {
    # wan 套件整体重跑：含新增 INTL-WAN-012
    "run:20260911_100225": "wan 套件全量重跑（含新增预置用例）",
    "run:20260911_095633": "端口映射/NAT 绑定预置 WAN 后重跑",
    "run:20260911_100722": "DDNS APP-116 绑定预置 WAN 后重跑",
    "run:20260911_102001": "DDNS APP-117 绑定预置 WAN 后重跑",
    "run:20260911_095816": "静态路由绑定预置 WAN 后重跑",
    "run:20260911_100753": "静态路由 ROUTE-008 复核重跑",
    "run:20260911_102030": "ACL FW-034 用例修订后重跑（空 IP 属合法行为）",
    "run:20260911_102052": "SEC-006 增加会话清理前置后重跑",
}


def main():
    base = json.load(open(os.path.join(BASE_DIR, "result.json"), encoding="utf-8"))
    merged = {}
    for c in base["cases"]:
        merged[c["id"]] = dict(c)

    order = [c["id"] for c in base["cases"]]
    applied, added_case_ids, extra_duration = [], [], 0.0

    for key, why in OVERRIDES.items():
        run_id = key.split(":", 1)[1]
        path = os.path.join(SINGLE_DIR, run_id, "result.json")
        if not os.path.exists(path):
            print(f"[warn] 缺少重跑结果：{path}")
            continue
        rd = json.load(open(path, encoding="utf-8"))
        extra_duration += rd.get("duration_s") or 0
        for c in rd.get("cases", []):
            cid = c["id"]
            entry = dict(c)
            entry["rerun"] = True
            entry["merged_from_run"] = run_id
            entry["merged_reason"] = why
            if cid in merged:
                merged[cid] = entry
            else:
                merged[cid] = entry
                order.append(cid)
                added_case_ids.append(cid)
        applied.append(run_id)

    cases = [merged[cid] for cid in order]
    passed = sum(1 for c in cases if c["status"] == "PASS")
    failed = sum(1 for c in cases if c["status"] == "FAIL")
    skipped = sum(1 for c in cases if c["status"] == "SKIP")
    total = len(cases)
    executed = total - skipped

    out_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_merged"
    out_dir = os.path.join(ROOT, "reports", "intl_real_html", out_id)
    os.makedirs(out_dir, exist_ok=True)

    result = {
        "total": total,
        "pass": passed,
        "fail": failed,
        "skip": skipped,
        "pass_rate": round(passed / executed * 100, 1) if executed else 0.0,
        "cases": cases,
        "start": base.get("start"),
        "end": datetime.now().isoformat(),
        "duration_s": round((base.get("duration_s") or 0) + extra_duration, 1),
        "merged": True,
        "base_run": "20260910_183752",
        "merged_runs": applied,
        "added_case_ids": added_case_ids,
        "merge_note": "全量回归基线结果 + 2026-09-11 用例修订（SEC-006/FW-034 结论纠正、WAN 预置与绑定）后重跑结果合并",
    }
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"合并结果已生成: {out_dir}")
    print(f"总数 {total} | 通过 {passed} | 失败 {failed} | 跳过 {skipped} | 执行通过率 {result['pass_rate']}%")
    print(f"覆盖 runs: {', '.join(applied)}")
    print(f"新增用例: {added_case_ids}")
    print(f"累计耗时: {result['duration_s']}s")
    print("\n非 PASS 明细:")
    for c in cases:
        if c["status"] != "PASS":
            print(f"  {c['status']} {c['id']} — {c['title'][:44]}")


if __name__ == "__main__":
    main()
