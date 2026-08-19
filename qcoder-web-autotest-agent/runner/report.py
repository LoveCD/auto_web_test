# -*- coding: utf-8 -*-
"""报告器：将执行结果输出为 result.json / result.md / result.html。

HTML 报告包含：
- 执行概要（总数/通过/失败/耗时/浏览器）
- 用例明细（PASS/FAIL、失败步骤与断言信息）
- 模块 x 优先级覆盖矩阵
- 失败截图链接
"""
import datetime
import json
import os

REPORT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")


def new_run_id(suite: str) -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_{suite}"


def build_coverage_matrix(report: dict) -> list:
    """模块 x 优先级 用例统计。"""
    modules, prios = {}, {}
    for case in report["cases"]:
        modules.setdefault(case["module"], []).append(case)
        prios.setdefault(case["priority"], []).append(case)
    rows = []
    all_prios = ["P0", "P1", "P2"]
    for module in sorted(modules):
        row = {"module": module}
        for pr in all_prios:
            cs = [c for c in modules[module] if c["priority"] == pr]
            row[pr] = f"{sum(1 for c in cs if c['status'] == 'pass')}/{len(cs)}"
        cs = modules[module]
        row["total"] = f"{sum(1 for c in cs if c['status'] == 'pass')}/{len(cs)}"
        rows.append(row)
    return rows


def write_reports(report: dict, screenshot_dir: str = None) -> str:
    """写入 result.json / result.md / result.html，返回报告目录。"""
    out_dir = os.path.join(REPORT_ROOT, report["run_id"])
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    write_markdown(report, os.path.join(out_dir, "result.md"))
    write_html(report, os.path.join(out_dir, "report.html"), screenshot_dir)
    return out_dir


def write_markdown(report: dict, path: str):
    lines = [
        f"# Web AutoTest Report: {report['suite_id']}",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Profile: `{report['profile']}`",
        f"- Browser: `{report.get('browser', 'chromium')}`",
        f"- Total: {report['summary']['total']}",
        f"- Passed: {report['summary']['passed']}",
        f"- Failed: {report['summary']['failed']}",
        f"- Duration: {report['summary']['duration_seconds']}s",
        "",
        "## Cases",
        "",
    ]
    for case in report["cases"]:
        mark = "PASS" if case["status"] == "pass" else "FAIL"
        lines.append(f"- {mark} `{case['id']}` {case['title']} [{case['module']}/{case['priority']}]")
        for step in case["steps"]:
            if step["status"] == "fail":
                for fail in step["failures"]:
                    lines.append(f"  - Failed step `{step['action']}`: {fail}")
        if case.get("screenshot"):
            lines.append(f"  - Screenshot: `{case['screenshot']}`")
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_html(report: dict, path: str, screenshot_dir: str = None):
    matrix = build_coverage_matrix(report)
    summary = report["summary"]

    case_rows = []
    for case in report["cases"]:
        badge = ("<span class='ok'>PASS</span>" if case["status"] == "pass"
                 else "<span class='bad'>FAIL</span>")
        steps_html = []
        for step in case["steps"]:
            icon = "&#10004;" if step["status"] == "pass" else "&#10008;"
            cls = "st-ok" if step["status"] == "pass" else "st-bad"
            fails = "<br>".join(_esc(f) for f in step["failures"])
            detail = ""
            if fails:
                detail = f"<br><span class='fail-detail'>{fails}</span>"
            steps_html.append(
                f"<div class='step {cls}'>{icon} <code>{_esc(step['action'])}</code>{detail}</div>")
        shot = ""
        if case.get("screenshot") and screenshot_dir:
            name = os.path.basename(case["screenshot"])
            shot = f"<a class='shot' href='screenshots/{name}' target='_blank'>screenshot</a>"
        case_rows.append(
            f"<tr><td><code>{_esc(case['id'])}</code></td><td>{badge}</td>"
            f"<td>{_esc(case['title'])}</td><td>{_esc(case['module'])}</td>"
            f"<td>{_esc(case['priority'])}</td><td>{''.join(steps_html)}{shot}</td></tr>")

    matrix_rows = []
    for row in matrix:
        matrix_rows.append(
            f"<tr><td>{row['module']}</td><td>{row['P0']}</td><td>{row['P1']}</td>"
            f"<td>{row['P2']}</td><td><b>{row['total']}</b></td></tr>")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Web AutoTest Report - {_esc(report['suite_id'])}</title>
<style>
body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; margin: 0; background: #f4f6fa; color: #24304a; }}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 28px 20px; }}
h1 {{ font-size: 22px; color: #0b4d8c; }}
.meta {{ color: #6b7690; font-size: 13px; margin: 6px 0 20px; }}
.cards {{ display: flex; gap: 14px; margin: 18px 0; }}
.card {{ flex: 1; background: #fff; border-radius: 8px; padding: 16px 18px; box-shadow: 0 1px 3px rgba(0,0,0,.07); }}
.card .num {{ font-size: 26px; font-weight: 700; }}
.card .lbl {{ color: #6b7690; font-size: 12px; margin-top: 2px; }}
.green {{ color: #1d8a4e; }} .red {{ color: #d93026; }} .blue {{ color: #0b4d8c; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.07); }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eef1f6; font-size: 13px; vertical-align: top; }}
th {{ background: #f7f9fc; color: #4a5670; font-weight: 600; }}
.ok {{ color: #1d8a4e; font-weight: 700; }} .bad {{ color: #d93026; font-weight: 700; }}
.step {{ font-size: 12px; padding: 2px 0; }}
.st-ok {{ color: #1d8a4e; }} .st-bad {{ color: #d93026; }}
.fail-detail {{ color: #b04a3e; }}
.shot {{ font-size: 12px; color: #0b4d8c; margin-left: 6px; }}
h2 {{ font-size: 16px; color: #0b4d8c; margin: 26px 0 12px; }}
</style></head><body><div class="wrap">
<h1>Web AutoTest Report: {_esc(report['suite_id'])}</h1>
<div class="meta">Run ID: <code>{_esc(report['run_id'])}</code> &nbsp;|&nbsp; Profile: <code>{_esc(report['profile'])}</code>
&nbsp;|&nbsp; Browser: {_esc(report.get('browser', 'chromium'))} &nbsp;|&nbsp; Generated: {_esc(report['generated_at'])}</div>
<div class="cards">
  <div class="card"><div class="num blue">{summary['total']}</div><div class="lbl">Total Cases</div></div>
  <div class="card"><div class="num green">{summary['passed']}</div><div class="lbl">Passed</div></div>
  <div class="card"><div class="num red">{summary['failed']}</div><div class="lbl">Failed</div></div>
  <div class="card"><div class="num">{summary['duration_seconds']}s</div><div class="lbl">Duration</div></div>
</div>
<h2>Coverage Matrix (passed/total by module x priority)</h2>
<table><tr><th>Module</th><th>P0</th><th>P1</th><th>P2</th><th>Total</th></tr>
{''.join(matrix_rows)}
</table>
<h2>Case Details</h2>
<table><tr><th>ID</th><th>Result</th><th>Title</th><th>Module</th><th>Priority</th><th>Steps</th></tr>
{''.join(case_rows)}
</table>
</div></body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
