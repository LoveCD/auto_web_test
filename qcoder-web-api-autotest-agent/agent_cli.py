import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent
CASES_DIR = ROOT / "cases"
REPORTS_DIR = ROOT / "reports"
OUTPUT_DIR = ROOT / "ai_outputs"


MODULE_KEYWORDS = {
    "Login": ["login", "auth", "token", "password", "credential", "unauthorized"],
    "Status": ["status", "version", "uptime", "online"],
    "WiFi": ["wifi", "wi-fi", "ssid", "wireless", "band", "wpa"],
    "WAN": ["wan", "dhcp", "pppoe", "ip address"],
    "System": ["system", "reboot", "restart", "upgrade", "factory"]
}


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_ai_output(name, content):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return path


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


DEFAULT_PRODUCT = "intl_gateway"


def iter_cases(product=None):
    """Iterate over all cases from both JSON (API) and YAML (Web UI) suite files.

    Args:
        product: 产品名称（如 intl_gateway）。如果为 None，扫描全部产品。
    """
    search_dir = CASES_DIR / product if product else CASES_DIR
    if not search_dir.exists():
        return
    for path in search_dir.rglob("*.json"):
        suite = load_json(path)
        for case in suite.get("cases", []):
            yield path, suite, case
    for path in search_dir.rglob("*.yaml"):
        suite = load_yaml(path)
        for case in suite.get("cases", []):
            yield path, suite, case


def latest_report_dir():
    dirs = [path for path in REPORTS_DIR.glob("*") if path.is_dir() and (path / "result.json").exists()]
    if not dirs:
        raise SystemExit("No reports found. Run a suite first.")
    return max(dirs, key=lambda path: path.stat().st_mtime)


def infer_modules(text):
    lower = text.lower()
    modules = []
    for module, keywords in MODULE_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            modules.append(module)
    return modules or ["Login", "Status", "WiFi", "WAN", "System"]


def case_matches_modules(case, modules):
    if case.get("module") in modules:
        return True
    tags = " ".join(case.get("tags", [])).lower()
    return any(module.lower() in tags for module in modules)


def command_run_suite(args):
    cmd = [
        sys.executable,
        str(ROOT / "runner" / "run_suite.py"),
        "--suite",
        args.suite,
        "--profile",
        args.profile
    ]
    return subprocess.call(cmd, cwd=str(ROOT.parent))


def command_run_web_suite(args):
    """Run Web UI test suite via Playwright."""
    cmd = [
        sys.executable,
        str(ROOT / "runner" / "run_web_suite.py"),
        "--suite",
        args.suite,
        "--profile",
        args.profile
    ]
    return subprocess.call(cmd, cwd=str(ROOT))


def command_generate_cases(args):
    requirement = Path(args.requirement)
    text = read_text(requirement)
    modules = [args.module] if args.module else infer_modules(text)
    generated = []

    if "LAN" in modules:
        generated.extend([
            {
                "id": "TC-API-LAN-001",
                "title": "LAN configuration can be queried",
                "module": "LAN",
                "priority": "P1",
                "tags": ["generated", "lan", "status"],
                "steps": [
                    {"action": "api.login"},
                    {"action": "api.get_lan", "expect": {"status_code": 200}}
                ]
            },
            {
                "id": "TC-API-LAN-002",
                "title": "LAN DHCP pool rejects invalid range",
                "module": "LAN",
                "priority": "P1",
                "tags": ["generated", "lan", "boundary"],
                "steps": [
                    {"action": "api.login"},
                    {
                        "action": "api.set_lan",
                        "params": {"pool_start": "192.168.1.200", "pool_end": "192.168.1.100"},
                        "expect": {"status_code": 400}
                    }
                ]
            }
        ])

    if "WiFi" in modules:
        generated.extend([
            {
                "id": "TC-API-WIFI-004",
                "title": "Wi-Fi setting response includes applied flag",
                "module": "WiFi",
                "priority": "P1",
                "tags": ["generated", "wifi", "contract"],
                "steps": [
                    {"action": "api.login"},
                    {
                        "action": "api.set_wifi",
                        "params": {"ssid": "AutoTest_24G", "password": "Test123456", "band": "2.4G"},
                        "expect": {"status_code": 200, "json.applied": True}
                    }
                ]
            }
        ])

    content = [
        "# QCoder Generate Cases Result",
        "",
        f"- Requirement: `{requirement}`",
        f"- Inferred modules: {', '.join(modules)}",
        f"- Generated cases: {len(generated)}",
        "",
        "## Suggested Cases",
        "",
        "```json",
        json.dumps({"cases": generated}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Review Notes",
        "",
        "- Review action names before adding generated cases to `cases/`.",
        "- Add missing runner keywords and profile API paths if a generated action is not supported.",
    ]
    path = write_ai_output("generate_cases_result.md", "\n".join(content))
    print(f"Generated case suggestions: {path}")
    return 0


def command_generate_web_cases(args):
    """Generate Web UI YAML test case suggestions from page requirements."""
    requirement = Path(args.requirement)
    text = read_text(requirement)
    modules = [args.module] if args.module else infer_modules(text)
    generated = []

    if "Login" in modules:
        generated.append({
            "id": "TC-WEB-LOGIN-GEN",
            "title": "Login page validates credentials",
            "module": "Login",
            "priority": "P0",
            "tags": ["generated", "auth"],
            "steps": [
                {"action": "web.navigate", "params": {"page": "login"}},
                {"action": "web.login", "params": {"username": "admin", "password": "admin123"}},
                {"action": "web.assert_visible", "params": {"selector_key": "dashboard_container", "page": "status"}}
            ]
        })

    if "WiFi" in modules:
        generated.append({
            "id": "TC-WEB-WIFI-GEN",
            "title": "Wi-Fi page saves valid configuration",
            "module": "WiFi",
            "priority": "P1",
            "tags": ["generated", "wifi", "config"],
            "steps": [
                {"action": "web.navigate", "params": {"page": "login"}},
                {"action": "web.login", "params": {"username": "admin", "password": "admin123"}},
                {"action": "web.navigate", "params": {"page": "wifi"}},
                {"action": "web.fill", "params": {"selector_key": "ssid_input", "value": "GeneratedSSID"}},
                {"action": "web.fill", "params": {"selector_key": "password_input", "value": "Generated123"}},
                {"action": "web.click", "params": {"selector_key": "save_button"}},
                {"action": "web.assert_visible", "params": {"selector_key": "success_message"}}
            ]
        })

    yaml_cases = yaml.dump({"cases": generated}, default_flow_style=False, allow_unicode=True, sort_keys=False)
    content = [
        "# QCoder Generate Web UI Cases Result",
        "",
        f"- Requirement: `{requirement}`",
        f"- Inferred modules: {', '.join(modules)}",
        f"- Generated cases: {len(generated)}",
        "",
        "## Suggested YAML Cases",
        "",
        "``yaml",
        yaml_cases.strip(),
        "```",
        "",
        "## Review Notes",
        "",
        "- Ensure selector_key values exist in `profiles/intl_baseline_web.yaml`.",
        "- Add missing Page Object methods if generated actions are not supported.",
        "- Review each case before adding to `cases/` directory."
    ]
    path = write_ai_output("generate_web_cases_result.md", "\n".join(content))
    print(f"Generated Web UI case suggestions: {path}")
    return 0


def _detect_input_format(text):
    """检测变更输入的格式：structured / git_diff / natural_language."""
    if "diff --git" in text or text.strip().startswith("--- ") or "+++ " in text:
        return "git_diff"
    if "## 变更" in text or "| 旧值 | 新值 |" in text or "### 描述" in text:
        return "structured"
    if len(text.strip()) < 200 and "\n" not in text.strip():
        return "natural_language"
    return "structured"


def _extract_selector_changes_from_diff(text):
    """从 git diff 中提取 selector 变化（id/class 属性）。"""
    changes = []
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("-") or line.startswith("+")):
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue
        # 提取 id 属性变化
        id_match = re.search(r'id="([^"]+)"', line[1:])
        class_match = re.search(r'class="([^"]+)"', line[1:])
        if id_match or class_match:
            prefix = "removed" if line.startswith("-") else "added"
            changes.append({"prefix": prefix, "line": line[1:].strip(), "id": id_match, "class": class_match})
    return changes


def _extract_files_from_diff(text):
    """从 git diff 中提取受影响的文件路径。"""
    files = []
    for line in text.splitlines():
        m = re.match(r'^(?:diff --git a/|\+\+\+ b/)(.+)', line)
        if m:
            files.append(m.group(1).strip())
    return files


def _infer_modules_from_files(files):
    """根据文件路径推断受影响模块。"""
    text = " ".join(files).lower()
    return infer_modules(text)


# 变更关键词→建议规则映射表
# AI 会根据 changelog 中出现的关键词自动匹配建议
CHANGE_RULES = [
    {
        "keywords": ["password", "密码", "passphrase"],
        "patterns": [r"(?:8|eight).*(?:10|ten)", r"10-63", r"最小.*10"],
        "suggestions": [
            "Update Wi-Fi password boundary cases from 8-63 to 10-63.",
            "Add a 9-character password rejection case.",
        ],
    },
    {
        "keywords": ["band", "频段", "2.4g", "5g"],
        "patterns": [r"band", r"频段"],
        "suggestions": [
            "Add `band` to Wi-Fi set request payload and add default-band compatibility case.",
        ],
    },
    {
        "keywords": ["applied", "生效"],
        "patterns": [r"applied", r"生效"],
        "suggestions": [
            "Add API contract assertion for response field `applied: true`.",
        ],
    },
    {
        "keywords": ["reboot", "重启", "restart"],
        "patterns": [r"reboot", r"重启"],
        "suggestions": [
            "Verify reboot flow: button → confirm → message → device recovery.",
        ],
    },
    {
        "keywords": ["wan", "pppoe", "dhcp", "wan mode"],
        "patterns": [r"pppoe", r"wan.*mode", r"wan.*type"],
        "suggestions": [
            "Update WAN mode switching cases (DHCP/PPPoE/static).",
        ],
    },
    {
        "keywords": ["upgrade", "firmware", "固件", "升级"],
        "patterns": [r"upgrade", r"firmware", r"固件"],
        "suggestions": [
            "Add firmware upgrade flow case: upload → progress → reboot → version check.",
            "Add post-upgrade configuration persistence assertion (keep or reset per product policy).",
        ],
    },
    {
        "keywords": ["lock", "锁定", "lockout", "暴力破解"],
        "patterns": [r"lock", r"锁定"],
        "suggestions": [
            "Add login lockout state-machine cases: N failures → locked → correct password rejected while locked → unlock after timeout.",
        ],
    },
    {
        "keywords": ["factory", "恢复出厂", "reset", "出厂"],
        "patterns": [r"factory", r"恢复出厂", r"reset"],
        "suggestions": [
            "Add factory-reset consistency cases: modified config → reset → all values back to defaults + re-login required.",
        ],
    },
    {
        "keywords": ["session", "会话", "timeout", "超时"],
        "patterns": [r"session", r"会话", r"timeout", r"超时"],
        "suggestions": [
            "Add session management cases: logout then access protected page → redirect to login; session expiry → re-authenticate.",
        ],
    },
    {
        "keywords": ["language", "语言", "i18n", "多语言"],
        "patterns": [r"language", r"i18n", r"多语言"],
        "suggestions": [
            "Add language switching cases: switch language → texts change, config preserved, switch back → normal.",
            "Check text-based assertions (web.assert_text) for i18n compatibility; prefer structural selectors.",
        ],
    },
]


def _parse_changelog(text):
    """解析 changelog 文本，提取变更条目和关键词。

    支持的输入格式（自动识别，无需固定模板）：
    - 版本 release notes（如 "## V2.1.0\\n- 修改 Wi-Fi 密码规则..."）
    - 提交记录（如 "feat: add band select / fix: password min length"）
    - 变更说明 markdown（用 _template.md 填写的结构化内容）
    - 纯自然语言描述
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    entries = []

    for line in lines:
        # 跳过 markdown 标题装饰行（---, |---|---| 等）
        if re.match(r'^[-|]+$', line):
            continue
        # 去掉 markdown 列表前缀和 commit type 前缀
        clean = re.sub(r'^(?:\d+[.)]|[-*+]|feat|fix|refactor|chore|docs|test)[:\]]*\s*', '', line, flags=re.IGNORECASE)
        clean = clean.strip()
        if clean:
            entries.append(clean)

    return entries


def _match_change_rules(text):
    """根据 changelog 文本自动匹配变更规则，返回建议列表。"""
    lower = text.lower()
    suggestions = []

    for rule in CHANGE_RULES:
        # 先检查是否有任何关键词出现
        if not any(kw.lower() in lower for kw in rule["keywords"]):
            continue
        # 再检查是否有匹配的 pattern
        for pattern in rule["patterns"]:
            if re.search(pattern, lower):
                suggestions.extend(rule["suggestions"])
                break
        # 即使没有 pattern 匹配，关键词命中也给出基本建议
        else:
            suggestions.append(f"Detected change related to: {', '.join(rule['keywords'][:3])}. Review impacted cases manually.")

    return suggestions


def command_update_cases(args):
    change = Path(args.change)
    product = getattr(args, "product", None) or DEFAULT_PRODUCT
    text = read_text(change)
    entries = _parse_changelog(text)
    modules = infer_modules(text)
    suggestions = _match_change_rules(text)

    impacted = []
    for path, suite, case in iter_cases(product):
        if case_matches_modules(case, modules):
            impacted.append({
                "id": case["id"],
                "title": case["title"],
                "module": case["module"],
                "file": str(path.relative_to(ROOT))
            })

    # 置信度：条目越多 + 有具体建议 = 置信度越高
    if len(entries) >= 3 and suggestions:
        confidence = "高"
    elif len(entries) >= 1:
        confidence = "中"
    else:
        confidence = "低"

    content = [
        "# QCoder Update Cases By Change Result",
        "",
        f"- Change file: `{change}`",
        f"- Parsed changelog entries: {len(entries)}",
        f"- Analysis confidence: `{confidence}`",
        f"- Impacted modules: {', '.join(modules)}",
        f"- Impacted cases: {len(impacted)}",
        "",
        "## Parsed Changelog Entries",
        "",
    ]
    content.extend([f"{i+1}. {e}" for i, e in enumerate(entries)] or ["(no parseable entries)"])
    content.extend(["", "## Impacted Cases", ""])
    content.extend([f"- `{item['id']}` {item['title']} ({item['file']})" for item in impacted])
    content.extend(["", "## Suggested Updates", ""])
    content.extend([f"- {item}" for item in suggestions] or ["- No concrete update inferred. Manual review required."])

    if confidence == "低":
        content.extend(["", "## ⚠️ Low Confidence", "", "Input lacks specific details. Consider providing a more detailed changelog or filling `changes/_template.md`."])

    content.extend(["", "## Recommended Regression", "", "- Run `smoke` first.", f"- Run module regression for: {', '.join(modules)}."])
    path = write_ai_output("update_cases_by_change_result.md", "\n".join(content))
    print(f"Change impact analysis written: {path}")
    return 0


def command_select_regression(args):
    change = Path(args.change)
    product = getattr(args, "product", None) or DEFAULT_PRODUCT
    modules = infer_modules(read_text(change))
    selected = []

    for path, suite, case in iter_cases(product):
        is_smoke = "smoke" in path.parts
        is_impacted = case_matches_modules(case, modules)
        is_p0 = case.get("priority") == "P0"
        if is_smoke or is_impacted or is_p0:
            reason = "smoke baseline" if is_smoke else "impacted module or P0 coverage"
            selected.append({"id": case["id"], "reason": reason})

    version = args.version or "DEMO"
    suite = {
        "suite_id": f"REG-{version}-WEB-API",
        "version": version,
        "change": str(change),
        "cases": selected
    }
    suite_path = ROOT / "suites" / "generated" / f"REG-{version}-WEB-API.json"
    write_json(suite_path, suite)
    content = [
        "# QCoder Regression Selection Result",
        "",
        f"- Version: `{version}`",
        f"- Change: `{change}`",
        f"- Selected cases: {len(selected)}",
        f"- Suite file: `{suite_path.relative_to(ROOT)}`",
        "",
        "## Cases",
        ""
    ]
    content.extend([f"- `{item['id']}`: {item['reason']}" for item in selected])
    path = write_ai_output("select_regression_result.md", "\n".join(content))
    print(f"Regression suite written: {suite_path}")
    print(f"Selection analysis written: {path}")
    return 0


def classify_failure(case, step):
    failures = " ".join(step.get("failures", [])).lower()
    response = step.get("response", {})
    action = step.get("action", "")

    # Web UI failure classification
    if action.startswith("web."):
        if "timeout" in failures or "page_load" in failures:
            return "page_load_timeout"
        if "not interactable" in failures or "not clickable" in failures:
            return "element_not_interactable"
        if "selector" in failures or "not found" in failures or "keyerror" in failures:
            return "selector_changed"
        if "unknown action" in failures:
            return "script_bug"
        if "expected" in failures and "got" in failures:
            return "product_bug"
        if failures:
            return "selector_changed"
        return "unknown"

    # API failure classification
    if response.get("status_code") == 0:
        return "environment_issue"
    if "missing" in failures:
        return "api_contract_changed"
    if "status_code" in failures and "401" in failures:
        return "test_data_issue"
    if "unknown action" in json.dumps(response).lower():
        return "script_bug"
    if "software_version" in failures:
        return "requirement_changed"
    if failures:
        return "product_bug"
    return "unknown"


def command_analyze_failure(args):
    report_dir = latest_report_dir() if args.latest else Path(args.run)
    report = load_json(report_dir / "result.json")
    failed_cases = [case for case in report["cases"] if case["status"] == "fail"]
    classifications = []
    content = [
        "# QCoder Failure Analysis Result",
        "",
        f"- Report: `{report_dir}`",
        f"- Suite: `{report['suite_id']}`",
        f"- Failed cases: {len(failed_cases)}",
        ""
    ]

    is_web = report.get("type") == "web"

    if not failed_cases:
        content.extend(["## Result", "", "No failed cases found. No failure analysis is required."])
    else:
        content.extend(["## Failures", ""])
        for case in failed_cases:
            failed_step = next((step for step in case["steps"] if step["status"] == "fail"), None)
            category = classify_failure(case, failed_step)
            classifications.append({"case_id": case["id"], "category": category, "step": failed_step["action"]})
            block = [
                f"### `{case['id']}` {case['title']}",
                "",
                f"- Failed step: `{failed_step['action']}`",
                f"- Category: `{category}`",
                f"- Evidence: {'; '.join(failed_step.get('failures', []))}",
            ]
            if is_web and case.get("screenshot"):
                block.append(f"- Screenshot: `{case['screenshot']}`")
            if is_web:
                block.append("- Suggested action: Review selector profile, page structure, and element visibility.")
            else:
                block.append("- Suggested action: Review expected value, API contract, environment availability, and test data.")
            block.extend(["- Rerun: yes, after fixing the identified cause.", ""])
            content.extend(block)

    write_json(report_dir / "failure_classification.json", {"classifications": classifications})
    path = write_ai_output("analyze_failure_result.md", "\n".join(content))
    print(f"Failure analysis written: {path}")
    return 0


def command_analyze_web_failure(args):
    """Analyze Web UI execution report with screenshot and selector evidence."""
    report_dir = latest_report_dir() if args.latest else Path(args.run)
    report = load_json(report_dir / "result.json")
    if report.get("type") != "web":
        print(f"Warning: report `{report_dir}` is not a Web UI report (type={report.get('type')}).")
    failed_cases = [case for case in report["cases"] if case["status"] == "fail"]
    classifications = []
    content = [
        "# QCoder Web UI Failure Analysis Result",
        "",
        f"- Report: `{report_dir}`",
        f"- Suite: `{report['suite_id']}`",
        f"- Profile: `{report.get('profile', 'N/A')}`",
        f"- Failed cases: {len(failed_cases)}",
        ""
    ]

    if not failed_cases:
        content.extend(["## Result", "", "No failed cases found. No failure analysis is required."])
    else:
        content.extend(["## Failures", ""])
        for case in failed_cases:
            failed_step = next((step for step in case["steps"] if step["status"] == "fail"), None)
            category = classify_failure(case, failed_step)
            classifications.append({"case_id": case["id"], "category": category, "step": failed_step["action"]})
            block = [
                f"### `{case['id']}` {case['title']}",
                "",
                f"- Failed step: `{failed_step['action']}`",
                f"- Category: `{category}`",
                f"- Evidence: {'; '.join(failed_step.get('failures', []))}",
            ]
            if case.get("screenshot"):
                block.append(f"- Screenshot: `{case['screenshot']}`")
            block.append("- Suggested action: Review selector profile, page structure, and element visibility.")
            block.extend(["- Rerun: yes, after fixing the identified cause.", ""])
            content.extend(block)

    write_json(report_dir / "failure_classification.json", {"classifications": classifications})
    path = write_ai_output("analyze_web_failure_result.md", "\n".join(content))
    print(f"Web failure analysis written: {path}")
    return 0


def command_coverage_review(args):
    scope = Path(args.scope)
    product = getattr(args, "product", None) or DEFAULT_PRODUCT
    modules = ["Login", "Status", "WiFi", "WAN", "System"]
    stats = {module: {"total": 0, "p0": 0, "p1": 0, "normal": 0, "negative": 0, "boundary": 0, "api": 0, "web": 0} for module in modules}
    for path, _, case in iter_cases(product):
        module = case.get("module")
        if module not in stats:
            stats[module] = {"total": 0, "p0": 0, "p1": 0, "normal": 0, "negative": 0, "boundary": 0, "api": 0, "web": 0}
        tags = set(case.get("tags", []))
        stats[module]["total"] += 1
        if path.suffix == ".json":
            stats[module]["api"] += 1
        elif path.suffix == ".yaml":
            stats[module]["web"] += 1
        if case.get("priority") == "P0":
            stats[module]["p0"] += 1
        if case.get("priority") == "P1":
            stats[module]["p1"] += 1
        if "negative" in tags:
            stats[module]["negative"] += 1
        elif "boundary" in tags:
            stats[module]["boundary"] += 1
        else:
            stats[module]["normal"] += 1

    gaps = []
    for module in modules:
        if stats[module]["total"] == 0:
            gaps.append(f"{module}: no automated cases.")
        if stats[module]["negative"] == 0:
            gaps.append(f"{module}: missing negative/unauthorized coverage.")
        if module in ["WiFi", "WAN"] and stats[module]["boundary"] == 0:
            gaps.append(f"{module}: missing boundary coverage.")

    content = [
        "# QCoder Coverage Review Result",
        "",
        f"- Scope: `{scope}`",
        "",
        "## Coverage Matrix",
        "",
        "| Module | Total | API | Web | P0 | P1 | Normal | Negative | Boundary |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    ]
    for module, item in stats.items():
        content.append(f"| {module} | {item['total']} | {item['api']} | {item['web']} | {item['p0']} | {item['p1']} | {item['normal']} | {item['negative']} | {item['boundary']} |")
    content.extend(["", "## Gaps", ""])
    content.extend([f"- {gap}" for gap in gaps] or ["- No obvious gap found in the current MVP scope."])
    path = write_ai_output("coverage_review_result.md", "\n".join(content))
    print(f"Coverage review written: {path}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="QCoder Web AutoTest Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run-suite")
    run.add_argument("--suite", choices=["smoke", "regression"], required=True)
    run.add_argument("--profile", default="intl_baseline")
    run.set_defaults(func=command_run_suite)

    web_run = sub.add_parser("run-web-suite")
    web_run.add_argument("--suite", choices=["smoke", "regression"], required=True)
    web_run.add_argument("--profile", default="intl_baseline_web")
    web_run.set_defaults(func=command_run_web_suite)

    gen = sub.add_parser("generate-cases")
    gen.add_argument("--requirement", required=True)
    gen.add_argument("--module")
    gen.set_defaults(func=command_generate_cases)

    web_gen = sub.add_parser("generate-web-cases")
    web_gen.add_argument("--requirement", required=True)
    web_gen.add_argument("--module")
    web_gen.set_defaults(func=command_generate_web_cases)

    upd = sub.add_parser("update-cases")
    upd.add_argument("--change", required=True)
    upd.add_argument("--product", default=DEFAULT_PRODUCT, help="产品名称（如 intl_gateway）")
    upd.set_defaults(func=command_update_cases)

    sel = sub.add_parser("select-regression")
    sel.add_argument("--change", required=True)
    sel.add_argument("--version")
    sel.add_argument("--product", default=DEFAULT_PRODUCT)
    sel.set_defaults(func=command_select_regression)

    fail = sub.add_parser("analyze-failure")
    source = fail.add_mutually_exclusive_group(required=True)
    source.add_argument("--latest", action="store_true")
    source.add_argument("--run")
    fail.set_defaults(func=command_analyze_failure)

    web_fail = sub.add_parser("analyze-web-failure")
    web_source = web_fail.add_mutually_exclusive_group(required=True)
    web_source.add_argument("--latest", action="store_true")
    web_source.add_argument("--run")
    web_fail.set_defaults(func=command_analyze_web_failure)

    cov = sub.add_parser("coverage-review")
    cov.add_argument("--scope", default=str(ROOT / "requirements" / "intl_baseline_web_scope.md"))
    cov.add_argument("--product", default=DEFAULT_PRODUCT)
    cov.set_defaults(func=command_coverage_review)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

