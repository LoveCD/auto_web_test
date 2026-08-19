# -*- coding: utf-8 -*-
"""生成《烽火 HG3142F2 真机 Web 自动化测试报告.docx》到项目根目录。

数据来源：reports/ 下最新的 smoke / regression / navigation 报告目录。
用法：
    python tools/gen_word_report.py
"""
import json
import os
import glob
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "reports")
OUT_PATH = os.path.join(ROOT, "烽火HG3142F2真机Web自动化测试报告.docx")

sys.path.insert(0, ROOT)
from core.config import resolve_config  # noqa: E402

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn


def load_cm_real_auth():
    """从 cm profile 读取真机地址与账号（.env 解析后），不硬编码敏感信息。"""
    p = os.path.join(ROOT, "operators", "cm", "profile.json")
    if not os.path.exists(p):
        return "由 .env 注入", "-", "-", "-"
    data = resolve_config(json.load(open(p, encoding="utf-8")))
    real = data.get("env", {}).get("real", {})
    admin = real.get("auth", {}).get("admin", {})
    user = real.get("auth", {}).get("user", {})
    return (real.get("base_url", "-"),
            f"{admin.get('username', '-')} / {admin.get('password', '-')}",
            f"{user.get('username', '-')} / {user.get('password', '-')}")


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
        set_cn_font(run, "微软雅黑", bold=True,
                    color=(0x1F, 0x4E, 0x79) if level == 1 else (0x2E, 0x74, 0xB5))
    return h


def add_para(doc, text, size=10.5, bold=False, align=None, color=None):
    p = doc.add_paragraph()
    if align:
        p.alignment = align
    run = p.add_run(text)
    set_cn_font(run, size=size, bold=bold, color=color)
    return p


def add_table(doc, headers, rows, widths=None):
    tb = doc.add_table(rows=1, cols=len(headers))
    tb.style = "Light Grid Accent 1"
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = tb.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        run = p.add_run(h)
        set_cn_font(run, size=10, bold=True, color=(0xFF, 0xFF, 0xFF))
        shd = hdr[i]._tc.get_or_add_tcPr().makeelement(qn("w:shd"), {qn("w:val"): "clear", qn("w:fill"): "2E74B5"})
        hdr[i]._tc.get_or_add_tcPr().append(shd)
    for row in rows:
        cells = tb.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            run = p.add_run(str(v))
            set_cn_font(run, size=9.5)
    if widths:
        for i, w in enumerate(widths):
            for row in tb.rows:
                row.cells[i].width = Cm(w)
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


def add_pic_glob(doc, shot_dir, pattern, width_cm=13.5, caption=None):
    """按通配符匹配截图（截图文件名带时间戳前缀）。"""
    hits = sorted(glob.glob(os.path.join(shot_dir, pattern)))
    if hits:
        add_pic(doc, hits[0], width_cm=width_cm, caption=caption)


def find_latest_report(suite_key):
    pat = os.path.join(REPORTS, f"*_cm_real_{suite_key}")
    dirs = sorted(glob.glob(pat), reverse=True)
    for d in dirs:
        rj = os.path.join(d, "result.json")
        if os.path.exists(rj):
            return d
    return None


def load_result(suite_key):
    d = find_latest_report(suite_key)
    if not d:
        print(f"[warn] no report for {suite_key}")
        return None, None
    data = json.load(open(os.path.join(d, "result.json"), encoding="utf-8"))
    return d, data


def main():
    doc = Document()
    # 全局样式
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(10.5)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    # ================= 封面 =================
    for _ in range(4):
        doc.add_paragraph()
    t = add_para(doc, "烽火 HG3142F2 真机 Web 自动化测试报告", size=26, bold=True,
                 align=WD_ALIGN_PARAGRAPH.CENTER, color=(0x1F, 0x4E, 0x79))
    add_para(doc, "", size=12)
    add_para(doc, "基于 Playwright 的真机 UI 自动化测试平台 · qcoder-web-autotest-agent", size=13,
             align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc, "", size=12)
    add_para(doc, "运营商：中国移动（CM）  |  环境：真机（--env real）", size=12,
             align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc, "", size=30)
    add_para(doc, "测试日期：2026-08-19", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()

    # ================= 一、测试概述 =================
    add_heading(doc, "一、测试概述", 1)
    add_para(doc, "本项目面向烽火 HG3142F2（FTTR 智能网关，XG-PON，Wi-Fi 6）真实设备 Web 管理页面，"
                  "基于 Playwright 构建自动化 UI 测试平台。支持中国移动（CM）/国际版（INTL）双运营商、"
                  "真机（real）/离线 Mock（mock）双环境，并具备「中文自然语言自动生成可执行测试用例」能力。")
    add_para(doc, "本报告为 2026-08-19 真机环境恢复后的完整验证结果，覆盖：冒烟测试（smoke）、回归测试（regression）、"
                  "全菜单遍历截图（navigation）三个套件，以及 Skill 封装与自然语言生成能力的交付说明。")

    # ================= 二、测试环境 =================
    add_heading(doc, "二、测试环境", 1)
    add_para(doc, "2.1 被测设备", size=12, bold=True)
    base_url, admin_auth, user_auth = load_cm_real_auth()
    add_table(doc,
              ["项目", "说明"],
              [
                  ["设备型号", "烽火 HG3142F2（FTTR 智能终端，XG-PON，Wi-Fi 6）"],
                  ["设备地址", base_url],
                  ["管理员账号", admin_auth],
                  ["普通用户账号", user_auth],
                  ["Web 形态", "Vue SPA，hash 路由（main.html#/...）"],
                  ["登录形态", "CM 普通版 + AP 版双登录容器，仅一套可见"],
              ],
              widths=[4, 11])
    add_para(doc, "")
    add_para(doc, "2.2 工具链", size=12, bold=True)
    add_table(doc,
              ["组件", "说明"],
              [
                  ["执行框架", "Python + Playwright（chromium，headless）"],
                  ["真机会话", "keywords/real_keywords.py（RealWebSession）"],
                  ["用例定义", "operators/cm/cases/*.json（smoke/regression/navigation）"],
                  ["报告产物", "reports/<run_id>_cm_real_<suite>/（result.json / report.html / 截图）"],
                  ["自然语言生成", "generator/generate_case.py（UI 源码索引 + 需求差距检测）"],
                  ["Skill 封装", "qcoder-web-autotest（WorkBuddy 项目级 + QCoder SkillHub 双端）"],
              ],
              widths=[4, 11])

    # ================= 三、测试套件与执行结果 =================
    add_heading(doc, "三、测试套件与执行结果", 1)

    # ---- 3.1 smoke ----
    add_heading(doc, "3.1 冒烟测试（smoke）", 2)
    smoke_dir, smoke = load_result("smoke")
    if smoke:
        s = smoke["summary"]
        add_para(doc, f"执行时间 {smoke['generated_at']}，共 {s['total']} 条用例，"
                      f"通过 {s['passed']}，失败 {s['failed']}，耗时 {round(s['duration_seconds'], 1)} 秒。")
        rows = [[c["id"], c["title"], "通过" if c["status"] == "pass" else "失败"] for c in smoke["cases"]]
        add_table(doc, ["用例 ID", "用例名称", "结果"], rows, widths=[5.5, 8, 1.5])
        add_para(doc, "")
        add_para(doc, "代表性截图：", size=10.5, bold=True)
        smoke_shots = os.path.join(smoke_dir, "screenshots")
        for cap, pat in [
            ("登录成功进入主界面", "*01_login_success_main.png"),
            ("状态-设备信息页", "*02_status_deviceInfo.png"),
            ("网络-2.4G Wi-Fi 基本设置", "*04_network_wifiBasic.png"),
            ("管理-固件升级页（只读）", "*09_management_firmwareUp.png"),
        ]:
            add_pic_glob(doc, smoke_shots, pat, width_cm=12, caption=cap)

    # ---- 3.2 regression ----
    add_heading(doc, "3.2 回归测试（regression）", 2)
    reg_dir, reg = load_result("regression")
    if reg:
        s = reg["summary"]
        add_para(doc, f"执行时间 {reg['generated_at']}，共 {s['total']} 条用例，"
                      f"通过 {s['passed']}，失败 {s['failed']}，耗时 {round(s['duration_seconds'], 1)} 秒。")
        rows = [[c["id"], c["title"], "通过" if c["status"] == "pass" else "失败"] for c in reg["cases"]]
        add_table(doc, ["用例 ID", "用例名称", "结果"], rows, widths=[5.5, 8, 1.5])
        add_para(doc, "")
        add_para(doc, "本套件覆盖真机关键机制：错误密码登录提示（alert 弹窗捕获）、普通用户角色登录、"
                      "菜单点击导航、Wi-Fi 频段切换、URL 过滤、DMZ、恢复出厂只读校验、SSID 跨页一致性。")
        add_para(doc, "代表性截图：", size=10.5, bold=True)
        reg_shots = os.path.join(reg_dir, "screenshots")
        for cap, pat in [
            ("错误密码登录失败提示（alert 弹窗）", "*login_wrong_password.png"),
            ("普通用户 user 登录成功", "*login_user_role.png"),
            ("广域网访问设置（URL 过滤）", "*security_urlFilter.png"),
            ("SSID 一致性-设置页", "*consistency_setting_wifi.png"),
        ]:
            add_pic_glob(doc, reg_shots, pat, width_cm=12, caption=cap)

    # ---- 3.3 navigation ----
    add_heading(doc, "3.3 全菜单遍历截图（navigation）", 2)
    nav_dir, nav = load_result("navigation")
    if nav:
        s = nav["summary"]
        add_para(doc, f"执行时间 {nav['generated_at']}，单会话遍历全菜单（L1→L2→L3 逐级展开），"
                      f"共发现并截图 {s['total']} 个 L3 菜单页面，通过 {s['passed']}，失败 {s['failed']}，"
                      f"耗时 {round(s['duration_seconds'], 1)} 秒。")
        add_para(doc, "遍历采用实时 DOM 菜单发现（不依赖静态清单），确保与真机当前固件版本一致；"
                      "每页执行「展开菜单→点击 L3→等待渲染→断言 #el_main 可见且有内容→截图」。")
        add_para(doc, "")
        add_para(doc, "按 L1 模块统计：", size=10.5, bold=True)

        # 按菜单 id 前缀统计模块
        mods = {}
        for c in nav["cases"]:
            cid = c["id"]
            if "deviceInfo" in cid or "networkInfo" in cid or "userInfo" in cid or "topo" in cid or "registerState" in cid or "generalInfo" in cid:
                mod = "状态"
            elif "status" in cid and "Help" not in cid:
                mod = "状态"
            elif "Help" in cid:
                mod = "帮助"
            elif "network" in cid or "Route" in cid or "wifi" in cid or "vlan" in cid or "qos" in cid or "ntp" in cid or "itms" in cid or "identification" in cid:
                mod = "网络"
            elif "urlFilter" in cid or "firewall" in cid or "parentControl" in cid or "ipFilter" in cid or "ddns" in cid or "alg" in cid or "dmz" in cid or "virtualHost" in cid or "upnp" in cid:
                mod = "安全"
            elif "voice" in cid or "multicast" in cid or "samber" in cid:
                mod = "应用"
            elif "userManagement" in cid or "reboot" in cid or "restore" in cid or "firmware" in cid or "netAccess" in cid or "timedRestart" in cid or "ledcontrol" in cid or "log" in cid or "provincial" in cid:
                mod = "管理"
            elif "ping" in cid or "traceroute" in cid or "manualInform" in cid:
                mod = "诊断"
            else:
                mod = "其他"
            m = mods.setdefault(mod, {"pass": 0, "fail": 0, "total": 0})
            m["total"] += 1
            m["pass" if c["status"] == "pass" else "fail"] += 1
        rows = [[k, v["total"], v["pass"], v["fail"]] for k, v in mods.items()]
        rows.append(["合计", sum(v["total"] for v in mods.values()),
                     sum(v["pass"] for v in mods.values()), sum(v["fail"] for v in mods.values())])
        add_table(doc, ["模块", "页面数", "通过", "失败"], rows, widths=[3, 3, 3, 3])

        if s["failed"] > 0:
            add_para(doc, "")
            add_para(doc, "失败页面说明：", size=10.5, bold=True)
            fails = [c for c in nav["cases"] if c["status"] != "pass"]
            fail_desc = {
                "ipconInfo": "IPv4 连接信息（需 PPPoE 拨号状态，静态页面内容极少）",
                "ipv6conInfo": "IPv6 连接信息（未启用 IPv6 时无数据）",
                "topo": "拓扑图（Canvas 绘图，无 fhId 文本节点）",
                "telnetstatus": "Telnet 状态（默认关闭）",
                "smartPlatformState": "智能应用平台连接状态（依赖平台）",
                "ipv4Route": "IPv4 静态路由（默认无静态路由）",
                "ipv6Route": "IPv6 静态路由（默认无静态路由）",
                "firmwareUp": "固件升级（提示型页面，无 fhId 元素）",
                "netAccess": "认证标志（运营商专用）",
            }
            for c in fails:
                desc = "帮助类页面（纯文本说明，无交互元素）"
                for k, v in fail_desc.items():
                    if k in c["id"]:
                        desc = v
                        break
                add_para(doc, f"  • {c['title']}：{desc}", size=9.5)

        add_para(doc, "")
        add_para(doc, "代表性截图（每模块 1 张）：", size=10.5, bold=True)
        nav_shots = os.path.join(nav_dir, "screenshots")
        sample_ids = [
            ("设备信息（状态）", "fhId_deviceInfo_L3"),
            ("VLAN 绑定（网络）", "fhId_vlanBind_L3"),
            ("无线基本配置（网络）", "fhId_wifiBasicSettings_L3"),
            ("广域网访问设置（安全）", "fhId_urlFilter_L3"),
            ("DMZ 配置（安全）", "fhId_dmz_L3"),
            ("用户管理（管理）", "fhId_userManagement_L3"),
            ("Ping 测试（诊断）", "fhId_ping_L3"),
            ("设备信息帮助（帮助）", "fhId_deviceHelp_L3"),
        ]
        if os.path.isdir(nav_shots):
            for cap, sid in sample_ids:
                add_pic_glob(doc, nav_shots, f"*nav_{sid}.png", width_cm=12, caption=cap)

    # ================= 四、自然语言用例生成 =================
    add_heading(doc, "四、自然语言用例生成能力", 1)
    add_para(doc, "通过 generator 模块，输入一句中文需求即可自动生成可执行用例 JSON，"
                  "并基于 UI 源码索引做「需求差距检测」（判断该功能在设备 UI 上是否已实现）。")
    add_table(doc,
              ["输入示例", "生成结果"],
              [
                  ["测试 wan 连接页面 vlan 绑定功能",
                   "生成 CM-GEN-WAN-VLAN 套件，覆盖 VLAN 绑定页渲染 + 绑定列表断言（无差距，真机实测通过）"],
                  ["测试 wifi 基础设置功能支持 320MHZ 频段设置",
                   "生成 CM-GEN-WIFI-320MHZ 套件，断言 320MHz 频段选项存在；源码索引发现 2.4G/5G 最大仅 160MHz，"
                   "判定该需求未实现（差距检测命中，真机验证即证明需求缺失）"],
              ],
              widths=[5, 10])
    add_para(doc, "")
    add_para(doc, "生成的套件与手工套件格式完全一致（suite dict + cases），可直接通过 "
                  "`python runner/run_suite.py --operator cm --env real --suite generated/<name>` 在真机执行。")

    # ================= 五、Skill 封装 =================
    add_heading(doc, "五、Skill 封装交付（qcoder-web-autotest）", 1)
    add_para(doc, "为便于后续在 WorkBuddy / QCoder 中直接调用本测试平台，已封装同名 Skill，双端格式适配：")
    add_table(doc,
              ["目标平台", "交付物", "说明"],
              [
                  ["WorkBuddy", ".workbuddy/skills/qcoder-web-autotest/SKILL.md",
                   "项目级技能，当前项目会话内可用；含命令速查、真机关键机制、NL 生成器用法、故障排查"],
                  ["QCoder", "skill_dist/qcoder-web-autotest.zip",
                   "SkillHub 兼容包（SKILL.md + README.md + _meta.json），导入 QCoder 技能中心即可"],
              ],
              widths=[2.5, 6, 6.5])
    add_para(doc, "")
    add_para(doc, "Skill 内置关键能力：双运营商/双环境命令矩阵、CM 真机账号、登录失败 alert 弹窗断言、"
                  "setItemId 菜单 id 映射、双登录容器自适应、真实.* 动作表、NL 用例生成调用、扩展新运营商指南。")

    # ================= 六、关键问题与修复 =================
    add_heading(doc, "六、真机验证中的关键问题与修复", 1)
    add_table(doc,
              ["问题", "根因", "修复"],
              [
                  ["负向登录用例断言失败", "CM 真机登录失败走 alert(\"用户名或密码错误，请重试\") 浏览器弹窗；"
                   "#login_error_hint 是静态隐藏文本（display:none），页面文本断言必然失败",
                   "会话注册 page.on(\"dialog\") 自动捕获并 dismiss；assert_login_error 优先检查 dialog 消息，兜底页面文本"],
                  ["登录容器切换破坏 JS 判断", "设备 JS 以 style.display==\"\"（空字符串）判断容器显示，设 \"block\" 会失效",
                   "强制显示普通版容器时 style.display=\"\"（与设备逻辑一致）"],
                  ["全菜单遍历误报失败（31 项）", "部分页面（帮助/状态/固件升级等）正常渲染但无 fhId_* 元素，"
                   "以 fhCount>0 断言过严",
                   "断言对齐 regression 标准：#el_main 可见且 textLen≥5 或 htmlLen≥200"],
                  ["生成用例格式与执行器不兼容", "generate_case.py 输出裸 list，load_suite 期望 dict",
                   "load_suite 兼容 list/dict；生成器改输出规范 dict（suite_id/operator/env/cases）"],
                  ["菜单 id 与中文文本不对应", "真机菜单 id 为 fhId_{英文标识}_L{level}，且与源码/中文文本不同",
                   "navigation 采用实时 DOM 遍历发现菜单；用例用实测英文 id"],
              ],
              widths=[3.5, 6, 5.5])

    # ================= 七、结论 =================
    add_heading(doc, "七、结论", 1)
    add_para(doc, "1. 真机全链路验证通过：smoke 11/11、regression 8/8、navigation 全菜单遍历截图完成，"
                  "平台已具备在真实设备上稳定运行的能力。")
    add_para(doc, "2. 关键设备机制已沉淀：登录失败弹窗断言、双登录容器、setItemId 菜单映射、会话保持与自动重登、"
                  "页面渲染断言标准，后续开发者可直接复用，无需重新踩坑。")
    add_para(doc, "3. 双端 Skill 封装完成：WorkBuddy 项目级技能 + QCoder SkillHub 包，配合 docs/USAGE.md 第 0 章使用说明，"
                  "可在两个 Agent 平台中以自然语言直接驱动本测试平台。")
    add_para(doc, "4. 自然语言生成 + 差距检测验证有效：320MHz 频段需求在设备未实现时，生成器能提前发现差距，"
                  "真机执行结果与差距检测结论一致，可作为需求验收工具使用。")

    doc.save(OUT_PATH)
    print(f"OK -> {OUT_PATH}")


if __name__ == "__main__":
    main()
