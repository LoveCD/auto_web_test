# -*- coding: utf-8 -*-
"""生成《开发使用说明与工作流简介》简易 Word 文档（v1.3 对齐 2026-09-04 优化）

v1.3 变更（2026-09-04）：
- INTL 执行器拆分：run_intl_real.py = 新 UI（SPA）专用；新增 run_intl_real_html.py = 老 UI（HTML 多页版）专用，执行器不再有 --variant
- 老 UI 用例资产合并：html 17 模块 67 文件 201 条（原 6 套件 39 条，0828 线成果）
- gen_intl_word.py 的 --variant 保留为报告数据源选择（reports/intl_real vs reports/intl_real_html）

v1.2 变更（2026-09-03）：
- 3.6 INTL 真机执行链路：新增 --scheme 双协议（自然语言选择 HTTP/HTTPS/auto 探测）
- 第 4 章 4.1：gen_intl_word.py 分析结论改为按本轮 result.json 动态生成；强调 --suite 首次必带
- 新增 3.7 单套件回归一键 SOP（触发语「按SOP直接跑」直跑三步链）
- 2.1 主链路、2.3 矩阵、附录同步（HG6142HT 实测、HTTPS 301、venv Scripts 路径）
"""
import os
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_PRIMARY = os.path.join(BASE, "docs", "开发使用说明与工作流简介.docx")
OUT_FALLBACK = os.path.join(BASE, "docs", "开发使用说明与工作流简介_v1.3_20260904.docx")

ACCENT = RGBColor(0x1F, 0x4E, 0x79)   # 深蓝
GRAY   = RGBColor(0x59, 0x59, 0x59)
CODE_BG = "F2F2F2"


def set_run_font(run, name_zh="微软雅黑", name_en="Calibri", size=10.5, bold=False, color=None):
    run.font.name = name_en
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name_zh)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def add_para(doc, text, size=10.5, bold=False, color=None, align=None, space_after=6, style=None):
    p = doc.add_paragraph(style=style)
    r = p.add_run(text)
    set_run_font(r, size=size, bold=bold, color=color)
    p.paragraph_format.space_after = Pt(space_after)
    if align is not None:
        p.alignment = align
    return p


def add_heading(doc, text, level=1):
    p = doc.add_paragraph()
    r = p.add_run(text)
    if level == 0:
        set_run_font(r, size=20, bold=True, color=ACCENT)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(6)
    elif level == 1:
        set_run_font(r, size=15, bold=True, color=ACCENT)
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1");   bottom.set(qn("w:color"), "1F4E79")
        pBdr.append(bottom); pPr.append(pBdr)
    elif level == 2:
        set_run_font(r, size=12.5, bold=True, color=RGBColor(0x2E, 0x74, 0xB5))
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
    else:
        set_run_font(r, size=11, bold=True)
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(3)
    return p


def add_code(doc, lines):
    for line in lines.split("\n"):
        p = doc.add_paragraph()
        r = p.add_run(line)
        set_run_font(r, name_zh="微软雅黑", name_en="Consolas", size=9)
        pPr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), CODE_BG)
        pPr.append(shd)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.left_indent = Cm(0.3)


def add_table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        r = hdr[i].paragraphs[0].add_run(h)
        set_run_font(r, size=9.5, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "1F4E79")
        hdr[i]._tc.get_or_add_tcPr().append(shd)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            set_run_font(r, size=9.5)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Cm(w)
    return t


doc = Document()
for sec in doc.sections:
    sec.top_margin = Cm(2.2); sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.4); sec.right_margin = Cm(2.4)

# ============ 封面 ============
add_heading(doc, "QCoder Web AutoTest Agent", 0)
add_heading(doc, "开发使用说明与工作流简介", 0)
add_para(doc, "面向烽火网关真实 Web UI 的端到端自动化测试智能体（qcoder-web-autotest-agent）", size=11, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
add_para(doc, "版本：v1.2（对齐 2026-09-03 优化：双协议访问 / 动态分析结论 / 单套件 SOP）  |  日期：2026-09-03", size=9, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)

# ============ 一、项目定位 ============
add_heading(doc, "一、项目定位", 1)
add_para(doc, "一句话定位：把「测试设计、用例维护、自动执行、失败分析和报告输出」固化成可重复流程的 Web 测试智能体——"
              "输入一句中文需求，自动生成可执行用例，在真机或离线 Mock 双环境执行，产出结构化报告（含截图）并一键生成品牌化 Word 报告。")
add_para(doc, "提效目标：人工执行约 3 人日 → 智能体执行 ≤ 2 小时；Smoke ≤ 20 分钟；失败分析与报告整理自动完成。")
add_para(doc, "当前规模与实测：INTL 新 UI 24 套件 109 条 + 老 UI 17 模块 67 文件 201 条 + CM 多套件；"
              "HG6142HT 新 UI 真机全量回归 107 条 / 通过率 95.3%（约 25 分钟）；status / login 单套件专项 100% 通过（约 1 分钟/套件）。")

# ============ 二、整个工作流简介 ============
add_heading(doc, "二、整个工作流简介", 1)

add_heading(doc, "2.1 主执行链路", 2)
add_code(doc, """需求 / 修改点 / 一句中文自然语言
   |
   v
(1) 扫描真实 UI 源码 + 索引（setItemId -> fhId_* 元素、菜单路由、下拉选项）
   v
(2) 自动生成可执行 JSON 用例（含需求差距 gap 检测）
   v
(3) 设备 Profile + Selector 解析（运营商目录隔离，敏感信息经 .env 注入）
   v
(4) 执行：CM runner/run_suite.py  /  INTL runner/run_intl_real.py（新 UI SPA）+ runner/run_intl_real_html.py（老 UI 多页），
      --scheme 双协议自动探测 HTTPS 优先）   真机 Playwright + 截图 / 离线 Mock
   v
(5) 自动报告：result.json（含逐用例耗时）+ 截图（reports/<run_id>/）
   v
(6) Word 报告：tools/gen_intl_word.py（分析结论按本轮 result.json 动态生成）
      / gen_word_report.py（CM）/ e2e_bootstrap gen-case-doc.js（统一 DOCX 模板）
   v
(7) AI 失败分析（selector_changed / product_bug / env_issue / script_bug）
   v
(8) AI 覆盖分析（页面覆盖矩阵 / 缺口补充建议）""")

add_heading(doc, "2.2 四大闭环", 2)
add_table(doc,
    ["闭环", "流程"],
    [
        ["新功能", "需求 → AI 生成用例 → AI 生成脚本 → 人工审核入库"],
        ["修改点", "变更说明 → AI 影响分析 → 更新用例/selector → 推荐回归集"],
        ["版本回归", "版本选择 → 自动执行 → AI 失败归因 → 准入报告（Word 一键生成）"],
        ["覆盖治理", "需求清单 → 用例库扫描 → 覆盖矩阵 → 缺口补充建议"],
    ],
    widths=[3.0, 12.5])

add_heading(doc, "2.3 双运营商 × 双环境 × 双 UI 变体矩阵", 2)
add_table(doc,
    ["维度", "取值", "说明"],
    [
        ["运营商", "--operator cm / intl", "中国移动（HG3142F2）/ 国际（HG6163FC1、HG6142HT）"],
        ["环境", "--env real / mock", "真机 Playwright + 截图 / 离线 Mock（可接 CI）"],
        ["INTL 新 UI 入口", "runner/run_intl_real.py", "SPA 新 UI：24 套件 109 条；每用例独立 context、逐用例耗时"],
        ["INTL 老 UI 入口", "runner/run_intl_real_html.py", "老 UI 多页版：17 模块 67 文件 201 条（0828 线合并）"],
        ["INTL 访问协议", "--scheme https / http / auto", "自然语言可选；auto=HTTPS 优先探测，自签证书自动忽略"],
        ["CM 执行入口", "runner/run_suite.py", "smoke / regression / navigation（全菜单遍历截图）"],
        ["Mock 服务", "mock_web_ui/server.py", "127.0.0.1，POST /api/reset 一键重置，可由执行器自动拉起"],
    ],
    widths=[3.2, 4.8, 7.5])

add_heading(doc, "2.4 目录结构速览", 2)
add_code(doc, """qcoder-web-autotest-agent/
├── core/config.py            # 统一配置：.env 加载 + ${VAR} 占位符解析
├── operators/
│   ├── cm/cases/             # 中国移动：profile/selectors/cases
│   └── intl/cases/real/
│       ├── new_ui/           # INTL 新 UI：24 套件 109 条（SPA）
│       └── html/             # INTL 老 UI：17 模块 67 文件 201 条（多页版）
├── keywords/                 # 真机关键字层 real_keywords.py + 断言引擎
├── runner/
│   ├── run_suite.py          # CM/通用执行器 + 报告器
│   ├── run_intl_real.py      # INTL 新 UI 真机执行器（--scheme 双协议）
│   └── run_intl_real_html.py # INTL 老 UI 真机执行器（HTML 多页版）
├── generator/                # NL 用例生成器（page_index + generate_case + index_cache）
├── mock_web_ui/              # 离线 Mock 网关（纯标准库，/api/reset 重置）
├── e2e_bootstrap/            # Node 端 Playwright E2E 基线（骨架生成 + DOCX 报告）
│   └── scripts/gen-case-doc.js   # 统一用例文档/执行报告 DOCX 生成器
├── agent/workflows/          # QCoder AI 工作流模板（5 个）
├── tools/
│   ├── gen_intl_word.py      # INTL Word 报告（--variant 选报告数据源+单套件过滤+FH品牌化）
│   ├── gen_word_report.py    # CM Word 报告生成
│   ├── gen_usage_doc.py      # 本文档生成脚本
│   └── docx_branding.py      # 封面 logo + 页眉品牌化
├── skill_dist/               # QCoder SkillHub 技能包（*.zip）
├── reports/                  # 执行报告（自动生成，gitignore）
└── docs/                     # USAGE / DEPLOYMENT / 本文档 / case-docs 交付物""")

# ============ 三、开发使用说明 ============
add_heading(doc, "三、开发使用说明", 1)

add_heading(doc, "3.1 环境准备", 2)
add_para(doc, "依赖：Python ≥ 3.8（Playwright ≥ 1.44 + Chromium、python-docx）；Node.js ≥ 16（仅 e2e_bootstrap 链路需要）。")
add_code(doc, """cd qcoder-web-autotest-agent
pip install -r requirements.txt
playwright install chromium

# 敏感配置注入（.env 已 gitignore，不会上传）
cp .env.example .env
# INTL 设备：QCT_INTL_BASE_URL / QCT_INTL_ADMIN_USER / QCT_INTL_ADMIN_PASS
#            QCT_INTL_USER_USER / QCT_INTL_USER_PASS
# CM 设备：  QCT_CM_BASE_URL / QCT_CM_ADMIN_USER / QCT_CM_ADMIN_PASS ...

# Windows venv 注意：若 venv 根目录无 python.exe，解释器在 venv\\Scripts\\python.exe""")

add_heading(doc, "3.2 快速开始（常用命令）", 2)
add_table(doc,
    ["用途", "命令"],
    [
        ["NL 生成用例（无需设备）", "python -m generator.generate_case --operator cm --query \"测试wan连接页面vlan绑定功能\""],
        ["INTL 新 UI 真机全量回归", "python runner/run_intl_real.py --suite all --scheme auto"],
        ["INTL 新 UI 单套件专项", "python runner/run_intl_real.py --suite status --scheme auto"],
        ["INTL 新 UI 指定明文 HTTP", "python runner/run_intl_real.py --suite status --scheme \"http明文\""],
        ["INTL 老 UI 真机全量回归", "python runner/run_intl_real_html.py --suite all --scheme auto"],
        ["INTL 老 UI 单套件专项", "python runner/run_intl_real_html.py --suite security --scheme auto"],
        ["CM 真机冒烟 / 回归", "python runner/run_suite.py --operator cm --env real --suite smoke / regression"],
        ["全菜单遍历截图（98 页）", "python runner/run_suite.py --operator cm --env real --suite navigation"],
        ["离线 Mock 执行（CI）", "python runner/run_suite.py --operator intl --env mock --suite smoke"],
        ["INTL Word 报告（见第 4 章）", "python tools/gen_intl_word.py --result <run_id> --suite <s>"],
    ],
    widths=[4.6, 10.9])
add_para(doc, "可选参数：--headed（有头调试）/ --browser firefox / --url 覆盖地址 / --admin-user --admin-pass 临时覆盖账号。"
              "退出码：0 = 全部通过，1 = 有失败（可直接接 CI 门禁）。", size=9.5, color=GRAY)

add_heading(doc, "3.3 自然语言生成用例（核心能力）", 2)
add_para(doc, "工作流程：① 扫描真实 UI 源码建立页面索引（setItemId('x') → fhId_x 运行时 id）→ ② 分词匹配目标页面（component 驼峰切分 + 中英同义词打分）→ ③ 匹配页面内功能元素 → ④ 跨页元素搜索（如 320MHz 信道宽度在 wifiAdvanced_5g 页）→ ⑤ 需求差距检测（gap：需求值不在源码选项时生成验证用例，真机失败即证明需求未实现）→ ⑥ 输出到 operators/{op}/cases/generated/。")
add_code(doc, """# 示例：生成"wifi 支持 320MHz 频段"用例（检测到 320MHz 未实现，生成 3 条用例含 gap 验证）
python -m generator.generate_case --operator cm --query "测试wifi基础设置功能支持320MHZ频段设置"
# UI 源码更新后加 --refresh 重建索引缓存""")

add_heading(doc, "3.4 用例编写规范（JSON）", 2)
add_para(doc, "用例位于 operators/{operator}/cases/*.json，每条用例由 id / module / priority / title / steps 组成，步骤为 real.* 动作序列：")
add_code(doc, """{
  "id": "TC-INTL-STATUS-001", "module": "Status", "priority": "P0",
  "title": "设备信息页加载",
  "steps": [
    {"action": "real.login", "params": {"role": "admin"}},
    {"action": "real.navigate_spa", "params": {"route": "/status/deviceInfo/deviceInfo"}},
    {"action": "real.assert_page", "params": {"component": "deviceInfo"}},
    {"action": "real.assert_element", "params": {"selector": "#fhId_SSID"}},
    {"action": "real.screenshot", "params": {"name": "device_info"}}
  ]
}""")
add_para(doc, "常用 real.* 动作：login / logout / navigate_spa / click_menu / click / fill / select_option / assert_page / "
              "assert_element / assert_option_present / assert_visible / assert_text_contains / ensure_switch / "
              "assert_switch_checked / assert_element_hidden / assert_input_value / click_button / screenshot / "
              "close_boxes（清弹窗）/ delete_wan_row（WAN 表格勾选删除）。"
              "选择器 key（如 login.username）从 selectors*.json 解析，也支持直接写原始选择器（#fhId_xxx、text=退出）。", size=9.5)

add_heading(doc, "3.5 双环境执行要点", 2)
add_table(doc,
    ["环境", "要点"],
    [
        ["真机 real", "配置修改类用例优先只读断言；连续 3 次密码错误锁定 1 分钟（security/锁定类套件置末执行）；负向登录用例需 auto_login:false；登录失败走 alert 弹窗断言（dialog 监听）；LAN/DHCP 类用例会触发网络重启，安排在回归末尾防级联失败"],
        ["Mock mock", "可真建/真改/真删，POST /api/reset 一键重置；端口已监听时自动复用（避免 Windows 双绑定）；适合 CI 无设备场景"],
    ],
    widths=[2.6, 12.9])

add_heading(doc, "3.6 INTL 真机执行链路（新老 UI 双执行器）", 2)
add_para(doc, "INTL 国际版真机不走 run_suite.py，按 UI 形态使用两个独立执行器（均每用例独立浏览器 context 状态隔离、"
              "逐用例记录 duration_s、内置 HTTPS 自签证书忽略、凭据从 .env（QCT_INTL_*）注入）："
              "runner/run_intl_real.py = SPA 新 UI（24 套件 109 条）；runner/run_intl_real_html.py = 老 UI HTML 多页版"
              "（17 模块 67 文件 201 条，含 SKIP 兼容、teardown logout、WAN 表格行操作等老 UI 特有机制）。")
add_table(doc,
    ["参数", "取值", "说明"],
    [
        ["执行器", "run_intl_real.py / run_intl_real_html.py", "新 UI 结果落 reports/intl_real/；老 UI 落 reports/intl_real_html/"],
        ["--suite", "套件名 / all", "新 UI：status/login/wan/reboot/security…；老 UI：wan/wifi/voip/security…（17 模块）"],
        ["--scheme", "https / http / auto", "自然语言可选（如 \"https加密\"、\"http明文\"、\"自动探测\"）；默认 auto=HTTPS 优先探测，失败回退 HTTP"],
        ["--headful", "开关", "有头调试模式"],
        ["--out", "目录", "自定义结果目录"],
    ],
    widths=[2.6, 4.0, 8.9])
add_code(doc, """# 新 UI（run_intl_real.py）：结果落 reports/intl_real/<run_id>/
python runner/run_intl_real.py --suite all --scheme auto      # 全量（约 25 分钟）
python runner/run_intl_real.py --suite status --scheme auto   # 单套件（约 1 分钟）

# 老 UI（run_intl_real_html.py）：结果落 reports/intl_real_html/<run_id>/
python runner/run_intl_real_html.py --suite all --scheme auto   # 全量（17 模块 201 条）

# 协议说明：HG6142HT 已开启 HTTPS 强制跳转（HTTP 301 -> HTTPS），
# auto/https 模式自动忽略自签证书；纯 http 指定也会被设备 301 到 HTTPS（设备端策略）""")
add_para(doc, "老 UI 特有机制：菜单/页面不存在时用例置 SKIP 不判失败（报告与通过率按执行数计算）；teardown 强制 logout"
              "（设备为服务端会话，context 关闭不清认证，越权用例依赖此清理）；WAN 表格定位按数据行打分（_find_wan_table，"
              "多页版无 #fhId_wanTable）、删除按行文本定位（delete_wan_row(row_text)）；固件上传用 set_input_files；"
              "security 锁定套件在老 UI 报告正常纳入统计，新 UI 报告排除主报告单独说明。", size=9.5)

add_heading(doc, "3.7 单套件回归一键 SOP（已固化，可复用）", 2)
add_para(doc, "单套件专项回归已固化为标准三步链，在 WorkBuddy 中说「按SOP直接跑」即可跳过环境探测/凭据核对直接执行：")
add_code(doc, """# 步骤 1：真机执行（约 1 分钟）
python runner/run_intl_real.py --suite <s> --scheme auto

# 步骤 2：生成报告（--suite 必须首次就带上，漏带会生成全量版报告需删除重做）
python tools/gen_intl_word.py --variant new_ui --result <run_id> --suite <s>

# 步骤 3：脱敏扫描 + 归档（解包 docx 扫描 CM/INTL 密码字面量，CLEAN 后复制到项目根，
#          命名：测试报告-INTL-REAL-<SUITE>-<设备型号>-<ts>.docx / 用例文档-INTL-REAL-<SUITE>-<ts>.docx）""")
add_para(doc, "实测数据（HG6142HT，2026-09-03）：status 7/7 约 63s、login 8/8 约 48s，全流程 2 个执行动作完成。", size=9.5, color=GRAY)

add_heading(doc, "3.8 扩展新运营商 / 新套件（6 步）", 2)
add_code(doc, """1. 复制 operators/cm/（或 intl/）为 operators/{new_op}/
2. 修改 profile.json（环境地址、账号占位符 ${VAR}、菜单模块、页面清单）
3. 修改 selectors*.json（登录/菜单/通用元素；真机选择器双文件与基线 profile 同步）
4. 编写 cases/*.json 用例（登录/网络类回归套件置末，防副作用级联）
5. 运行：python runner/run_suite.py --operator {new_op} --env real --suite smoke
6. NL 生成器 DEFAULT_UI_ROOTS 加入新运营商源码路径""")

add_heading(doc, "3.9 Skill 双端封装", 2)
add_table(doc,
    ["平台", "位置 / 安装方式", "触发示例"],
    [
        ["WorkBuddy", ".workbuddy/skills/qcoder-web-autotest/（项目级，随项目同步）", "直接自然语言对话触发（含「按SOP直接跑」）"],
        ["QCoder", "导入 skill_dist/qcoder-web-autotest.zip（SkillHub 兼容）", "同一条自然语言命令"],
    ],
    widths=[2.6, 7.0, 5.9])

add_heading(doc, "3.10 安全与注意事项", 2)
add_para(doc, "① 真机地址与账号不写入代码/profile.json，全部经 .env / 环境变量注入（${QCT_*} 占位符运行时解析），仓库可安全公开发布；CI 用 GitHub Secrets。"
              "② 任何入库内容（文档/代码/示例）一律不得含密码字面量，哪怕作为「反例示例」；docx 交付前解包扫 word/document.xml，命中即整改。"
              "③ 修改源码/选择器后注意 operators/{op}/selectors.json 与 profiles/selectors/ 基线选择器双文件同步。", size=10)

# ============ 四、测试报告生成说明 ============
add_heading(doc, "四、测试报告生成说明", 1)
add_para(doc, "执行完成后的结果（result.json + 截图）可通过三条工具链生成 Word/HTML 报告，全部自动嵌入截图、自动填充结果与结论，交付前已做凭据脱敏扫描。")

add_heading(doc, "4.1 INTL Word 报告（tools/gen_intl_word.py，主力工具）", 2)
add_para(doc, "面向 INTL 真机执行结果（run_intl_real.py / run_intl_real_html.py 输出，--variant 选择数据源目录），自动完成：读取 reports/ 最新（或指定 run_id）结果 → 分套件统计 → "
              "用例耗时填充 → 失败用例分析 → FH 品牌化封面（左上 logo）+ FH 页眉 → 输出用例文档与测试报告两个 DOCX。"
              "分析结论段已改为按本轮 result.json 动态生成（统计/耗时 TOP3/功能覆盖/专项观察），兼容全量与单套件模式，无数据时回退静态文案。")
add_table(doc,
    ["参数", "说明", "示例"],
    [
        ["--result", "run_id 或 latest（默认取最新主套件结果）", "--result 20260903_161815"],
        ["--variant", "报告数据源：new_ui（默认，读 reports/intl_real）/ html（读 reports/intl_real_html）", "--variant html"],
        ["--suite", "单套件专项报告（过滤用例与统计双侧）", "--suite status"],
        ["--mode", "case=仅用例文档 / report=仅测试报告 / both（默认）", "--mode report"],
        ["--out", "输出目录（默认 docs/case-docs/）", "--out ../reports"],
    ],
    widths=[2.6, 8.4, 4.5])
add_code(doc, """# 全量回归报告（新 UI，取最新结果）
python tools/gen_intl_word.py

# 指定 run_id 的测试报告
python tools/gen_intl_word.py --result 20260903_122623 --mode report

# 单套件专项（--suite 必须首次生成就带上，漏带会生成全量版需返工）
python tools/gen_intl_word.py --variant new_ui --result 20260903_161815 --suite status

# 老 UI 变体 + 单套件专项
python tools/gen_intl_word.py --variant html --suite wan --result 20260902_102955

# 输出：docs/case-docs/测试报告-INTL-REAL[-<SUITE>]-<时间戳>.docx + 用例文档-*.docx""")

add_heading(doc, "4.2 CM Word 报告（tools/gen_word_report.py）", 2)
add_para(doc, "面向 CM 执行结果（run_suite.py 输出），读取 reports/ 最新结果自动生成 Word 报告（FH 品牌化，密码自动脱敏）：")
add_code(doc, """pip install python-docx     # 如未安装
python tools/gen_word_report.py""")

add_heading(doc, "4.3 统一 DOCX 模板报告（e2e_bootstrap/scripts/gen-case-doc.js）", 2)
add_para(doc, "与执行报告同版式的统一模板（templates/test-report-template.docx），每条用例一页测试项表格"
              "（测试类型/目的/预置条件/测试浏览器/环境/步骤/期望/结果/结论/备注），步骤渲染人性化"
              "（real.navigate → 「导航」），支持三种模式：")
add_table(doc,
    ["模式", "命令", "产物"],
    [
        ["① 单套件设计文档", "node scripts/gen-case-doc.js <suite.json> --topic 主题", "用例文档-*.docx（结果=待执行）"],
        ["② 批量设计文档", "node scripts/gen-case-doc.js --all", "全部套件用例文档（排除 generated/）"],
        ["③ 执行报告", "node scripts/gen-case-doc.js --result <result.json>", "测试报告-*.docx（自动填结果/结论/截图）"],
    ],
    widths=[3.6, 6.9, 5.0])
add_code(doc, """cd e2e_bootstrap
# ① 单套件设计文档
node scripts/gen-case-doc.js ../operators/cm/cases/login.json --topic "CM登录界面验证用例"
# ② 批量设计文档
node scripts/gen-case-doc.js --all
# ③ 执行报告（自动匹配套件，截图路径来自 result.detail，嵌入各用例备注）
node scripts/gen-case-doc.js --result ../reports/<run_id>/result.json

# 常用选项：--template 模板路径 / --base-url / --preconditions
#           --qcoder-root 工程根 / --operator --suite（报告模式指定套件）""")

add_heading(doc, "4.4 e2e_bootstrap 自测报告（Node 链路）", 2)
add_code(doc, """cd e2e_bootstrap
cp .env.example .env          # E2E_BASE_URL / E2E_DEMO_PATH
npm install && npx playwright install chromium
npm run test:generate -- --input ./TEST_CASE_SPEC.md --name 新人快速上手   # 三字段生成骨架
npm test                                                                  # 执行 + 报告

# 产物：playwright-report/index.html（HTML）
#       self-test-reports/*.docx（Word，截图嵌入用例备注）""")

add_heading(doc, "4.5 报告内容与脱敏约定", 2)
add_table(doc,
    ["报告组成", "说明"],
    [
        ["封面 + 页眉", "FH logo 封面（左上）+ FH 页眉（tools/docx_branding.py），设备型号/日期/套件范围"],
        ["汇总统计", "总用例/通过/失败/跳过/超时/中断/通过率/总耗时；分套件统计表；单条耗时（均/最长 TOP3）"],
        ["用例明细", "每用例：步骤、期望、结果（通过/失败）、失败步骤与原因、备注嵌截图"],
        ["分析结论", "按本轮 result.json 动态生成：通过率/耗时画像/功能覆盖逐条/专项观察；无数据回退静态文案"],
        ["脱敏铁律", "任何密码不入 docx（字面值见内部扫描清单，取值仅存于工程根 .env）；交付前解包扫 word/document.xml 验证"],
    ],
    widths=[3.4, 12.1])

# ============ 五、附录 ============
add_heading(doc, "五、附录：关键约定速查", 1)
add_table(doc,
    ["约定", "说明"],
    [
        ["退出码", "0 = 全部通过，1 = 有失败（可接 CI 门禁）"],
        ["运行目录", "所有命令在项目根 qcoder-web-autotest-agent/ 下执行"],
        ["元素 id", "UI 源码 setItemId('x') → 运行时 id fhId_x；菜单 fhId_{英文标识}_L{level}，以 navigation 实测为准"],
        ["INTL 结果目录", "新 UI：reports/intl_real/<run_id>/；老 UI：reports/intl_real_html/<run_id>/"],
        ["套件顺序", "改表单/网络类套件（lan、wan CRUD、security 锁定）置末执行，防 DHCP 重启/锁定级联失败"],
        ["登录失败断言", "真机密码错误走 alert 弹窗（dialog 事件），不能用静态元素 #login_error_hint"],
        ["错误提示选择器", "新真机为 class：div.login_error_hint（selectors 已兼容 id 与 class 双写法）"],
        ["访问协议", "HG6142HT 当前 HTTPS 强制（HTTP 301 跳转）；--scheme auto 即可，无需手工处理自签证书"],
        ["双频合一", "CM 在「无线基本配置」（#fhId_onApplySameSSID）；INTL 在独立 bandSteering 页（#fhId_Enable）"],
        ["venv 路径", "Windows 下解释器在 venv\\Scripts\\python.exe（venv 根目录无 python.exe 属正常）"],
        ["发布路径", "发布仓库 = workspace 根 auto_web_test_repo/（聚合仓库），勿直接 push 子项目 .git"],
    ],
    widths=[3.4, 12.1])

# ============ 保存 ============
os.makedirs(os.path.dirname(OUT_PRIMARY), exist_ok=True)
out = OUT_PRIMARY
try:
    doc.save(out)
except PermissionError:
    out = OUT_FALLBACK
    doc.save(out)
print("SAVED:", out)
