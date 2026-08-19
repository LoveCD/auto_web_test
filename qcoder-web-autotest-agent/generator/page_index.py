# -*- coding: utf-8 -*-
"""真实 UI 源码页面索引器。

扫描运营商 UI 源码目录（fiberweb SPA 的 content/pages/*.js），提取每个页面的：
  - component 名（文件名，即路由组件名）
  - 页面标题 / 提示文本（main_header_title / main_header_hint）
  - 菜单路由（menudata.js 中 path -> component 映射）
  - 元素清单：setItemId('x') 生成的运行时 id fhId_x、表单 label、控件类型、
    下拉选项（el-option label/value）、数值校验规则（min/max）

供自然语言用例生成器（generate_case.py）做页面/元素匹配。
索引可缓存为 JSON，避免每次重新扫描 139+ 个源文件。
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from core.config import load_dotenv  # noqa: E402

load_dotenv()  # 确保 QCT_UI_SOURCE_* 环境变量来自 .env

# 默认 UI 源码根目录（web 仓库）
# 可通过环境变量 QCT_UI_SOURCE_CM_DIR / QCT_UI_SOURCE_INTL_DIR 覆盖，
# 未配置时回退到工程同级的 web 仓库相对路径；索引缓存存在时无需源码目录。
DEFAULT_UI_ROOTS = {
    "cm": os.environ.get("QCT_UI_SOURCE_CM_DIR")
          or os.path.join(ROOT, "..", "web", "web", "UI", "CM", "fiberweb", "html", "src"),
    "intl": os.environ.get("QCT_UI_SOURCE_INTL_DIR")
            or os.path.join(ROOT, "..", "web", "web", "UI", "INTL", "fiberweb", "html", "src"),
}
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index_cache")

# ------------------------------------------------------------------ 正则
RE_HEADER_TITLE = re.compile(r'main_header_title">(?:\s*\$t\(\'([^\']+)\'\)|([^<]{1,60}))<')
RE_HEADER_HINT = re.compile(r'main_header_hint">(?:\s*\$t\(\'([^\']+)\'\)|([^<]{1,200}))<')
RE_SET_ITEM_ID = re.compile(r"setItemId\(\s*'([^']+)'\s*\)")
RE_SET_ITEM_ID_DYN = re.compile(r"setItemId\(\s*'([^']+)'\s*\+")
RE_FORM_ITEM = re.compile(r"<el-form-item\b([^>]*)>")
RE_LABEL_ATTR = re.compile(r"""(?:label|:label)\s*=\s*\\?["']([^"'>]*?)\\?["']""")
RE_LABEL_I18N = re.compile(r"""\$t\(\s*\\?['"]([^'">]+?)\\?['"]\s*\)""")
RE_OPTION = re.compile(
    r"""<el-option\s[^>]*?label\s*=\s*\\?["']([^"'>]*?)\\?["'][^>]*?value\s*=\s*\\?["']([^"'>]*?)\\?["']""")
RE_OPTION_VALUE_ONLY = re.compile(
    r"""<el-option\s[^>]*?value\s*=\s*\\?["']([^"'>]*?)\\?["'][^>]*?label\s*=\s*\\?["']([^"'>]*?)\\?["']""")
RE_BUTTON = re.compile(r"""<el-button\b([^>]*)>([^<]{0,30})<""")
RE_INPUT_BUTTON = re.compile(
    r"""<input[^>]*type=["']button["'][^>]*value=["']([^"']{1,30})["']""")
RE_CHECK_RULES = re.compile(r"(\w+)\s*:\s*\[\s*\{([^\]]{0,400}?)\}\s*,?\s*\]")
RE_MIN = re.compile(r"min:\s*(\d+)")
RE_MAX = re.compile(r"max:\s*(\d+)")
RE_NUMTYPE = re.compile(r"type:\s*'number'")

CONTROL_TYPES = [
    ("el-select", "select"), ("el-input", "input"), ("el-switch", "switch"),
    ("el-checkbox", "checkbox"), ("el-radio", "radio"), ("el-button", "button"),
]


def _read_text(path):
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
            # 还原 JS 模板字符串转义：setItemId(\'x\') -> setItemId('x')
            text = text.replace("\\'", "'").replace('\\"', '"')
            return text
        except UnicodeDecodeError:
            continue
    return ""


def _extract_label(attrs):
    """从 el-form-item 属性串提取 label：兼容 label="中文" 与 :label="$t('Key')"。"""
    m = RE_LABEL_ATTR.search(attrs)
    if not m:
        return None
    label = m.group(1).strip()
    m2 = RE_LABEL_I18N.search(label)
    if m2:
        label = m2.group(1).strip()
    return label or None


def _extract_prop(attrs):
    m = re.search(r"""prop\s*=\s*\\?["'](\w+)\\?["']""", attrs)
    return m.group(1) if m else None


def _detect_control_type(window):
    for tag, ctype in CONTROL_TYPES:
        if tag in window:
            return ctype
    return "unknown"


def _parse_validation(text, prop):
    """从 checkData 校验规则中提取数值范围（如 VLAN ID 1~4094）。"""
    if not prop:
        return None
    for m in RE_CHECK_RULES.finditer(text):
        if m.group(1) != prop:
            continue
        body = m.group(2)
        if not RE_NUMTYPE.search(body):
            continue
        vmin = RE_MIN.search(body)
        vmax = RE_MAX.search(body)
        if vmin or vmax:
            return {
                "type": "number",
                "min": int(vmin.group(1)) if vmin else None,
                "max": int(vmax.group(1)) if vmax else None,
            }
    return None


def parse_menudata(menudata_path):
    """解析 menudata.js，返回 {component: route} 映射。"""
    if not menudata_path or not os.path.exists(menudata_path):
        return {}
    text = _read_text(menudata_path)
    route_map = {}
    for m in re.finditer(
            r"path:\s*'([^']+)'\s*,\s*component:\s*getRoute\('content/pages/([^']+)'\)",
            text):
        route, comp = m.group(1), m.group(2)
        route_map.setdefault(comp, route)
    return route_map


def parse_page_file(path, route_map):
    """解析单个页面源码文件，返回索引条目（无元素时返回 None）。"""
    component = os.path.splitext(os.path.basename(path))[0]
    text = _read_text(path)
    if not text:
        return None

    page = {
        "component": component,
        "file": os.path.basename(path),
        "title": None,
        "hint": None,
        "route": route_map.get(component),
        "elements": [],
    }
    m = RE_HEADER_TITLE.search(text)
    if m:
        page["title"] = (m.group(1) or m.group(2) or "").strip() or None
    m = RE_HEADER_HINT.search(text)
    if m:
        page["hint"] = (m.group(1) or m.group(2) or "").strip() or None

    seen = set()

    def add_element(eid, label, ctype, prop, options, validation=None, text_=None):
        if not eid or eid in seen:
            return
        seen.add(eid)
        el = {
            "id": eid,
            "selector": f"#fhId_{eid}",
            "label": label,
            "type": ctype,
            "prop": prop,
            "options": options or [],
        }
        if validation:
            el["validation"] = validation
        if text_:
            el["text"] = text_.strip()[:30]
        page["elements"].append(el)

    # ---- el-form-item 区域：label + 控件 id + 选项 + 校验
    for m in RE_FORM_ITEM.finditer(text):
        attrs = m.group(1)
        label = _extract_label(attrs)
        prop = _extract_prop(attrs)
        end = text.find("</el-form-item>", m.start())
        window = text[m.start(): end if end > 0 else m.start() + 3000]
        ctype = _detect_control_type(window)
        options = []
        if ctype == "select":
            for om in RE_OPTION.finditer(window):
                options.append({"label": om.group(1).strip(), "value": om.group(2).strip()})
            if not options:
                for om in RE_OPTION_VALUE_ONLY.finditer(window):
                    options.append({"label": om.group(2).strip(), "value": om.group(1).strip()})
        ids = RE_SET_ITEM_ID.findall(window)
        main_id = ids[0] if ids else None
        if main_id:
            add_element(main_id, label, ctype, prop, options,
                        _parse_validation(text, prop))

    # ---- 独立按钮（不在 form-item 内）
    for m in RE_BUTTON.finditer(text):
        attrs, btext = m.group(1), m.group(2).strip()
        idm = re.search(r"""setItemId\(\s*'([^']+)'""", attrs) or \
            re.search(r"""id=["']fhId_([^"']+)["']""", attrs)
        if idm:
            add_element(idm.group(1), None, "button", None, [], None, btext)
    for m in RE_INPUT_BUTTON.finditer(text):
        add_element(None, None, "button", None, [], None, m.group(1))

    return page if page["elements"] else None


def build_index(operator, ui_src_root=None, use_cache=True):
    """构建（或读取缓存）运营商页面索引。返回 (pages, stats)。"""
    cache_path = os.path.join(CACHE_DIR, f"{operator}.json")
    if use_cache and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["pages"], data["stats"]

    src_root = ui_src_root or os.path.abspath(DEFAULT_UI_ROOTS[operator])
    pages_dir = os.path.join(src_root, "content", "pages")
    menudata = os.path.join(src_root, "menu", "menudata.js")
    if not os.path.isdir(pages_dir):
        raise SystemExit(
            f"UI source not found: {pages_dir}\n"
            f"  请设置环境变量 QCT_UI_SOURCE_{operator.upper()}_DIR 指向 UI 源码 src 目录，"
            "或先在有源码的环境构建索引缓存（generator/index_cache/）。")
    route_map = parse_menudata(menudata)

    pages = []
    for fn in sorted(os.listdir(pages_dir)):
        if not fn.endswith(".js"):
            continue
        entry = parse_page_file(os.path.join(pages_dir, fn), route_map)
        if entry:
            pages.append(entry)

    stats = {
        "operator": operator,
        "pages_scanned": len([f for f in os.listdir(pages_dir) if f.endswith(".js")]),
        "pages_indexed": len(pages),
        "elements_total": sum(len(p["elements"]) for p in pages),
        "routes_mapped": len([p for p in pages if p["route"]]),
    }
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"stats": stats, "pages": pages}, f, ensure_ascii=False, indent=1)
    return pages, stats


def clear_cache(operator=None):
    """清除索引缓存（UI 源码更新后调用）。"""
    if not os.path.isdir(CACHE_DIR):
        return
    for fn in os.listdir(CACHE_DIR):
        if operator and not fn.startswith(operator):
            continue
        os.remove(os.path.join(CACHE_DIR, fn))


if __name__ == "__main__":
    import sys
    op = sys.argv[1] if len(sys.argv) > 1 else "cm"
    pgs, st = build_index(op, use_cache=False)
    print(json.dumps(st, ensure_ascii=False, indent=2))
    for p in pgs[:5]:
        print(f"\n== {p['component']} (route={p['route']}) title={p['title']}")
        for el in p["elements"][:8]:
            print(f"   {el['id']:<32} {el['type']:<8} label={el['label']} "
                  f"opts={len(el['options'])}")
