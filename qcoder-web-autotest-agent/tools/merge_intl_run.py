# -*- coding: utf-8 -*-
"""把「修订后重跑的少量用例」结果并回全量基线，生成可直接出报告的合并 run 目录。

用法：
  python _merge_run.py <base_run_id> <override_run_dir> [<override_run_dir> ...]

  base_run_id        reports/intl_real_html/<base_run_id>/result.json   全量基线
  override_run_dir   任意目录（相对仓库根或绝对路径），其下需有 result.json

合并规则：按 use case id 覆盖基线条目，被覆盖的条目标记 rerun / merged_from_run。
"""
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML_REPORTS = os.path.join(ROOT, "reports", "intl_real_html")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)

    base_id = sys.argv[1]
    base_path = os.path.join(HTML_REPORTS, base_id, "result.json")
    base = load(base_path)

    merged = {c["id"]: dict(c) for c in base["cases"]}
    order = [c["id"] for c in base["cases"]]
    applied, extra_duration = [], 0.0

    for raw in sys.argv[2:]:
        d = raw if os.path.isabs(raw) else os.path.join(ROOT, raw)
        rp = os.path.join(d, "result.json")
        if not os.path.exists(rp):
            print(f"[warn] 缺少重跑结果，跳过：{rp}")
            continue
        rd = load(rp)
        run_id = os.path.basename(d.rstrip("/\\"))
        extra_duration += rd.get("duration_s") or 0
        n = 0
        for c in rd.get("cases", []):
            cid = c["id"]
            entry = dict(c)
            entry["rerun"] = True
            entry["merged_from_run"] = run_id
            merged[cid] = entry
            if cid not in order:
                order.append(cid)
            n += 1
        applied.append(f"{run_id}({n}条)")
        print(f"并入 {run_id}：{n} 条，用时 {rd.get('duration_s')}s")

    cases = [merged[cid] for cid in order]
    total = len(cases)
    passed = sum(1 for c in cases if c.get("status") == "PASS")
    failed = sum(1 for c in cases if c.get("status") == "FAIL")
    skipped = sum(1 for c in cases if c.get("status") == "SKIP")
    executed = total - skipped

    out_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_merged"
    out_dir = os.path.join(HTML_REPORTS, out_id)
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
        "base_run": base_id,
        "merged_runs": applied,
        "merge_note": (
            "全量基线 %s + 用例修订后重跑结果合并；被覆盖的条目标记 merged_from_run" % base_id
        ),
    }
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print()
    print(f"合并结果已生成: {out_dir}")
    print(f"总数 {total} | 通过 {passed} | 失败 {failed} | 跳过 {skipped} | 通过率 {result['pass_rate']}%")
    print(f"累计耗时 {result['duration_s']}s")
    print("非 PASS 明细:")
    bad = [c for c in cases if c.get("status") != "PASS"]
    for c in bad:
        print(f"  {c['status']} {c['id']} — {c.get('title', '')[:44]}")
    if not bad:
        print("  （无）")
    print()
    print("OUT_ID=" + out_id)


if __name__ == "__main__":
    main()
