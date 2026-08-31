# -*- coding: utf-8 -*-
"""生成《开发使用说明与工作流简介》简易 Word 文档"""
import os
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "开发使用说明与工作流简介.docx")
OUT_PATH = os.path.abspath(OUT_PATH)

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
        # 底部边框线
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
        # 底纹
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
# 页边距
for sec in doc.sections:
    sec.top_margin = Cm(2.2); sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.4); sec.right_margin = Cm(2.4)

# ============ 封面标题 ============
add_heading(doc, "QCoder Web AutoTest Agent", 0)
add_heading(doc, "开发使用说明与工作流简介", 0)
add_para(doc, "面向烽火网关真实 Web UI 的端到端自动化测试智能体（qcoder-web-autotest-agent）", size=11, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
add_para(doc, "版本：v1.1  |  日期：2026-08-31  |  适用：开发者 / 测试工程师", size=9, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)

# ============ 一、项目定位 ============
add_heading(doc, "一、项目定位", 1)
add_para(doc, "一句话定位：把「测试设计、用例维护、自动执行、失败分析和报告输出」固化成可重复流程的 Web 测试智能体——"
              "输入一句中文需求，自动生成可执行用例，在真机或离线 Mock 双环境执行，产出结构化报告（含截图）。")
add_para(doc, "提效目标：人工执行约 3 人日 → 智能体执行 ≤ 2 小时；Smoke ≤ 20 分钟；失败分析与报告整理自动完成。")

# ============ 二、整个工作流简介 ============
add_heading(doc, "二、整个工作流简介", 1)

add_heading(doc, "2.1 主执行链路", 2)
add_code(doc, """需求 / 修改点 / 一句中文自然语言
   │
   ▼
① 扫描真实 UI 源码 + 索引（setItemId → fhId_* 元素、菜单路由、下拉选项）
   ▼
② 自动生成可执行 JSON 用例（含需求差距 gap 检测）
   ▼
③ 设备 Profile + Selector 解析（运营商目录隔离，敏感信息经 .env 注入）
   ▼
④ Playwright 真机执行（--env real） / 离线 Mock 执行（--env mock）
   ▼
⑤ 自动报告：JSON / MD / HTML + 截图 + 覆盖矩阵
   ▼
⑥ AI 失败分析（selector_changed / product_bug / env_issue / script_bug）
   ▼
⑦ AI 覆盖分析（页面覆盖矩阵 / 缺口补充建议）""")

add_heading(doc, "2.2 四大闭环", 2)
add_table(doc,
    ["闭环", "流程"],
    [
        ["新功能", "需求 → AI 生成用例 → AI 生成脚本 → 人工审核入库"],
        ["修改点", "变更说明 → AI 影响分析 → 更新用例/selector → 推荐回归集"],
        ["版本回归", "版本选择 → 自动执行 → AI 失败归因 → 准入报告"],
        ["覆盖治理", "需求清单 → 用例库扫描 → 覆盖矩阵 → 缺口补充建议"],
    ],
    widths=[3.0, 12.5])
add_para(doc, "AI 工作流模板固化在 agent/workflows/：generate_cases（需求→用例）、update_cases_by_change（变更→用例更新）、"
              "select_regression（变更→回归集）、coverage_review（页面覆盖矩阵→缺口建议），QCoder/WorkBuddy 直接加载执行。", size=9.5)

add_heading(doc, "2.3 双运营商 × 双环境矩阵", 2)
add_table(doc,
    ["环境", "说明", "典型命令"],
    [
        ["cm（中国移动）", "烽火 HG3142F2 FTTR 网关（192.168.1.1），多页结构；四类范本套件真机 22/22 + mock 20/20 验证通过", "--operator cm"],
        ["intl（国际）", "HG6163FC1 国际版 / FG-8040H（SPA 单页结构 main.html#/）；navigation 实测 7 个 L1 × 24 个 L2 页面", "--operator intl"],
        ["real（真机）", "Playwright 驱动真实设备 + 截图；INTL 走独立执行器 run_intl_real.py（每用例独立 context）", "--env real"],
        ["mock（离线）", "本地 Mock 网关（127.0.0.1），无设备可跑，可接 CI", "--env mock"],
    ],
    widths=[3.4, 8.0, 4.1])

add_heading(doc, "2.4 目录结构速览", 2)
add_code(doc, """qcoder-web-autotest-agent/
├── core/config.py            # 统一配置：.env 加载 + ${VAR} 占位符解析
├── operators/
│   ├── cm/                   # 运营商：profile / selectors / cases（四类范本 + mock 套件）
│   └── intl/
│       ├── profile.json / selectors.json / selectors_real.json
│       └── cases/real/       # INTL 真机 24 套件（login/wan/status/reboot/security
│                             #   + wifi/lan/nat/firewall/account/ntp 等 19 个页面套件）
├── keywords/                 # 真机关键字层 real_keywords.py + 断言引擎
├── runner/run_suite.py       # CM 用例执行器 + 报告器（mock 兼容层回退读取 selectors）
├── runner/run_intl_real.py   # INTL 真机独立执行器（SPA 菜单 + fhId_，QCT_INTL_* 注入）
├── run_single.py             # 单用例快速执行（调试用）
├── run_nav_intl.py           # INTL 真机导航遍历（页面清单/覆盖矩阵数据源）
├── generator/                # NL 用例生成器（page_index + generate_case + index_cache）
├── mock_web_ui/              # 离线 Mock 网关（纯标准库，/api/reset 重置）
├── e2e_bootstrap/            # Node 端 Playwright E2E 基线（骨架生成 + DOCX 报告）
├── agent/workflows/          # QCoder AI 工作流模板（generate_cases / update_cases_by_change /
│                             #   select_regression / coverage_review / agent 系列）
├── skill_dist/               # QCoder SkillHub 技能包（*.zip）
├── tools/                    # gen_intl_word.py / gen_usage_doc.py / _verify_new.py 等
├── docs/                     # USAGE / DEPLOYMENT / TEMPLATES / INTL_PAGE_COVERAGE
└── reports/                  # 执行报告（自动生成，gitignore）""")

# ============ 三、开发使用说明 ============
add_heading(doc, "三、开发使用说明", 1)

add_heading(doc, "3.1 环境准备", 2)
add_para(doc, "依赖：Python ≥ 3.8（Playwright ≥ 1.44 + Chromium）；Node.js ≥ 16（仅 e2e_bootstrap 链路需要）。")
add_code(doc, """cd qcoder-web-autotest-agent
pip install -r requirements.txt
playwright install chromium

# 敏感配置注入（.env 已 gitignore，不会上传）
cp .env.example .env          # 填写 QCT_CM_BASE_URL / QCT_CM_ADMIN_USER 等""")

add_heading(doc, "3.2 快速开始（常用命令）", 2)
add_table(doc,
    ["用途", "命令"],
    [
        ["NL 生成用例（无需设备）", "python -m generator.generate_case --operator cm --query \"测试wan连接页面vlan绑定功能\""],
        ["CM 真机冒烟 / 回归", "python runner/run_suite.py --operator cm --env real --suite smoke / regression"],
        ["全菜单遍历截图（98 页）", "python runner/run_suite.py --operator cm --env real --suite navigation"],
        ["INTL 真机全套件执行", "python runner/run_intl_real.py --suite wan（24 套件，QCT_INTL_* 凭据走 .env）"],
        ["INTL 单用例调试", "python run_single.py --suite firewall --case INTL-FIREWALL-004"],
        ["INTL 导航遍历（覆盖矩阵）", "python run_nav_intl.py（输出 docs/INTL_PAGE_COVERAGE.md 数据源）"],
        ["离线 Mock 执行（CI）", "python runner/run_suite.py --operator intl --env mock --suite smoke"],
        ["Word 测试报告", "python tools/gen_word_report.py"],
        ["用例文档 / 执行报告 DOCX", "node scripts/gen-case-doc.js --all / --result <result.json>（在 e2e_bootstrap/ 下）"],
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
  "id": "TC-CM-WIFI-001", "module": "Network", "priority": "P0",
  "title": "WiFi 基本设置页加载",
  "steps": [
    {"action": "real.login", "params": {"role": "admin"}},
    {"action": "real.navigate_spa", "params": {"route": "/network/wifiSettings/wifiBasic"}},
    {"action": "real.assert_page", "params": {"component": "wifiBasic"}},
    {"action": "real.assert_element", "params": {"selector": "#fhId_SSID"}},
    {"action": "real.screenshot", "params": {"name": "wifi_basic"}}
  ]
}""")
add_para(doc, "常用 real.* 动作：login / logout / navigate_spa / click_menu / click / fill / select_option / assert_page / "
              "assert_element / assert_option_present / assert_visible / assert_text_contains / ensure_switch / "
              "assert_switch_checked / assert_element_hidden / assert_input_value / click_button / screenshot。"
              "选择器 key（如 login.username）从 selectors.json 解析，也支持直接写原始选择器（#fhId_xxx、text=退出）。", size=9.5)

add_heading(doc, "3.5 双环境执行要点", 2)
add_table(doc,
    ["环境", "要点"],
    [
        ["CM 真机 real", "只做只读断言，不点「保存设置」（WiFi/VLAN 等配置用例零风险）；连续 3 次密码错误锁定 1 分钟；负向登录用例需 auto_login:false；登录失败走 alert 弹窗断言（dialog 监听）"],
        ["INTL 真机 real", "独立执行器 run_intl_real.py：每用例独立浏览器 context（天然状态隔离）；SPA main.html#/ 路由 + fhId_ 菜单；确认框为英文 locale（Confirm/Cancel），real_keywords 自动兼容中英文；凭据经 QCT_INTL_* 环境变量注入（.env），fill() 支持 ${QCT_INTL_*} 占位符解析"],
        ["Mock mock", "可真建/真改/真删，POST /api/reset 一键重置；端口已监听时复用（避免 Windows 双绑定）；适合 CI 无设备场景"],
    ],
    widths=[2.6, 12.9])

add_heading(doc, "3.6 扩展新运营商（6 步）", 2)
add_code(doc, """1. 复制 operators/cm/ 为 operators/{new_op}/
2. 修改 profile.json（环境地址、账号、菜单模块、页面清单）
3. 修改 selectors.json（登录/菜单/通用元素选择器；真机额外维护 selectors_real.json）
4. 编写 cases/*.json 用例（真机放 cases/real/，mock 放 cases/）
5. 运行：python runner/run_suite.py --operator {new_op} --env real --suite smoke
6. NL 生成器 DEFAULT_UI_ROOTS 加入新运营商源码路径
（INTL 真机为 SPA 单页结构时，按 run_intl_real.py 模式建独立执行器 + selectors_real.json）""")

add_heading(doc, "3.7 报告与产物", 2)
add_para(doc, "每次运行生成 reports/{时间戳}_{operator}_{env}_{suite}/：result.json（用例/步骤级结果）、report.json / report.html（人读报告）、screenshots/*.png（PASS 按步骤命名，FAIL 前缀标红）。", size=10)
add_para(doc, "统一 DOCX 模板（gen-case-doc.js 三种模式）：① 单套件设计文档（结果=待执行）② --all 批量设计文档 ③ --result 执行报告（自动填充结果/结论/失败原因/汇总 + 嵌入截图，截图路径来自 result.detail）。", size=10)
add_para(doc, "e2e_bootstrap（Node 链路）：三字段输入 TEST_CASE_SPEC.md → npm run test:generate 生成骨架 → npm test 执行并输出 HTML/DOCX 报告。", size=10)
add_para(doc, "INTL 真机覆盖矩阵（docs/INTL_PAGE_COVERAGE.md）：以 navigation 实测为准的 24 页清单（7 个 L1 × 24 个 L2），逐页标注用例覆盖情况，作为 AI 全覆盖工作的基准；run_nav_intl.py 负责重新遍历刷新数据源。", size=10)

add_heading(doc, "3.8 Skill 双端封装", 2)
add_table(doc,
    ["平台", "位置 / 安装方式", "触发示例"],
    [
        ["WorkBuddy", ".workbuddy/skills/qcoder-web-autotest/（项目级，随项目同步）", "直接自然语言对话触发"],
        ["QCoder", "导入 skill_dist/qcoder-web-autotest.zip（SkillHub 兼容）", "同一条自然语言命令"],
    ],
    widths=[2.6, 7.0, 5.9])

add_heading(doc, "3.9 安全与注意事项", 2)
add_para(doc, "① 真机地址与账号不写入代码/profile.json，全部经 .env / 环境变量注入（${QCT_*} 占位符运行时解析），仓库可安全公开发布；CI 用 GitHub Secrets。"
              "② 收到外部压缩包/目录先扫两套真实密码（CM 与 INTL 各一套），docx 是 zip 需解包扫 word/document.xml；git log -S 对含特殊字符（如 |）的字符串会漏报，用 git rev-list --all 逐个 git grep -lF 最可靠。"
              "③ 修改源码/选择器后注意 operators/{op}/selectors.json 与 profiles/selectors/ 基线选择器双文件同步。"
              "④ INTL 真机凭据用 QCT_INTL_ADMIN_PASS / QCT_INTL_USER_PASS（.env 配置，无默认值），run_intl_real.py 的 fill() 会自动解析用例内 ${QCT_INTL_*} 占位符。", size=10)

# ============ 四、附录 ============
add_heading(doc, "四、附录：关键约定速查", 1)
add_table(doc,
    ["约定", "说明"],
    [
        ["退出码", "0 = 全部通过，1 = 有失败（可接 CI 门禁）"],
        ["运行目录", "所有命令在项目根 qcoder-web-autotest-agent/ 下执行"],
        ["元素 id", "UI 源码 setItemId('x') → 运行时 id fhId_x；菜单 fhId_{英文标识}_L{level}"],
        ["会话隔离", "共享 session 下，修改表单的用例末尾需刷新页面或复位关键选择，避免脏状态继承；INTL 真机每用例独立 context 天然隔离"],
        ["登录失败断言", "真机密码错误走 alert 弹窗（dialog 事件），不能用静态元素 #login_error_hint"],
        ["确认框", "INTL 真机为英文 locale（Confirm/Cancel），real_keywords 自动兼容中英文（确定/Confirm/OK）"],
        ["双频合一", "CM 在「无线基本配置」（#fhId_onApplySameSSID）；INTL 在独立 bandSteering 页（#fhId_Enable）"],
        ["INTL 凭据", "QCT_INTL_BASE_URL/ADMIN_USER/ADMIN_PASS/USER_USER/USER_PASS（.env 注入，无默认值）"],
    ],
    widths=[3.4, 12.1])

doc.save(OUT_PATH)
print("SAVED:", OUT_PATH)
