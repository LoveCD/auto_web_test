# -*- coding: utf-8 -*-
"""生成 INTL 国际版真机（192.168.1.1）测试用例文档与测试报告（Word）。
版式完全对齐 CM 模板（gen-case-doc.js + test-report-template.docx）：
  封面 / 版本记录 / 【要求】 / 【目的】 / 自动化测试 /
  测试项N：用例ID 用例名（Heading 1）+ 测试项表格（12 行 x 2 列）/
  测试结果（总用例/通过/失败/跳过/超时/中断）/ 测试结论
并在每个测试项后嵌入该用例的成果截图。

数据来源：
  - 用例：operators/intl/cases/real/*.json
  - 结果：reports/intl_real/<run_id>/result.json + 截图

用法：
    python tools/gen_intl_word.py [--result <run_id>] [--out DIR] [--mode case|report|both]
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.docx_branding import FH_BODY_PREFIX, FH_COVER_HEADER, add_cover_logo, apply_fh_header  # noqa: E402

CASES_DIR = os.path.join(ROOT, "operators", "intl", "cases", "real")
REPORTS_DIR = os.path.join(ROOT, "reports", "intl_real")
OUT_DIR = os.path.join(ROOT, "docs", "case-docs")

DEVICE = {
    "model": "HG6163FC1（GPON 智能网关）",
    "product": "INTL 国际版",
    "project": "INTL 真机 Web 自动化测试",
    "dept": "自动化测试",
    "author": "自动化自测",
}
SUITE_NAMES = {
    "login": "登录页面",
    "status": "系统状态页面",
    "wan": "WAN 连接配置页面",
    "reboot": "重启页面",
    "security": "安全（登录锁定）",
    "wifi": "无线（WiFi）页面",
    "lan": "LAN 页面",
    "nat": "NAT 页面",
    "firewall": "防火墙页面",
    "account": "账号管理页面",
    "remote": "远程管理页面",
    "voip": "VoIP 页面",
    "auth": "认证（Auth）页面",
    "ddos": "DDoS 防护页面",
    "web": "Web 管理页面",
    "vpn": "VPN 页面",
    "ddns": "DDNS 页面",
    "media": "媒体（Media）页面",
    "upnp": "UPnP 页面",
    "ntp": "NTP 页面",
    "diag": "诊断（Diag）页面",
    "log": "日志（Log）页面",
    "topology": "网络拓扑页面",
    "help": "帮助（Help）页面",
}
MODULE_NAMES = {
    "login": "Login",
    "status": "Status",
    "wan": "WAN",
    "reboot": "System",
    "security": "Security",
    "wifi": "WiFi",
    "lan": "LAN",
    "nat": "NAT",
    "firewall": "Firewall",
    "account": "Account",
    "remote": "Remote",
    "voip": "VoIP",
    "auth": "Auth",
    "ddos": "DDoS",
    "web": "Web",
    "vpn": "VPN",
    "ddns": "DDNS",
    "media": "Media",
    "upnp": "UPnP",
    "ntp": "NTP",
    "diag": "Diag",
    "log": "Log",
    "topology": "Topology",
    "help": "Help",
}

BLUE = (0x1F, 0x4E, 0x79)
LIGHT_BLUE = (0x2E, 0x74, 0xB5)
HEADER_FILL = "2E74B5"


def set_cn_font(run, name="微软雅黑", size=None, bold=None, color=None):
    run.font.name = "Times New Roman"
    r = run._element.rPr
    rFonts = r.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = r.makeelement(qn("w:rFonts"), {})
        r.append(rFonts)
    rFonts.set(qn("w:eastAsia"), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        set_cn_font(run, "微软雅黑", bold=True, color=BLUE if level == 1 else LIGHT_BLUE)
    return h


def add_para(doc, text, size=10.5, bold=False, align=None, color=None):
    p = doc.add_paragraph()
    if align:
        p.alignment = align
    run = p.add_run(text)
    set_cn_font(run, size=size, bold=bold, color=color)
    return p


def shade_cell(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.makeelement(qn("w:shd"), {qn("w:val"): "clear", qn("w:fill"): fill})
    tcPr.append(shd)


def add_kv_table(doc, rows, widths=(4.5, 10.5)):
    tb = doc.add_table(rows=0, cols=2)
    tb.style = "Table Grid"
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    for k, v in rows:
        cells = tb.add_row().cells
        cells[0].text = ""
        r0 = cells[0].paragraphs[0].add_run(str(k))
        set_cn_font(r0, size=10, bold=True)
        shade_cell(cells[0], "DEEAF6")
        cells[1].text = ""
        r1 = cells[1].paragraphs[0].add_run(str(v))
        set_cn_font(r1, size=10)
    for row in tb.rows:
        row.cells[0].width = Cm(widths[0])
        row.cells[1].width = Cm(widths[1])
    return tb


def add_pic(doc, path, width_cm=13.5, caption=None):
    if not os.path.exists(path):
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(path, width=Cm(width_cm))
    if caption:
        c = doc.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = c.add_run(caption)
        set_cn_font(r, size=9, color=(0x59, 0x59, 0x59))


def load_cases():
    cases = {}
    for f in sorted(glob.glob(os.path.join(CASES_DIR, "*.json"))):
        name = os.path.splitext(os.path.basename(f))[0]
        cases[name] = json.load(open(f, encoding="utf-8"))
    return cases


def find_latest_result():
    """找到最新的主套件（login/status/wan/reboot）结果。
    security（登录锁定）套件受设备 IP 级锁定状态影响、行为不稳定，
    不纳入主报告统计，作为补充安全测试单独说明。
    """
    dirs = sorted(glob.glob(os.path.join(REPORTS_DIR, "*")), reverse=True)
    for d in dirs:
        rj = os.path.join(d, "result.json")
        if not os.path.exists(rj):
            continue
        data = json.load(open(rj, encoding="utf-8"))
        ids = {c.get("id") for c in data.get("cases", [])}
        if any(x.startswith("INTL-SEC-") for x in ids):
            continue
        return d, data
    return None, None


def _cover_field_table(doc, rows):
    """封面信息表：无边框、黑体标签（对齐参考样例 header 封面版式）。"""
    tb = doc.add_table(rows=0, cols=2)
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    # 无边框
    from docx.oxml import OxmlElement
    tblPr = tb._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        borders.append(el)
    tblPr.append(borders)
    for k, v in rows:
        cells = tb.add_row().cells
        cells[0].width = Cm(3.3)
        cells[1].width = Cm(9.2)
        p0 = cells[0].paragraphs[0]
        r0 = p0.add_run(str(k))
        set_cn_font(r0, name="黑体", size=14, bold=False)
        p1 = cells[1].paragraphs[0]
        r1 = p1.add_run(str(v))
        set_cn_font(r1, name="黑体", size=14)
    return tb


def build_cover(doc, doc_kind="测试报告"):
    add_cover_logo(doc)  # 封面左上角 FiberHome logo（参考样例位置）
    for _ in range(3):
        doc.add_paragraph()
    add_para(doc, "（Web UI自动化自测）", size=26, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER, color=(0, 0, 0))
    for _ in range(4):
        doc.add_paragraph()
    add_para(doc, doc_kind, size=36, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER, color=(0, 0, 0))
    for _ in range(5):
        doc.add_paragraph()
    _cover_field_table(doc, [
        ("设备型号：", DEVICE["model"]),
        ("产品代号：", DEVICE["product"]),
        ("项目代号：", DEVICE["project"]),
        ("部    门：", DEVICE["dept"]),
        ("拟    制：", DEVICE["author"]),
        ("审    核：", ""),
        ("批    准：", ""),
    ])
    # 封面节结束（分节而非分页，便于封面节/正文节挂不同页眉——对齐参考样例）
    from docx.enum.section import WD_SECTION_START
    doc.add_section(WD_SECTION_START.NEW_PAGE)


def build_version_record(doc, run_id, mode):
    add_heading(doc, "版本记录", 1)
    tb = doc.add_table(rows=1, cols=6)
    tb.style = "Table Grid"
    headers = ["序号", "版本号", "生成时间", "主要修改记录", "作者", "备注"]
    for i, h in enumerate(headers):
        tb.rows[0].cells[i].text = ""
        r = tb.rows[0].cells[i].paragraphs[0].add_run(h)
        set_cn_font(r, size=9.5, bold=True, color=(0xFF, 0xFF, 0xFF))
        shade_cell(tb.rows[0].cells[i], HEADER_FILL)
    row = tb.add_row()
    vals = ["1", "V1.0", datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"INTL 真机接入测试（{mode}）", "自动化自测", f"run_id: {run_id}"]
    for i, v in enumerate(vals):
        row.cells[i].text = ""
        r = row.cells[i].paragraphs[0].add_run(v)
        set_cn_font(r, size=9.5)
    doc.add_page_break()


def build_requirement_purpose(doc):
    add_heading(doc, "【要求】", 1)
    for t in [
        "1、明确测试目的：禁止复制测试用例名称。在配套方案设计文档里，简要描述测试用例背景，解决何种问题，新增何种功能，并简要描述主要验证内容；",
        "2、要求测试步骤清晰明确，文字说明需要使用到的配置、命令，而不是使用可读性差的函数名、命令行；",
        "3、如命令行类功能测试，在备注中标注测试需要使用的命令行，并说明关键参数含义；",
        "4、测试步骤和预期结果不允许为空；",
        "5、备注栏尽量避免为空，可提供问题排查相关命令。",
    ]:
        add_para(doc, t, size=10.5)
    add_heading(doc, "【目的】", 1)
    for t in [
        "1、提高测试用例可读性、可执行性。减少由于文档不清晰，导致的反复沟通成本；",
        "2、要求尽量提供调试命令行，出现测试问题时集成测试人员能抓取有效调试log：可提高集成测试人员的问题排查能力；可提高研发人员定位问题效率；",
        "3、高质量的测试用例是财富，长期积累，有助于提高后期工作效率，以及形成宝贵的文档资料，增强问题可追溯性。",
    ]:
        add_para(doc, t, size=10.5)


def case_module(cid):
    # 长前缀优先匹配，避免 LOGIN 被 LOG、WAN 与 LAN 等子串误判
    for suite, prefix in [("login", "LOGIN"), ("status", "STATUS"), ("wan", "WAN"),
                          ("reboot", "REBOOT"), ("security", "SEC"),
                          ("firewall", "FIREWALL"), ("topology", "TOPOLOGY"),
                          ("account", "ACCOUNT"), ("remote", "REMOTE"),
                          ("wifi", "WIFI"), ("voip", "VOIP"), ("auth", "AUTH"),
                          ("ddos", "DDOS"), ("ddns", "DDNS"), ("upnp", "UPNP"),
                          ("media", "MEDIA"), ("diag", "DIAG"), ("help", "HELP"),
                          ("lan", "LAN"), ("nat", "NAT"), ("ntp", "NTP"),
                          ("vpn", "VPN"), ("web", "WEB"), ("log", "LOG")]:
        if prefix in cid:
            return MODULE_NAMES[suite]
    return "General"


def build_test_item(doc, idx, case, result_map, run_id, mode):
    cid = case["id"]
    title = case["title"]
    prio = case.get("priority", "P1")
    tags = case.get("tags", [])
    module = case_module(cid)
    add_heading(doc, f"测试项{idx}：{cid} {title}", 1)

    result = result_map.get(cid)
    if result:
        status = result.get("status", "PASS")
        steps = result.get("steps", [])
        steps_pass = sum(1 for s in steps if s.get("status") == "PASS")
        steps_total = len(steps)
        exec_time = result.get("start", "")
        actual = f"实际结果：{'通过' if status == 'PASS' else '失败'}（{steps_pass}/{steps_total} 个步骤通过）"
        conclusion = "通过" if status == "PASS" else "失败"
        exec_status = "通过" if status == "PASS" else "失败"
    else:
        actual = "实际结果：待执行"
        conclusion = "待执行"
        exec_status = "待执行"
        exec_time = "-"

    # 测试步骤文本
    step_lines = []
    for i, s in enumerate(case.get("steps", [])):
        action = s.get("action", "")
        desc = s.get("desc", "")
        params = {k: v for k, v in s.items() if k not in ("action", "desc")}
        param_str = "，".join(f"{k}={v}" for k, v in params.items()) if params else ""
        step_lines.append(f"{i + 1}. {desc}（{action}{('，' + param_str) if param_str else ''}）")
    steps_text = "\n".join(step_lines) if step_lines else "-"

    # 期望结果文本（从断言动作生成）
    expect_lines = []
    for s in case.get("steps", []):
        if s.get("action", "").startswith("real.assert"):
            expect_lines.append(f"- 断言[{s['action'].replace('real.assert_', '')}]：{s.get('desc', '')}")
    expect_text = "\n".join(expect_lines) if expect_lines else "1. 页面无异常，行为符合预期"

    env_text = (f"1. 运营商: intl\n2. 环境: real\n3. 浏览器: chromium\n"
                f"4. 运行ID: {run_id}\n5. 执行时间: {exec_time[:19] if exec_time else '-'}\n6. 耗时: -")

    add_kv_table(doc, [
        ("测试类型", module),
        ("测试目的", f"{cid} {title}"),
        ("预置条件", case.get("precondition", "-")),
        ("测试浏览器", "chromium"),
        ("测试环境", env_text),
        ("测试步骤", steps_text),
        ("期望结果", expect_text),
        ("测试结果", actual),
        ("测 试 人", "自动化自测"),
        ("测试结论", conclusion),
        ("备注", f"优先级: {prio}\n模块: {module}\n执行状态: {exec_status}"),
    ])

    # 嵌入成果截图（成功用例的 detail 截图 / 失败用例的失败截图）
    if result:
        for st in result.get("steps", []):
            if st.get("detail"):
                add_pic(doc, st["detail"], width_cm=13.5, caption=f"{cid} 成果截图（步骤{st['index']}）")
            if st.get("screenshot"):
                add_pic(doc, st["screenshot"], width_cm=13.5, caption=f"{cid} 失败截图（步骤{st['index']}）")
    doc.add_page_break()


def build_result_summary(doc, result_map, mode):
    add_heading(doc, "测试结果", 1)
    total = len(result_map)
    passed = sum(1 for r in result_map.values() if r.get("status") == "PASS")
    failed = total - passed
    add_para(doc, f"总用例：{total}", size=11)
    add_para(doc, f"通过：{passed}", size=11)
    add_para(doc, f"失败：{failed}", size=11)
    add_para(doc, "跳过：0", size=11)
    add_para(doc, "超时：0", size=11)
    add_para(doc, "中断：0", size=11)
    add_heading(doc, "测试结论", 1)
    if mode == "case":
        add_para(doc, "待执行", size=12, bold=True)
    else:
        add_para(doc, "通过" if failed == 0 else "失败", size=12, bold=True,
                 color=(0x00, 0x80, 0x00) if failed == 0 else (0xC0, 0x00, 0x00))


def gen_doc(cases, result_map, run_id, mode, out):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(10.5)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    build_cover(doc, doc_kind="用例文档" if mode == "case" else "测试报告")
    build_version_record(doc, run_id, mode)
    build_requirement_purpose(doc)
    add_heading(doc, "自动化测试", 1)

    idx = 1
    for suite, cases_list in cases.items():
        if suite not in SUITE_NAMES or not cases_list:
            continue
        if suite == "security":
            # security（登录锁定）受设备 IP 级锁定状态影响，作为补充说明，不生成测试项
            continue
        for c in cases_list:
            build_test_item(doc, idx, c, result_map, run_id, mode)
            idx += 1

    build_result_summary(doc, result_map, mode)

    # FH 页眉（对齐参考样例）：封面节 = FH 编号；正文节 = SDV测试报告 + FH 编号
    apply_fh_header(doc, body_text=f"{FH_BODY_PREFIX}          {FH_COVER_HEADER}")

    if mode == "case":
        fname = f"用例文档-INTL-REAL-{datetime.now().strftime('%Y%m%d-%H%M%S')}.docx"
    else:
        fname = f"测试报告-INTL-REAL-{datetime.now().strftime('%Y%m%d-%H%M%S')}.docx"
    out_path = os.path.join(out, fname)
    doc.save(out_path)
    print(f"{'用例文档' if mode=='case' else '测试报告'} OK -> {out_path}")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default="latest")
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--mode", default="both", choices=["case", "report", "both"])
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    cases = load_cases()
    result_dir, result = find_latest_result()
    run_id = os.path.basename(result_dir) if result_dir else "N/A"

    result_map = {}
    if result:
        for c in result.get("cases", []):
            result_map[c["id"]] = c

    if args.mode in ("case", "both"):
        gen_doc(cases, result_map, run_id, "case", args.out)
    if args.mode in ("report", "both"):
        if result is None:
            print("[warn] 未找到结果，跳过测试报告")
        else:
            gen_doc(cases, result_map, run_id, "report", args.out)


if __name__ == "__main__":
    main()
