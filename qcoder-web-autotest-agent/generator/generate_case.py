# -*- coding: utf-8 -*-
"""自然语言 -> 可执行测试用例 生成器。

输入一句中文需求描述（如"测试wan连接页面vlan绑定功能"、
"测试wifi基础设置功能支持320MHZ频段设置"），基于真实 UI 源码索引
（page_index.py）自动生成可由 runner/run_suite.py 执行的用例 JSON：

  1. 分词并匹配目标页面（component/标题/提示/元素 label 打分）
  2. 匹配页面内功能元素（label/选项命中）
  3. 跨页元素搜索：若目标功能元素不在得分最高页面，自动定位其真实所在页
  4. 需求差距检测（gap）：如需求 320MHz 而源码选项只有 20~160MHz，
     仍生成 assert_option_present 用例（真机执行将失败，即暴露需求未实现）
  5. 输出 operators/{op}/cases/generated/{name}.json

用法（项目根目录）:
    python -m generator.generate_case --operator cm --query "测试wan连接页面vlan绑定功能"
    python -m generator.generate_case --operator cm --query "测试wifi基础设置功能支持320MHZ频段设置"

生成后执行（有真机时）:
    python runner/run_suite.py --operator cm --env real --suite generated/{name}
"""
import argparse
import io
import json
import os
import re
import sys

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from generator.page_index import build_index, clear_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STOPWORDS = {
    "测试", "页面", "功能", "支持", "验证", "检查", "的", "用例", "自动",
    "生成", "一下", "能够", "可以", "相关", "进行", "请", "我", "设置",
}

# 中文词 -> component 英文词段映射（camelCase 切分后匹配）
ZH_EN = {
    "基础": ["basic"], "连接": ["connect", "conn"], "绑定": ["bind"],
    "高级": ["advanced"], "状态": ["status"], "安全": ["security"],
    "管理": ["manage", "management"], "升级": ["up", "upgrade"],
    "恢复": ["restore", "reset"], "过滤": ["filter"], "诊断": ["diag"],
    "帮助": ["help"], "应用": ["app", "application"], "网络": ["network"],
    "无线": ["wifi", "wireless"], "开关": ["enable", "switch"],
}

# 功能词 -> 元素 label 匹配关键词（用于跨页元素定位）
FEATURE_KEYWORDS = {
    "频段": ["频宽", "带宽", "频段", "信道宽度", "bandwidth", "channel"],
    "频宽": ["频宽", "带宽", "信道宽度", "bandwidth", "channel"],
    "带宽": ["频宽", "带宽", "信道宽度", "bandwidth", "channel"],
    "信道": ["信道", "channel"],
    "绑定": ["绑定", "bind", "vlan"],
    "加密": ["加密", "encryption"],
    "认证": ["认证", "security", "mode"],
    "功率": ["功率", "power", "光功率"],
}


# ------------------------------------------------------------------ 分词
def tokenize(query):
    q = query.lower()
    # 先剔除停用词，避免粘连（"频段设置功能" -> "频段"）
    for w in STOPWORDS:
        q = q.replace(w, " ")
    en_tokens = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", q)
    zh_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", q)
    tokens = []
    for t in en_tokens + zh_tokens:
        if t in STOPWORDS or t in tokens:
            continue
        tokens.append(t)
    return tokens


def extract_numbers(query):
    """提取 数字+单位 需求（如 320MHZ -> {'value': '320', 'unit': 'mhz'}）。"""
    out = []
    for m in re.finditer(r"(\d+)\s*(mhz|dbm|ms|us|%|位|db)", query.lower()):
        out.append({"value": m.group(1), "unit": m.group(2)})
    return out


# ------------------------------------------------------------------ 匹配
def component_tokens(component):
    """wifiAdvanced_5g -> ['wifi', 'advanced', '5g']（camelCase 切分）。"""
    words = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", component)
    return [w.lower() for w in words]


def element_supports_unit(el, unit):
    """判断元素选项域是否与需求单位一致（如 320MHz 只对 MHz 型选项做差距检测）。

    避免把"频段(2.4G/5G)"这类非带宽选择器误报为 320MHz 差距。
    """
    if not unit or not el.get("options"):
        return True  # 无单位需求或动态选项（v-for），不做域过滤
    u = unit.lower()
    return any(u in f"{o.get('label', '')} {o.get('value', '')}".lower()
               for o in el["options"])


def score_page(page, tokens):
    comp = page["component"].lower()
    comp_words = component_tokens(page["component"])
    title = (page["title"] or "").lower()
    hint = (page["hint"] or "").lower()
    labels = " ".join((el.get("label") or "") for el in page["elements"]).lower()
    score = 0
    for t in tokens:
        if re.search(r"[a-z0-9]", t):
            # 英文/数字词：component 词段精确命中 > 子串命中
            if t in comp_words:
                score += 12
            elif t in comp:
                score += 10
            elif t in title:
                score += 8
            elif t in labels:
                score += 5
            elif t in hint:
                score += 4
        else:
            # 中文词：先试中英同义词映射到 component 词段
            en_words = ZH_EN.get(t, [])
            if any(w in comp_words for w in en_words):
                score += 8
            elif t in comp:
                score += 8
            if t in title:
                score += 8
            elif t in labels:
                score += 5
            elif t in hint:
                score += 4
    return score


def match_page(pages, tokens):
    """返回得分最高页面（同分时元素多者胜）。"""
    best, best_score = None, -1
    for p in pages:
        s = score_page(p, tokens) * 100 + min(len(p["elements"]), 30)
        if s > best_score:
            best, best_score = p, s
    return best


def match_elements_in_page(page, tokens):
    """在页面内按 label/id 命中的元素（保持源码顺序）。"""
    hits = []
    for el in page["elements"]:
        hay = f"{el.get('label') or ''} {el['id']}".lower()
        if any(t in hay for t in tokens):
            hits.append(el)
    return hits


def global_search_element(pages, tokens, numbers):
    """按功能词全局搜索元素（label 子串命中），用于跨页定位。

    如"320MHz 频段"的实际元素（信道宽度管理）在 wifiAdvanced_5g 而非
    wifiBasic。返回 [(page, element), ...]。
    """
    feature_kws = set()
    for t in tokens:
        feature_kws.update(FEATURE_KEYWORDS.get(t, []))
    results = []
    for p in pages:
        for el in p["elements"]:
            label = (el.get("label") or "")
            eid = el["id"]
            hay = f"{label} {eid}".lower()
            if not any(kw.lower() in hay for kw in feature_kws):
                continue
            if el["type"] in ("select", "input") and el["id"] not in ("onApply",):
                results.append((p, el))
    return results


def option_matches(options, value, unit=""):
    """判断选项列表中是否含指定值（如 320 + mhz）。"""
    if not options:
        return False
    for o in options:
        text = f"{o.get('label', '')} {o.get('value', '')}".lower()
        if value and value in re.findall(r"\d+", text):
            if not unit or unit in text:
                return True
    return False


# ------------------------------------------------------------------ 用例生成
def build_case(operator, page, elements, numbers, query, seq):
    """为一组（页面, 元素）生成一条用例 dict。返回 (case, gaps)。"""
    comp = page["component"]
    case_id = f"TC-{operator.upper()}-GEN-{seq:03d}"
    steps = [
        {"action": "real.login", "params": {"role": "admin"}},
        {"action": "real.navigate_spa", "params": {"route": page["route"] or comp}},
        {"action": "real.assert_page", "params": {"component": comp},
         "expect": {"visible": "page.container"}},
        {"action": "real.screenshot",
         "params": {"name": f"gen_{comp}_01_loaded"}},
    ]
    gaps = []
    step_no = 2
    fmt_unit = {"mhz": "MHz", "dbm": "dBm", "ms": "ms", "us": "us",
                "%": "%", "位": "位", "db": "dB"}

    for el in elements:
        # 元素存在性断言
        steps.append({"action": "real.assert_element",
                      "params": {"selector": el["selector"]}})
        # 需求值 -> 选项断言（差距检测核心）
        for n in numbers:
            req = f"{n['value']}{fmt_unit.get(n['unit'], n['unit'].upper())}"
            if el["type"] != "select":
                continue
            # 单位域过滤：元素选项与需求单位无关时跳过（避免误报）
            if not element_supports_unit(el, n["unit"]):
                continue
            if option_matches(el["options"], n["value"], ""):
                steps.append({"action": "real.select_option",
                              "params": {"selector": el["selector"],
                                         "option_text": req}})
                steps.append({"action": "real.screenshot",
                              "params": {"name": f"gen_{comp}_0{step_no}_selected_{req}"}})
            else:
                # UI 源码中无该选项：生成"验证选项存在"用例（真机执行失败=需求未实现）
                gaps.append({
                    "page": comp, "element": el["id"],
                    "label": el.get("label"),
                    "required": req,
                    "available_options": [o.get("label") for o in el["options"]][:10],
                })
                steps.append({"action": "real.assert_option_present",
                              "params": {"selector": el["selector"],
                                         "option_text": req},
                              "note": "gap check: 需求值若未实现，此步将失败"})
            step_no += 1

    steps.append({"action": "real.screenshot",
                  "params": {"name": f"gen_{comp}_final"}})
    title = (page["title"] or comp) + (
        f" - {'/'.join(e['id'] for e in elements[:3])}" if elements else "")
    case = {
        "id": case_id,
        "module": "Generated",
        "priority": "P1",
        "title": title,
        "generated_from": query,
        "source_file": page["file"],
        "route": page["route"],
        "steps": steps,
    }
    if gaps:
        case["requirement_gaps"] = gaps
    return case, gaps


def generate(operator, query, out_name=None, refresh=False):
    if refresh:
        clear_cache(operator)
    pages, stats = build_index(operator)
    tokens = tokenize(query)
    numbers = extract_numbers(query)
    if not tokens:
        raise SystemExit(f"无法从 query 中提取有效关键词: {query}")

    # 1) 主页面匹配
    main_page = match_page(pages, tokens)
    if not main_page:
        raise SystemExit("页面索引为空，请先运行 generator/page_index.py")

    # 2) 页面内元素命中
    elements = match_elements_in_page(main_page, tokens)

    cases, all_gaps = [], []
    seq = 1
    case, gaps = build_case(operator, main_page, elements, numbers, query, seq)
    cases.append(case)
    all_gaps.extend(gaps)
    used_pages = {main_page["component"]}

    # 3) 跨页元素搜索（功能元素不在主页面时）
    #    仅当主页面内没有命中任何与功能词相关的元素时触发
    feature_hits_main = any(
        any(kw in ((e.get("label") or "") + e["id"]).lower()
            for kw in FEATURE_KEYWORDS.get(t, [t]))
        for t in tokens for e in elements)
    if not feature_hits_main or numbers:
        # 按页面分组，每页取最优元素（静态选项多者优先）
        by_page = {}
        order = []
        for p, el in global_search_element(pages, tokens, numbers):
            if p["component"] in used_pages:
                continue
            if p["component"] not in by_page:
                by_page[p["component"]] = []
                order.append(p["component"])
            by_page[p["component"]].append((p, el))
        for comp_name in order:
            lst = by_page[comp_name]
            # 数值需求：只保留选项域匹配该单位的元素
            if numbers:
                units = [n["unit"] for n in numbers if n["unit"]]
                lst = [(p, el) for p, el in lst
                       if all(element_supports_unit(el, u) for u in units)]
                if not lst:
                    continue
            p, el = max(lst, key=lambda item: len(item[1]["options"]))
            if numbers and el["type"] == "select":
                seq += 1
                case, gaps = build_case(operator, p, [el], numbers, query, seq)
                cases.append(case)
                all_gaps.extend(gaps)
                used_pages.add(p["component"])

    # 4) 输出套件文件
    if not out_name:
        slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:40]
        out_name = f"gen_{slug}" if slug else "gen_case"
    out_dir = os.path.join(ROOT, "operators", operator, "cases", "generated")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{out_name}.json")
    suite_data = {
        "suite_id": f"{operator.upper()}-GEN-{out_name.upper()}",
        "operator": operator,
        "env": "real",
        "title": f"NL 生成套件：{query}",
        "generator": "generate_case.py",
        "cases": cases,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(suite_data, f, ensure_ascii=False, indent=2)

    # 5) 生成报告
    report = {
        "operator": operator,
        "query": query,
        "tokens": tokens,
        "numbers": numbers,
        "index_stats": stats,
        "matched_pages": [c["source_file"] for c in cases],
        "cases": [{"id": c["id"], "title": c["title"],
                   "steps": len(c["steps"])} for c in cases],
        "requirement_gaps": all_gaps,
        "suite_file": os.path.relpath(out_path, ROOT),
        "run_command": f"python runner/run_suite.py --operator {operator} "
                       f"--env real --suite generated/{out_name}",
    }
    rep_path = os.path.join(out_dir, f"{out_name}_report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 控制台摘要
    print(f"[GEN] query        : {query}")
    print(f"[GEN] tokens       : {tokens}  numbers: {numbers}")
    print(f"[GEN] index        : {stats['pages_indexed']} pages / "
          f"{stats['elements_total']} elements")
    for c in cases:
        print(f"[GEN] case         : {c['id']}  {c['title']}  ({len(c['steps'])} steps)")
    if all_gaps:
        print("[GEN] ⚠ 需求差距（UI 源码中未实现，已生成验证用例，真机执行将失败）:")
        for g in all_gaps:
            print(f"       - {g['page']}/{g['element']}({g['label']}) "
                  f"需求 {g['required']}，现有选项 {g['available_options']}")
    else:
        print("[GEN] 需求差距     : 无")
    print(f"[GEN] suite file   : {report['suite_file']}")
    print(f"[GEN] run command  : {report['run_command']}")
    return report


def main():
    ap = argparse.ArgumentParser(
        description="自然语言生成 UI 测试用例（基于真实 UI 源码索引）")
    ap.add_argument("--operator", required=True, choices=["cm", "intl"],
                    help="运营商: cm / intl")
    ap.add_argument("--query", required=True,
                    help='自然语言需求，如 "测试wan连接页面vlan绑定功能"')
    ap.add_argument("--out-name", default=None, help="输出套件名（默认按 query 生成）")
    ap.add_argument("--refresh", action="store_true",
                    help="强制重建源码索引缓存")
    args = ap.parse_args()
    generate(args.operator, args.query, args.out_name, args.refresh)


if __name__ == "__main__":
    main()
