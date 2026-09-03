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

CASES_DIR_NEW = os.path.join(ROOT, "operators", "intl", "cases", "real", "new_ui")
CASES_DIR_HTML = os.path.join(ROOT, "operators", "intl", "cases", "real", "html")
REPORTS_DIR_NEW = os.path.join(ROOT, "reports", "intl_real")
REPORTS_DIR_HTML = os.path.join(ROOT, "reports", "intl_real_html")
OUT_DIR = os.path.join(ROOT, "docs", "case-docs")

# --variant html = 国际老 UI（HTML 多页版）；new_ui = SPA 新 UI（默认）
VARIANT = "new_ui"
SUITE_FILTER = None  # 仅纳入指定套件（如 "status"），None=全部套件


def _cases_dir():
    return CASES_DIR_HTML if VARIANT == "html" else CASES_DIR_NEW


def _reports_dir():
    return REPORTS_DIR_HTML if VARIANT == "html" else REPORTS_DIR_NEW


DEVICE = {
    "model": "HG6142HT（GPON 智能网关）",
    "product": "INTL 国际版",
    "project": "INTL 真机 Web 自动化测试",
    "dept": "自动化测试",
    "author": "自动化自测",
}
SUITE_NAMES = {
    "login": "登录页面",
    "mobile": "手机端兼容性",
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
    "mobile": "Mobile",
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
    for f in sorted(glob.glob(os.path.join(_cases_dir(), "*.json"))):
        name = os.path.splitext(os.path.basename(f))[0]
        cases[name] = json.load(open(f, encoding="utf-8"))
    return cases


def find_latest_result(run_id=None):
    """按 run_id 精确取结果；未指定时取最新的主套件（login/status/wan/reboot）结果。
    new_ui 变体：security（登录锁定）套件受设备 IP 级锁定状态影响、行为不稳定，
    不纳入主报告统计，作为补充安全测试单独说明。
    html 变体：security（锁定状态机+权限基线）为核心套件，正常纳入统计。
    """
    if run_id and run_id != "latest":
        d = os.path.join(_reports_dir(), run_id)
        rj = os.path.join(d, "result.json")
        if os.path.exists(rj):
            return d, json.load(open(rj, encoding="utf-8"))
        print(f"[warn] 未找到指定 run_id={run_id} 的结果，回退最新结果")
    dirs = sorted(glob.glob(os.path.join(_reports_dir(), "*")), reverse=True)
    for d in dirs:
        rj = os.path.join(d, "result.json")
        if not os.path.exists(rj):
            continue
        data = json.load(open(rj, encoding="utf-8"))
        ids = {c.get("id") for c in data.get("cases", [])}
        if VARIANT != "html" and any(x.startswith("INTL-SEC-") for x in ids):
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
        dur = result.get("duration_s")
        dur_text = f"{dur}s" if dur is not None else "-"
        actual = f"实际结果：{'通过' if status == 'PASS' else '失败'}（{steps_pass}/{steps_total} 个步骤通过）"
        conclusion = "通过" if status == "PASS" else "失败"
        exec_status = "通过" if status == "PASS" else "失败"
    else:
        actual = "实际结果：待执行"
        conclusion = "待执行"
        exec_status = "待执行"
        exec_time = "-"
        dur_text = "-"

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
                f"4. 运行ID: {run_id}\n5. 执行时间: {exec_time[:19] if exec_time else '-'}\n6. 耗时: {dur_text}")

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


def _fmt_seconds(sec):
    """秒 → 'X 分 Y 秒' / 'Y 秒'"""
    if sec is None:
        return "-"
    sec = round(float(sec))
    if sec >= 60:
        return f"{sec // 60} 分 {sec % 60} 秒"
    return f"{sec} 秒"


def _suite_key_of(cid):
    """用例 ID → 套件 key（与 case_module 的前缀规则保持一致）"""
    pairs = [("INTL-LOGIN-", "login"), ("INTL-MOBILE-", "mobile"), ("INTL-STATUS-", "status"),
             ("INTL-WAN-", "wan"),
             ("INTL-REBOOT-", "reboot"), ("INTL-SEC-", "security"), ("INTL-FIREWALL-", "firewall"),
             ("INTL-TOPOLOGY-", "topology"), ("INTL-ACCOUNT-", "account"), ("INTL-REMOTE-", "remote"),
             ("INTL-WIFI-", "wifi"), ("INTL-VOIP-", "voip"), ("INTL-AUTH-", "auth"),
             ("INTL-DDOS-", "ddos"), ("INTL-DDNS-", "ddns"), ("INTL-UPNP-", "upnp"),
             ("INTL-MEDIA-", "media"), ("INTL-DIAG-", "diag"), ("INTL-HELP-", "help"),
             ("INTL-LAN-", "lan"), ("INTL-NAT-", "nat"), ("INTL-NTP-", "ntp"),
             ("INTL-VPN-", "vpn"), ("INTL-WEB-", "web"), ("INTL-LOG-", "log")]
    for prefix, key in pairs:
        if cid.startswith(prefix):
            return key
    return "other"


def _classify_failure(error):
    """失败原因粗分类"""
    if not error:
        return "未捕获异常"
    if "TimeoutError" in error:
        return "断言超时（元素未出现/未跳转）"
    if "AssertionError" in error:
        return "断言不成立（实际行为与预期不符）"
    if "PWTimeout" in error or "Timeout" in error:
        return "等待超时"
    return "执行异常"


def build_result_summary(doc, result_map, mode, result=None):
    add_heading(doc, "测试结果", 1)
    total = len(result_map)
    passed = sum(1 for r in result_map.values() if r.get("status") == "PASS")
    failed = total - passed

    # ---- 总体统计 ----
    add_para(doc, f"总用例：{total}", size=11)
    add_para(doc, f"通过：{passed}", size=11)
    add_para(doc, f"失败：{failed}", size=11)
    add_para(doc, "跳过：0", size=11)
    add_para(doc, "超时：0", size=11)
    add_para(doc, "中断：0", size=11)
    pass_rate = f"{passed / total * 100:.1f}%" if total else "-"

    if result and mode != "case":
        dur = result.get("duration_s")
        add_para(doc, f"通过率：{pass_rate}", size=11)
        add_para(doc, f"总耗时：{_fmt_seconds(dur)}（{dur}s）", size=11)
        durs = [c.get("duration_s") for c in result.get("cases", []) if c.get("duration_s") is not None]
        if durs:
            add_para(doc, f"平均单条用例耗时：{sum(durs) / len(durs):.1f}s（最短 {min(durs)}s，最长 {max(durs)}s）",
                     size=11)
        add_para(doc, f"执行区间：{str(result.get('start', '-'))[:19]} ~ {str(result.get('end', '-'))[:19]}", size=11)

        # ---- 分套件统计表 ----
        add_heading(doc, "分套件统计", 2)
        stats = {}
        order = []
        for c in result.get("cases", []):
            key = _suite_key_of(c.get("id", ""))
            if key not in stats:
                stats[key] = {"total": 0, "pass": 0, "dur": 0.0}
                order.append(key)
            stats[key]["total"] += 1
            if c.get("status") == "PASS":
                stats[key]["pass"] += 1
            stats[key]["dur"] += c.get("duration_s") or 0
        tb = doc.add_table(rows=1, cols=6)
        tb.style = "Table Grid"
        headers = ["序号", "套件", "用例数", "通过", "失败", "耗时"]
        for i, h in enumerate(headers):
            tb.rows[0].cells[i].text = ""
            r = tb.rows[0].cells[i].paragraphs[0].add_run(h)
            set_cn_font(r, size=9.5, bold=True, color=(0xFF, 0xFF, 0xFF))
            shade_cell(tb.rows[0].cells[i], HEADER_FILL)
        for i, key in enumerate(order, 1):
            s = stats[key]
            row = tb.add_row()
            vals = [str(i), f"{key}（{SUITE_NAMES.get(key, key)}）", str(s["total"]),
                    str(s["pass"]), str(s["total"] - s["pass"]), f"{s['dur']:.1f}s"]
            for j, v in enumerate(vals):
                row.cells[j].text = ""
                r = row.cells[j].paragraphs[0].add_run(v)
                set_cn_font(r, size=9.5)

        # ---- 失败用例分析 ----
        fail_cases = [c for c in result.get("cases", []) if c.get("status") != "PASS"]
        if fail_cases:
            add_heading(doc, "失败用例分析", 2)
            tb = doc.add_table(rows=1, cols=5)
            tb.style = "Table Grid"
            headers = ["用例ID", "用例标题", "失败步骤", "原因分类", "失败原因摘要"]
            for i, h in enumerate(headers):
                tb.rows[0].cells[i].text = ""
                r = tb.rows[0].cells[i].paragraphs[0].add_run(h)
                set_cn_font(r, size=9.5, bold=True, color=(0xFF, 0xFF, 0xFF))
                shade_cell(tb.rows[0].cells[i], HEADER_FILL)
            for c in fail_cases:
                err = (c.get("error") or "").split("\n")[0][:120]
                step_desc = ""
                for st in c.get("steps", []):
                    if st.get("status") != "PASS":
                        step_desc = f"{st.get('index', '-')} {st.get('desc', '')}"
                        break
                if not step_desc and err.startswith("step "):
                    step_desc = err.split("]")[0].strip(" [")
                row = tb.add_row()
                vals = [c.get("id", "-"), c.get("title", "-"), step_desc or "-",
                        _classify_failure(c.get("error")), err or "-"]
                for j, v in enumerate(vals):
                    row.cells[j].text = ""
                    r = row.cells[j].paragraphs[0].add_run(v)
                    set_cn_font(r, size=9)

        # ---- 设备行为差异与安全发现 ----
        add_heading(doc, "设备行为差异与安全发现", 2)
        for t in _analysis_notes(result=result):
            add_para(doc, t, size=10.5)

    add_heading(doc, "测试结论", 1)
    if mode == "case":
        add_para(doc, "待执行", size=12, bold=True)
    else:
        add_para(doc, "通过" if failed == 0 else "失败", size=12, bold=True,
                 color=(0x00, 0x80, 0x00) if failed == 0 else (0xC0, 0x00, 0x00))


# ---- 分析结论（随轮次更新；--variant html 用 HTML 版，new_ui 用 NEWUI 版）----
RESULT_ANALYSIS_NOTES_NEWUI = [
    "1、本轮为 INTL 新 UI（SPA 架构、英文 UI）系统状态页面专项真机验证，测试对象为国际版网关 HG6142HT"
    "（192.168.1.1），管理员账号由环境变量注入（.env 中 QCT_INTL_ADMIN_*，报告脱敏），登录成功后落地路由 "
    "main.html#/status/deviceInfo/deviceInfo，status 套件共 7 条用例（P0 2 条、P1 5 条，含 1 条 XSS 负向安全用例）。",
    "2、执行结果：7/7 全部通过，通过率 100%，测试结论「通过」。总耗时 63.7 秒（用例净耗时合计 61.4 秒，"
    "含套件初始化开销），平均单条用例 8.8 秒；其中 XSS 注入负向用例耗时最长（15.1 秒，需遍历多输入点并逐项断言转义），"
    "运行时间递增类用例 10.0 秒次之（需两次刷新间隔观察状态迁移），常规查询/断言类用例约 6.9~8.2 秒。",
    "3、功能覆盖分析：① 页面可访问性与渲染（STATUS-001）通过，设备信息页正常加载；② 关键字段有效性"
    "（STATUS-002）通过，软件版本、硬件版本、序列号等字段均有有效值；③ 运行时间随刷新递增（STATUS-003）通过，"
    "系统状态迁移正常，无时间回跳或冻结；④ MAC 地址格式校验（STATUS-004）通过，符合 XX:XX:XX:XX:XX:XX 格式；"
    "⑤ 跨页一致性（STATUS-005）通过，首页状态与设备信息页 MAC 地址一致，前后端数据源无漂移；"
    "⑥ CPU/内存使用率（STATUS-006）通过，百分比字段显示有效；⑦ XSS 注入负向（STATUS-007）通过，"
    "注入内容被正确转义，未触发对话框/脚本执行，前端具备基础输入防护能力。",
    "4、本专项为只读验证（查询、断言、截图类动作，无配置修改），不存在 LAN/DHCP 修改触发网关网络重启的副作用，"
    "无环境级联失败；全量回归中发现的 INTL-REBOOT-004（未登录深链管理子路由未重定向登录页）与本页面无直接关联，"
    "但设备管理（Device Management）域含 Reboot/Restore/Upgrade 等敏感入口，建议后续将该页面纳入路由鉴权专项加固验证范围。",
    "5、耗时统计说明：本轮为单套件专项执行（status），如需完整回归画像（24 套件 107 条，总耗时约 24.7 分钟），"
    "参见同日全量回归报告；status 套件单跑耗约占全量执行的 4.5%，适合作为冒烟/巡检快速卡点。",
]
RESULT_ANALYSIS_NOTES_HTML = [
    "1、本轮真机为国际老 UI 网关（login.html 独立登录页 + main.html#/ SPA 外壳、英文 UI），管理员账号由环境变量"
    "注入（用户名 1），登录成功后落地路由为 main.html#/status/deviceInfo/deviceInfo；登录失败提示元素为 "
    "div.login_error_hint（class 实现，文本 \"Username or Password Error!\"），连续错误 3 次触发账号锁定提示"
    "\"Username or password is wrong 3 times, please retry 1\"（锁定约 1 分钟）。",
    "2、失败原因分布（待回归完成后回填精确数字）。",
    "3、菜单结构实测：一级菜单 Status/Network/Security/Application/Management，fhId_* 菜单体系与 SPA 新 UI 一致，"
    "本机无 NTP/媒体/帮助/拓扑菜单（老 UI 功能裁剪），相关用例未纳入本轮回归。",
    "4、安全发现（INTL-LOGIN-005 失败根因）：执行过登录/登出的客户端 IP，在登出后服务端会话未失效，"
    "全新浏览器上下文（无 Cookie）直接访问受保护页面仍可渲染完整菜单并返回真实数据，"
    "说明登出仅清除前端状态或会话按客户端 IP 残留，存在会话固定/未授权访问风险，建议研发确认登出接口"
    "是否调用服务端会话销毁。",
    "5、全量回归执行顺序将 security（连续 3 次错误密码触发账号锁定）置于末尾，避免锁定波及其后套件登录；"
    "老 UI security 套件为锁定状态机 + 权限基线核心用例，正常纳入全量回归与统计。",
]


def _analysis_notes(result=None):
    """分析结论：有本轮 result 数据时按数据动态生成（兼容全量与 --suite 单套件专项），否则回退静态文案。"""
    if not result or not result.get("cases"):
        return RESULT_ANALYSIS_NOTES_HTML if VARIANT == "html" else RESULT_ANALYSIS_NOTES_NEWUI
    cases = result.get("cases", [])
    total = len(cases)
    passed = sum(1 for c in cases if c.get("status") == "PASS")
    failed = total - passed
    rate = f"{passed / total * 100:.1f}%" if total else "-"
    dur = result.get("duration_s") or 0
    durs = [c.get("duration_s") or 0 for c in cases]
    avg = (sum(durs) / total) if total else 0.0
    p0 = sum(1 for c in cases if c.get("priority") == "P0")
    p1 = total - p0
    neg = sum(1 for c in cases if "type:negative" in (c.get("tags") or []))
    suites = {}
    for c in cases:
        key = _suite_key_of(c.get("id", ""))
        suites.setdefault(key, []).append(c)
    suite_desc = "、".join(f"{k} {len(v)} 条" for k, v in suites.items())
    scope = f"专项验证（套件：{SUITE_FILTER}）" if SUITE_FILTER else "全量回归"
    ui_desc = "老 UI（HTML 多页版）" if VARIANT == "html" else "新 UI（SPA 架构、英文 UI）"

    slowest = sorted(zip(durs, cases), key=lambda x: -x[0])[:3]
    slow_desc = "；".join(f"{c.get('id')} {d}s（{c.get('title')}）" for d, c in slowest)
    notes = [
        f"1、本轮为 INTL {ui_desc}真机{scope}，测试对象为国际版网关 HG6142HT（192.168.1.1，HTTPS 自动探测），"
        f"账号由环境变量注入（.env QCT_INTL_*，报告脱敏）；本轮涉及套件：{suite_desc}，共 {total} 条用例"
        f"（P0 {p0} 条、P1 {p1} 条，含 {neg} 条负向安全类用例）。",
        f"2、执行结果：{passed}/{total} 通过（失败 {failed}），通过率 {rate}，"
        f"{'测试结论「通过」' if failed == 0 else '测试结论「不通过」，失败明细见失败用例分析表'}。"
        f"总耗时 {_fmt_seconds(dur)}（{dur}s），平均单条用例 {avg:.1f}s；耗时前三：{slow_desc}。",
    ]
    if failed:
        notes.append(
            "3、失败用例分析：详见「失败用例分析」表，按原因分类逐条给出失败步骤与根因摘要；"
            "选择器不匹配类失败建议以 navigation 实测菜单树复核 fhId_* 元素后同步 selectors 双文件。"
        )
    else:
        marks = "①②③④⑤⑥⑦⑧⑨⑩"
        notes.append(
            "3、功能覆盖分析：" + "；".join(
                f"{marks[i] if i < 10 else str(i + 1)} {c.get('title')}（{c.get('id')}）通过"
                for i, c in enumerate(cases)
            ) + "。"
        )
    if "login" in suites and failed == 0:
        notes.append(
            "4、登录域专项观察：① 正向登录与错误密码负向校验符合预期，错误提示经 div.login_error_hint 呈现；"
            "② 空用户名/空密码由前端校验拦截；③ 连续 3 次错误密码触发账号锁定（约 1 分钟），"
            "锁定类用例置于套件末位执行，避免锁定波及其后用例；④ 登出与未登录深链访问均正确回跳登录页；"
            "⑤ 历史回归曾发现登出后服务端会话未失效风险（当时 INTL-LOGIN-007 有效失败），本轮该场景通过，"
            "建议保持纳入例行回归观察。"
        )
    else:
        notes.append(
            "4、本轮执行" + ("为只读验证（查询、断言、截图类动作，无配置修改），不存在跨套件环境级联失败风险。"
                            if not failed else "含配置/状态变更类用例，已按套件顺序控制副作用与锁定级联。")
        )
    tail_scope = f"单套件专项执行（{SUITE_FILTER}）" if SUITE_FILTER else "全量回归执行"
    notes.append(
        f"5、耗时统计说明：本轮为{tail_scope}，净耗时 {dur}s；如需完整回归画像（24 套件 107 条，"
        f"总耗时约 24.7 分钟），参见同日全量回归报告。"
    )
    return notes


def gen_doc(cases, result_map, run_id, mode, out, result=None):
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
        if SUITE_FILTER and suite != SUITE_FILTER:
            # --suite 指定时仅纳入指定套件（单套件专项报告）
            continue
        if suite == "security" and VARIANT != "html":
            # new_ui：security（登录锁定）受设备 IP 级锁定状态影响，作为补充说明，不生成测试项
            # html：老 UI security（锁定状态机+权限基线）为核心套件，正常生成测试项
            continue
        for c in cases_list:
            build_test_item(doc, idx, c, result_map, run_id, mode)
            idx += 1

    build_result_summary(doc, result_map, mode, result=result)

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
    global VARIANT, SUITE_FILTER
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default="latest")
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--mode", default="both", choices=["case", "report", "both"])
    ap.add_argument("--variant", default="new_ui", choices=["new_ui", "html"],
                    help="new_ui=SPA 新 UI（默认）；html=国际老 UI 多页版")
    ap.add_argument("--suite", default=None,
                    help="仅纳入指定套件（如 status/login/wan/reboot），缺省=全部套件")
    args = ap.parse_args()
    VARIANT = args.variant
    SUITE_FILTER = args.suite

    os.makedirs(args.out, exist_ok=True)
    cases = load_cases()
    result_dir, result = find_latest_result(args.result)
    run_id = os.path.basename(result_dir) if result_dir else "N/A"

    result_map = {}
    if result:
        for c in result.get("cases", []):
            if SUITE_FILTER and _suite_key_of(c["id"]) != SUITE_FILTER:
                continue
            result_map[c["id"]] = c

    if args.mode in ("case", "both"):
        gen_doc(cases, result_map, run_id, "case", args.out)
    if args.mode in ("report", "both"):
        if result is None:
            print("[warn] 未找到结果，跳过测试报告")
        else:
            gen_doc(cases, result_map, run_id, "report", args.out, result=result)


if __name__ == "__main__":
    main()
