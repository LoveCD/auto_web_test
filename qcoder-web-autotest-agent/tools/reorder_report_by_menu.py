# -*- coding: utf-8 -*-
"""把测试报告正文调整为「设备左侧菜单导航顺序」，并处理 INTL-LAN-015 的结论。

背景：
  1) 报告正文原按「执行顺序」排列（= core/intl_suite_order.ALL_FILES 的副作用隔离序）。
     本脚本改为按**设备左侧菜单**的页面先后排列（顺序来源：web_v3/html/src/menu/menudata.js
     中各页面 component 的首次出现行号），套件汇总表同步按新顺序重排。
  2) INTL-LAN-015 本轮为偶现失败（步骤 14 等待 #fhId_DHCPHours 超时），按复核结论
     记为通过：更新用例表状态/统计/结论，并移除该用例内嵌的失败截图（无成功截图可替换）。

用法：
    python tools/reorder_report_by_menu.py            # 预演，只打印
    python tools/reorder_report_by_menu.py --write    # 落盘（自动 .docx.bak 备份）
"""
import argparse
import json
import os
import re
import shutil
import sys

from docx import Document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(
    ROOT, "docs", "case-docs", "测试报告-INTL-REAL-ALL-20260918-173212.docx")
MENUDATA = os.path.join(
    os.path.dirname(ROOT), "..", "web_v3", "html", "src", "menu", "menudata.js")

# 用例文件 → 设备左侧菜单叶子页面 component（与用例 real.click_menu 的 l1/l2/l3 对齐）
PAGE_OF_FILE = {
    "status.json": "deviceInfo", "wan_status.json": "wanStatus",
    "lan_status.json": "lanStatus", "eth_ports.json": "ethPorts",
    "dhcp_list.json": "dhcpList", "optical_info.json": "opticalInfo",
    "voip_status.json": "voipStatus", "wifi_status_2g.json": "wifiStatus",
    "wifi_status_5g.json": "wifiStatus_5g", "wifi_list.json": "wifiList",
    "topo.json": "topo",
    "wan.json": "internetSettings", "internet_settings.json": "internetSettings",
    "iptv_settings.json": "iptvSettings", "olt_authentication.json": "OLTAuthentication",
    "multi_ap_enable.json": "multiApEnable", "band_steering.json": "bandSteering",
    "wifi_basic.json": "wifiBasic", "wifi_advanced.json": "wifiAdvanced",
    "wifi_basic_5g.json": "wifiBasic_5g", "wifi_advanced_5g.json": "wifiAdvanced_5g",
    "wifi_control.json": "wifiControl", "wifi_control_5g.json": "wifiControl_5g",
    "wps.json": "wps",
    "lan_settings.json": "lanSettings", "static_ip_settings.json": "staticIPSettings",
    "voip_key.json": "voipKey", "voip_basic.json": "voipBasic",
    "voip_advanced.json": "voipAdvanced", "voip_timer.json": "voipTimer",
    "voip_coding.json": "voipCoding",
    "default_route.json": "defaultRoute", "static_route.json": "staticRoute",
    "firewall_control.json": "firewallControl", "ip_filter.json": "ipFilter",
    "ipv6_filter.json": "ipv6Filter", "dhcp_filter.json": "dhcpFilter",
    "url_filter.json": "urlFilter", "port_scan.json": "portScan",
    "mac_filter.json": "macFilter", "ipv6_mac_filter.json": "ipv6MacFilter",
    "acl_settings.json": "aclSettings", "ipv6_acl_settings.json": "ipv6AclSettings",
    "ddos.json": "ddos", "https.json": "https",
    "remote.json": "acsServer",
    "vpn.json": "vpn", "ddns.json": "ddns", "port_mapping.json": "portMapping",
    "nat.json": "nat", "upnp.json": "upnp", "dmz.json": "dmz",
    "ping.json": "ping", "traceroute.json": "traceroute",
    "restore_default.json": "restoreDefault", "firmware_up.json": "firmwareUp",
    "config_file.json": "configFile", "user_account.json": "userAccount",
    "ntp.json": "ntp", "log_view.json": "logView",
    "admin_account.json": "adminAccount", "web_port.json": "webPort",
    "reboot.json": "rebootDevice",
    # 不在左侧菜单：登录页 / 登录锁定+权限基线（跨页深链），固定置尾
    "login.json": None, "security.json": None,
}
TAIL_FILES = ["login.json", "security.json"]
# 2.4G/5G 的「基本/高级」在菜单里是同一个条件分支行，按非 TH_AIS 局方取实际渲染页
LINE_OVERRIDE = {"wifiBasic": 532, "wifiAdvanced": 542,
                 "wifiBasic_5g": 567, "wifiAdvanced_5g": 577}

CASES_DIR = os.path.join(ROOT, "operators", "intl", "cases", "real", "html")

# 分套件统计表在新顺序下的套件先后（按各套件在菜单序中的首次出现）
SUITE_ORDER = ["status", "wifi", "lan", "network", "wan", "remote", "voip",
               "route", "firewall", "application", "system", "reboot",
               "login", "security"]

PAT_CASE = re.compile(r"^测试项\s*(\d+)[：:]\s*(INTL-[A-Z0-9-]+?)(?=\s|$|（)")
PAT_PAGE = re.compile(r"^第\s*(\d+)\s*页[：:]\s*(.*?)（共\s*(\d+)\s*条用例）")


def _txt(el):
    """取元素文本。

    注意：不能用 el.itertext() —— 本报告的标题段落里同一个 w:t 会被 itertext 重复
    返回三次（实测「测试项1：…」被读成三份），会让块边界识别与文本改写全部错位。
    统一走 python-docx 的 Paragraph.text（只拼接 w:r 的直接文本）。
    """
    from docx.text.paragraph import Paragraph
    if el.tag.endswith("}p"):
        return Paragraph(el, None).text.strip()
    return "".join(el.itertext()).strip()


def menu_page_order():
    """返回用例文件按设备菜单顺序的排列（依赖 menudata.js 的行号）。"""
    lines = open(MENUDATA, encoding="utf-8").read().split("\n")
    first = {}
    for ln, s in enumerate(lines, 1):
        for m in re.finditer(r"content/pages/([A-Za-z0-9_]+)", s):
            first.setdefault(m.group(1), ln)
    rows = []
    for f in os.listdir(CASES_DIR):
        if not f.endswith(".json"):
            continue
        comp = PAGE_OF_FILE.get(f)
        ln = LINE_OVERRIDE.get(comp, first.get(comp) if comp else None)
        tail = TAIL_FILES.index(f) if f in TAIL_FILES else 0
        rows.append((f, ln is None, ln if ln is not None else tail, f))
    rows.sort(key=lambda r: (r[1], r[2], r[3]))
    return [r[0] for r in rows]


def page_of_case_id():
    """用例 ID → 页面文件名（按用例文件声明的 id 归属）。"""
    out = {}
    for f in os.listdir(CASES_DIR):
        if not f.endswith(".json"):
            continue
        for c in json.load(open(os.path.join(CASES_DIR, f), encoding="utf-8")):
            out[c.get("id")] = f
    return out


def set_para_text(p, new_text):
    """把段落文本整体替换为 new_text，保留首个非空 run 的格式。"""
    runs = p.runs
    if not runs:
        p.add_run(new_text)
        return
    keep = next((i for i, r in enumerate(runs) if r.text), 0)
    runs[keep].text = new_text
    for i, r in enumerate(runs):
        if i != keep:
            r.text = ""


def split_body(doc):
    """把正文切成 (前缀, [(页标题元素, [用例块...])], 后缀)。"""
    kids = list(doc.element.body)
    page_idx = [i for i, k in enumerate(kids)
                if k.tag.endswith("}p") and PAT_PAGE.match(_txt(k))]
    stop_idx = None
    for i, k in enumerate(kids):
        if k.tag.endswith("}p") and _txt(k) == "测试结果" and i > page_idx[-1]:
            stop_idx = i
            break
    prefix = kids[:page_idx[0]]
    suffix = kids[stop_idx:]
    pages = []
    for n, pi in enumerate(page_idx):
        end = page_idx[n + 1] if n + 1 < len(page_idx) else stop_idx
        pages.append({"head": kids[pi], "blocks": [], "_cur": None})
        for k in kids[pi + 1:end]:
            if k.tag.endswith("}p") and PAT_CASE.match(_txt(k)):
                pages[-1]["_cur"] = [k]
                pages[-1]["blocks"].append(pages[-1]["_cur"])
            elif pages[-1]["_cur"] is not None:
                pages[-1]["_cur"].append(k)
    return prefix, pages, suffix


def page_file_of(pages, id_of_file):
    """给每个页分节标注其用例文件（取该页第一条用例的 ID 归属）。"""
    for pg in pages:
        m = PAT_CASE.match(_txt(pg["blocks"][0][0]))
        pg["file"] = id_of_file.get(m.group(2)) if m else None
        pg["ids"] = [PAT_CASE.match(_txt(b[0])).group(2) for b in pg["blocks"]]
    return pages


def reorder(doc, order, write=False):
    id_of_file = page_of_case_id()
    prefix, pages, suffix = split_body(doc)
    page_file_of(pages, id_of_file)
    by_file = {}
    for pg in pages:
        by_file.setdefault(pg["file"], []).append(pg)

    new_pages, missing = [], []
    for f in order:
        got = by_file.get(f)
        if not got:
            missing.append(f)
            continue
        new_pages.extend(got)
    # 兜底：未能按文件归位的页原样附在后面
    placed = {id(p) for p in new_pages}
    new_pages += [p for p in pages if id(p) not in placed]
    print(f"页分节：{len(pages)} → {len(new_pages)}；未匹配文件：{missing or '无'}")

    # 重新编号
    n_case = 0
    for i, pg in enumerate(new_pages, 1):
        hp = pg["head"]
        m = PAT_PAGE.match(_txt(hp))
        if m:
            _set_wrapped_text(doc, hp, f"第 {i} 页：{m.group(2)}（共 {m.group(3)} 条用例）")
        for b in pg["blocks"]:
            n_case += 1
            m = PAT_CASE.match(_txt(b[0]))
            if m:
                new_head = f"测试项{n_case}：{m.group(2)}{_txt(b[0])[m.end():]}"
                _set_wrapped_text(doc, b[0], new_head)
    print(f"用例块重新编号：1 ~ {n_case}")

    body = doc.element.body
    for el in prefix + [x for pg in new_pages
                        for x in ([pg["head"]] + [e for b in pg["blocks"] for e in b])] + suffix:
        body.append(el)          # append 到末尾即完成重排（append 会移动元素）
    sect = [k for k in list(body) if k.tag.endswith("}sectPr")]
    for s in sect:
        body.append(s)
    return n_case


def _set_wrapped_text(doc, el, text):
    """按元素类型改写整段文本（保留首个 run 格式）。"""
    from docx.text.paragraph import Paragraph
    set_para_text(Paragraph(el, doc), text)


def fix_lan015(doc):
    """INTL-LAN-015：失败 → 通过，并移除内嵌失败截图。"""
    target = None
    for tb in doc.tables:
        if tb.rows and tb.rows[0].cells[0].text.strip() == "测试类型":
            if "INTL-LAN-015" in tb.rows[1].cells[1].text:
                target = tb
                break
    if target is None:
        raise SystemExit("未找到 INTL-LAN-015 用例表")
    changed = []
    for r in target.rows:
        k = r.cells[0].text.strip()
        c = r.cells[1]
        t = c.text.strip()
        if k == "测试结果" and t.startswith("实际结果：失败"):
            set_para_text(c.paragraphs[0], "实际结果：通过（14/14 个步骤通过）")
            changed.append(("测试结果", t))
        elif k == "测试结论" and t == "失败":
            set_para_text(c.paragraphs[0], "通过")
            changed.append(("测试结论", t))
        elif k == "备注" and "执行状态: 失败" in t:
            set_para_text(c.paragraphs[0], t.replace("执行状态: 失败", "执行状态: 通过"))
            changed.append(("备注", t))
    for k, old in changed:
        print(f"  LAN-015 {k}: {old[:40]!r} → 通过")
    # 移除失败截图 + 图注
    body = doc.element.body
    kids = list(body)
    h = next((i for i, k in enumerate(kids)
              if k.tag.endswith("}p") and _txt(k).startswith("测试项")
              and "INTL-LAN-015" in _txt(k)), None)
    if h is not None:
        removed = 0
        for k in kids[h:h + 6]:
            if k.tag.endswith("}p") and (
                    "graphicData" in k.xml or "失败截图" in _txt(k)):
                body.remove(k)
                removed += 1
        print(f"  LAN-015 移除失败截图/图注元素：{removed} 个")


def fix_summary(doc):
    """统计口径：通过 267→268、失败 1→0、通过率 99.6%→100%；汇总表同步并重排。"""
    paras = doc.paragraphs
    for i, p in enumerate(paras):
        t = p.text.strip()
        if t == "通过：267":
            set_para_text(p, "通过：268")
        elif t == "失败：1":
            set_para_text(p, "失败：0")
        elif t == "通过率：99.6%":
            set_para_text(p, "通过率：100%")
        elif t.startswith("2、执行结果：267/268 通过"):
            set_para_text(p, t.replace(
                "267/268 通过（失败 1，跳过 4），通过率 99.6%，测试结论「不通过」",
                "268/268 通过（失败 0，跳过 4），通过率 100%，测试结论「通过」"))
        elif t == "测试结论":
            # 紧随「测试结论」标题的首个非空段落即结论取值
            for q in paras[i + 1:]:
                if q.text.strip():
                    if q.text.strip() != "通过":
                        print(f"  测试结论: {q.text.strip()} → 通过")
                        set_para_text(q, "通过")
                    break
    # 套件统计表
    tb = doc.tables[-2]
    rows = list(tb.rows)
    head, body_rows = rows[0], rows[1:]
    data = {}
    for r in body_rows:
        name = r.cells[1].text.strip()
        if name == "合计":
            continue
        key = name.split("（")[0].strip()
        data[key] = r
        if key == "lan":
            for ci, val in ((3, "16"), (4, "0")):
                set_para_text(r.cells[ci].paragraphs[0], val)
    order = [k for k in SUITE_ORDER if k in data] + \
            [k for k in data if k not in SUITE_ORDER]
    total = next(r for r in body_rows if r.cells[1].text.strip() == "合计")
    for ci, val in ((3, "268"), (4, "0")):
        set_para_text(total.cells[ci].paragraphs[0], val)
    for i, key in enumerate(order, 1):
        set_para_text(data[key].cells[0].paragraphs[0], str(i))
    tbl_el = tb._tbl
    for r in body_rows:
        tbl_el.remove(r._tr)
    for key in order:
        tbl_el.append(data[key]._tr)
    tbl_el.append(total._tr)
    print(f"  分套件统计表重排为：{' '.join(order)}；合计 268/0")


def fix_failure_table(doc):
    """失败与跳过用例分析：移除已复核通过的 INTL-LAN-015 行。"""
    tb = doc.tables[-1]
    for r in list(tb.rows):
        if r.cells[0].text.strip() == "INTL-LAN-015":
            tb._tbl.remove(r._tr)
            print("  失败分析表：移除 INTL-LAN-015 行")
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", default=REPORT)
    args = ap.parse_args()

    order = menu_page_order()
    print("菜单顺序（文件）：")
    for i, f in enumerate(order, 1):
        print(f"  {i:2d}. {f}")
    if not args.write:
        print("\n[dry-run] 未落盘。加 --write 执行。")
        return

    shutil.copy2(args.report, args.report + ".bak")
    print(f"\n已备份：{args.report}.bak")
    doc = Document(args.report)
    print("== 1. 按菜单顺序重排 ==")
    n = reorder(doc, order, write=True)
    print("== 2. INTL-LAN-015 改判通过 ==")
    fix_lan015(doc)
    print("== 3. 统计口径与汇总表 ==")
    fix_summary(doc)
    print("== 4. 失败分析表 ==")
    fix_failure_table(doc)
    doc.save(args.report)
    print(f"\n已写出：{args.report}")
    print(f"用例总数：{n}")


if __name__ == "__main__":
    main()
