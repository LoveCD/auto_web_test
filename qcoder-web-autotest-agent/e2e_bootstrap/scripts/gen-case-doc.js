/**
 * gen-case-doc.js — 按 web-playwright-e2e-bootstrap 模板生成用例文档 / 执行报告
 *
 * 用途：将 qcoder-web-autotest 套件 JSON（operators 下 cases 目录内的 *.json）转换为
 *       e2e-bootstrap 模板格式的 Word 文档。文档与 Playwright 执行报告
 *       （self-test-report-reporter.js）共用同一 DOCX 模板，版式完全一致。
 *
 * 三种模式:
 *   1) 设计文档（默认）：套件 JSON → 用例设计文档，结果/结论列填"待执行"。
 *   2) 执行报告（--result）：读取 run_suite.py 输出的 result.json，匹配套件 JSON
 *      合并渲染，结果/结论/截图从执行结果填充，汇总区自动统计。
 *   3) 批量（--all）：扫描 operators 下各运营商 cases 目录的 *.json（排除 generated/），逐个生成设计文档。
 *
 * 用法:
 *   node scripts/gen-case-doc.js <suite.json> [选项]                     # 单套件设计文档
 *   node scripts/gen-case-doc.js --all [选项]                            # 批量设计文档
 *   node scripts/gen-case-doc.js --result <result.json> [选项]           # 执行报告
 *
 * 选项:
 *   --qcoder-suite <path>   套件 JSON 路径（也可作为首个位置参数传入）
 *   --all                   批量模式：生成 operators 下各运营商 cases 目录的 *.json（排除 generated/）
 *   --result <path>         执行报告模式：读取 result.json（run_suite.py 输出）
 *   --qcoder-root <dir>     工程根目录（默认 scripts/ 的上级上级，即 qcoder-web-autotest-agent）
 *   --topic <主题>          报告主题（默认取 suite_id / suite）
 *   --project-code <代号>   项目代号（默认 YYYYMMDD）
 *   --template <path>       DOCX 模板路径（默认 ./templates/test-report-template.docx）
 *   --out <dir>            输出目录（默认 ./self-test-reports）
 *   --base-url <url>        目标地址（默认读 .env 的 E2E_BASE_URL）
 *   --preconditions <文本>  预置条件，分号或换行分隔（设计文档模式）
 */
const fs = require("fs");
const path = require("path");
const Rep = require("../reporters/self-test-report-reporter.js");

const {
  renderTemplateDocx,
  toNumberedText,
  buildCaseOrderedValuesByTemplate,
  formatCaseDisplayName,
  safeName,
  nowParts,
  dateForView,
  detectCaseFieldCountFromTemplate
} = Rep;

// ---------- 动作 → 中文标签（步骤渲染人性化） ----------
const ACTION_LABELS = {
  "real.navigate": "导航",
  "real.login": "登录",
  "real.logout": "退出登录",
  "real.fill": "填写输入框",
  "real.click": "点击元素",
  "real.click_button": "点击按钮",
  "real.ensure_switch": "设置开关",
  "real.assert_switch_checked": "断言开关状态",
  "real.wait": "等待",
  "real.screenshot": "截图",
  "real.assert_input_value": "断言输入框值",
  "real.assert_login_error": "断言登录失败",
  "real.assert_element_hidden": "断言元素隐藏",
  "real.assert_rendered": "断言页面渲染",
  "real.navigate_or_assert": "导航并断言",
  "navigate": "导航",
  "login": "登录",
  "logout": "退出登录",
  "fill": "填写输入框",
  "click": "点击元素",
  "click_button": "点击按钮",
  "ensure_switch": "设置开关",
  "wait": "等待",
  "screenshot": "截图",
  "assert_input_value": "断言输入框值",
  "assert_login_error": "断言登录失败",
  "assert_element_hidden": "断言元素隐藏",
  "assert_rendered": "断言页面渲染",
  "navigate_or_assert": "导航并断言"
};

function actionLabel(action) {
  const key = String(action || "");
  if (ACTION_LABELS[key]) {
    return ACTION_LABELS[key];
  }
  const base = key.replace(/^real\./, "");
  return ACTION_LABELS[base] || key;
}

// ---------- 参数解析 ----------
function parseArgs(argv) {
  const args = { positional: [], flags: {} };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = argv[i + 1];
      if (next && !next.startsWith("--")) {
        args.flags[key] = next;
        i += 1;
      } else {
        args.flags[key] = true;
      }
    } else {
      args.positional.push(arg);
    }
  }
  return args;
}

// ---------- qcoder 套件 JSON → 模板 slot ----------
function paramToText(params = {}) {
  const parts = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") {
      continue;
    }
    parts.push(`${k}=${typeof v === "object" ? JSON.stringify(v) : v}`);
  }
  return parts.join("，");
}

function expectToLines(expect = {}) {
  const lines = [];
  for (const [k, v] of Object.entries(expect || {})) {
    if (v === undefined || v === null) {
      continue;
    }
    const text = Array.isArray(v)
      ? v.join(" | ")
      : typeof v === "object"
        ? JSON.stringify(v)
        : String(v);
    lines.push(`断言[${k}]：${text}`);
  }
  return lines;
}

function stepToText(step) {
  const action = String(step.action || "");
  const params = step.params || {};
  const desc = params.desc || params.description || "";
  const extras = paramToText({ ...params, desc: undefined, description: undefined });
  const label = actionLabel(action);
  let text = desc ? `${label} ${desc}` : `${label}${params.path ? ` ${params.path}` : ""}`;
  if (extras) {
    text += `（${extras}）`;
  }
  return text;
}

/** 套件用例 → 模板 slot（设计文档模式，结果/结论=待执行） */
function suiteToCaseSlots(suite, opts) {
  const cases = Array.isArray(suite.cases) ? suite.cases : [];
  const operator = suite.operator || "";
  const env = suite.env || "";
  const envLines = [`运营商: ${operator || "-"}`, `环境: ${env || "-"}`];
  if (opts.baseUrl) {
    envLines.push(`目标地址: ${opts.baseUrl}`);
  }
  envLines.push("待执行时配置 .env 环境变量");
  const envText = toNumberedText(envLines);

  const preconditions = toNumberedText(
    String(
      opts.preconditions ||
        "已完成 e2e 依赖安装并可执行 Playwright 测试;已在 .env 中配置 E2E_BASE_URL、账号及必要参数;测试设备/环境网络可达，登录页面可访问"
    )
      .split(/[;\n]/)
      .map((s) => s.trim())
      .filter(Boolean)
  );

  return cases.map((c, idx) => {
    const id = c.id || `CASE-${idx + 1}`;
    const title = c.title || c.testCase || id;
    const purposeText = `${id} ${title}`;
    const steps = (c.steps || []).map(stepToText);
    const expected = [];
    (c.steps || []).forEach((s) => {
      expected.push(...expectToLines(s.expect));
    });
    if (!expected.length) {
      expected.push("页面无异常，行为符合预期");
    }

    const remarks = [`优先级: ${c.priority || "-"}`];
    if (typeof c.auto_login === "boolean") {
      remarks.push(`自动登录: ${c.auto_login ? "是" : "否"}`);
    }
    if (c.module) {
      remarks.push(`模块: ${c.module}`);
    }

    return {
      // name 用于"测试项N"标题（appendExtraCaseTables 克隆块依赖 slot.name）
      name: purposeText,
      testType: c.module || "通用",
      purpose: purposeText,
      preconditions,
      testBrowser: "-",
      env: envText,
      steps: toNumberedText(steps.length ? steps : ["按用例定义执行页面交互流程"]),
      expected: toNumberedText(expected),
      result: "实际结果：待执行",
      conclusion: "待执行",
      remarks: remarks.join("\n")
    };
  });
}

/** 执行结果 + 套件 → 模板 slot（执行报告模式） */
function resultToCaseSlots(result, suite, opts) {
  const resultCases = Array.isArray(result.cases) ? result.cases : [];
  const suiteCases = Array.isArray(suite && suite.cases) ? suite.cases : [];
  const byId = new Map(suiteCases.map((c) => [c.id, c]));
  const operator = suite && suite.operator ? suite.operator : result.operator || "";
  const env = suite && suite.env ? suite.env : result.env || "";
  const envLines = [
    `运营商: ${operator || "-"}`,
    `环境: ${env || "-"}`,
    `浏览器: ${result.browser || "chromium"}`,
    `运行ID: ${result.run_id || "-"}`,
    `执行时间: ${result.generated_at || "-"}`,
    `耗时: ${result.summary && result.summary.duration_seconds != null ? `${result.summary.duration_seconds}s` : "-"}`
  ];
  const envText = toNumberedText(envLines);

  return resultCases.map((rc, idx) => {
    const sc = byId.get(rc.id);
    const id = rc.id || `CASE-${idx + 1}`;
    const title = rc.title || (sc && sc.title) || id;
    const purposeText = `${id} ${title}`;
    const status = rc.status || "fail";

    // 步骤：优先套件 JSON（含 params/expect），fallback 执行结果
    let steps;
    let expected;
    if (sc && Array.isArray(sc.steps) && sc.steps.length) {
      steps = sc.steps.map(stepToText);
      expected = [];
      sc.steps.forEach((s) => {
        expected.push(...expectToLines(s.expect));
      });
    } else {
      steps = (rc.steps || []).map((s) => {
        const label = actionLabel(s.action);
        const detail = s.detail ? `：${s.detail}` : "";
        return `${label}${detail}`;
      });
      expected = ["页面无异常，行为符合预期"];
    }
    if (!expected.length) {
      expected.push("页面无异常，行为符合预期");
    }

    // 结果文本：从失败步骤提取原因
    const failSteps = (rc.steps || []).filter((s) => s.status === "fail");
    let resultText;
    if (status === "pass") {
      resultText = `实际结果：通过（${(rc.steps || []).length} 个步骤全部通过）`;
    } else if (failSteps.length) {
      const first = failSteps[0];
      const reason = (first.failures && first.failures[0]) || first.detail || "未知错误";
      resultText = `实际结果：失败（步骤「${actionLabel(first.action)}」失败，原因：${reason}）`;
    } else {
      resultText = `实际结果：失败`;
    }

    // 备注：设计信息 + 执行状态
    const remarks = [`优先级: ${(sc && sc.priority) || rc.priority || "-"}`];
    if (sc && typeof sc.auto_login === "boolean") {
      remarks.push(`自动登录: ${sc.auto_login ? "是" : "否"}`);
    }
    if (sc && sc.module) {
      remarks.push(`模块: ${sc.module}`);
    }
    remarks.push(`执行状态: ${status === "pass" ? "通过" : "失败"}`);

    return {
      name: purposeText,
      testType: (sc && sc.module) || rc.module || "通用",
      purpose: purposeText,
      preconditions: toNumberedText(
        String(
          "已完成 e2e 依赖安装并可执行 Playwright 测试;已在 .env 中配置 E2E_BASE_URL、账号及必要参数;测试设备/环境网络可达，登录页面可访问"
        )
          .split(/[;\n]/)
          .map((s) => s.trim())
          .filter(Boolean)
      ),
      testBrowser: result.browser || "-",
      env: envText,
      steps: toNumberedText(steps.length ? steps : ["按用例定义执行页面交互流程"]),
      expected: toNumberedText(expected),
      result: resultText,
      conclusion: status === "pass" ? "通过" : "失败",
      remarks: remarks.join("\n")
    };
  });
}

/** 从执行结果收集截图（测试项序号 → [{path, ext}]） */
function collectScreenshots(result, resultPath) {
  const shots = {};
  const baseDir = path.dirname(path.resolve(resultPath));
  (result.cases || []).forEach((rc, idx) => {
    const candidates = [];
    (rc.steps || []).forEach((s) => {
      const act = String(s.action || "");
      if (
        (act === "screenshot" || act.endsWith(".screenshot") || act === "real.screenshot") &&
        s.detail &&
        /\.(png|jpe?g|gif)$/i.test(String(s.detail))
      ) {
        candidates.push(String(s.detail));
      }
    });
    if (rc.screenshot) {
      candidates.push(String(rc.screenshot));
    }
    const resolved = [];
    candidates.forEach((p) => {
      const abs = path.isAbsolute(p) ? p : path.resolve(baseDir, p);
      if (fs.existsSync(abs)) {
        resolved.push({ path: abs, ext: path.extname(abs) || ".png" });
      }
    });
    if (resolved.length) {
      shots[String(idx + 1)] = resolved;
    }
  });
  return shots;
}

/** 批量模式：列出 operators 下各运营商 cases 目录的 *.json（排除 generated/） */
function listSuiteFiles(qcoderRoot) {
  const out = [];
  const opsDir = path.join(qcoderRoot, "operators");
  if (!fs.existsSync(opsDir)) {
    return out;
  }
  for (const op of fs.readdirSync(opsDir)) {
    const casesDir = path.join(opsDir, op, "cases");
    if (!fs.statSync(path.join(opsDir, op)).isDirectory() || !fs.existsSync(casesDir)) {
      continue;
    }
    for (const f of fs.readdirSync(casesDir)) {
      if (!f.endsWith(".json")) {
        continue;
      }
      const full = path.join(casesDir, f);
      const rel = path.relative(path.join(opsDir, op), full);
      if (rel.startsWith("generated")) {
        continue; // 跳过 NL 生成器临时产物
      }
      out.push(full);
    }
  }
  return out.sort();
}

/** 生成单个设计文档 */
async function generateDoc(suitePath, flags, qcoderRoot) {
  const suite = JSON.parse(fs.readFileSync(path.resolve(suitePath), "utf8"));
  const topic = flags.topic || suite.suite_id || "Web UI自动化用例";
  const projectCode = flags["project-code"] || dateForView().replace(/-/g, "");
  const templatePath = path.resolve(flags.template || "./templates/test-report-template.docx");
  const outDir = path.resolve(flags.out || "self-test-reports");
  const baseUrl = flags["base-url"] || process.env.E2E_BASE_URL || "";

  const slots = suiteToCaseSlots(suite, {
    baseUrl,
    preconditions: flags.preconditions || ""
  });
  if (!slots.length) {
    throw new Error(`套件中没有用例（${suitePath} cases 为空）`);
  }

  const caseFieldCount = await detectCaseFieldCountFromTemplate(templatePath);
  const ordered = buildOrderedValues(slots, caseFieldCount);
  const summaryValues = [
    String(slots.length), "0", "0", "0", "0", "0", "待执行"
  ];
  const emptyOrdered = [...ordered, ...summaryValues];

  const parts = nowParts();
  const fileBase = `用例文档-${safeName(topic)}-${parts.year}${parts.month}${parts.day}-${parts.hour}${parts.minute}${parts.second}`;
  const outPath = path.join(outDir, `${fileBase}.docx`);
  fs.mkdirSync(outDir, { recursive: true });

  const case1Name = slots.length >= 1 ? formatCaseDisplayName(1, slots[0].purpose) : "测试项1（无）";
  const case2Name = slots.length >= 2 ? formatCaseDisplayName(2, slots[1].purpose) : "测试项2（无）";
  const extraCaseSlots = slots.slice(2).map((slot, i) => ({
    caseNo: i + 3,
    slot
  }));

  await renderTemplateDocx(
    templatePath,
    outPath,
    {
      xxxxValues: [projectCode, parts.year],
      xxValues: [parts.month, parts.day],
      publishDate: dateForView(),
      changeSummary: `用例设计文档：${topic}（共 ${slots.length} 条，待执行）`,
      case1Name,
      case2Name,
      extraCaseSlots
    },
    emptyOrdered
  );

  console.log(
    `[gen-case-doc] 用例文档生成成功: ${path.relative(process.cwd(), outPath).split(path.sep).join("/")}（${slots.length} 条用例，模板字段 ${caseFieldCount} 字段/条）`
  );
}

/** 生成执行报告（--result 模式） */
async function generateReport(resultPath, flags, qcoderRoot) {
  const absResult = path.resolve(resultPath);
  const result = JSON.parse(fs.readFileSync(absResult, "utf8"));
  const suiteName = flags.suite || result.suite || "";
  const operator = flags.operator || result.operator || "";
  const topic = flags.topic || result.suite_id || `${operator.toUpperCase()}-${suiteName}` || "Web UI自动化测试报告";
  const projectCode = flags["project-code"] || dateForView().replace(/-/g, "");
  const templatePath = path.resolve(flags.template || "./templates/test-report-template.docx");
  const outDir = path.resolve(flags.out || "self-test-reports");

  // 匹配套件 JSON（提供步骤/期望设计数据）
  let suite = null;
  if (suiteName && operator) {
    const suitePath = path.join(qcoderRoot, "operators", operator, "cases", `${suiteName}.json`);
    if (fs.existsSync(suitePath)) {
      suite = JSON.parse(fs.readFileSync(suitePath, "utf8"));
    } else {
      console.warn(`[gen-case-doc] 未找到匹配套件 ${suitePath}，步骤/期望将回退执行结果 detail`);
    }
  }

  const slots = resultToCaseSlots(result, suite, {});
  if (!slots.length) {
    throw new Error("执行结果中没有用例（cases 为空）");
  }

  const caseFieldCount = await detectCaseFieldCountFromTemplate(templatePath);
  const ordered = buildOrderedValues(slots, caseFieldCount);
  const summary = result.summary || {};
  const total = summary.total != null ? summary.total : slots.length;
  const passed = summary.passed != null ? summary.passed : slots.filter((s) => s.conclusion === "通过").length;
  const failed = summary.failed != null ? summary.failed : slots.length - passed;
  const conclusion = failed > 0 ? "失败" : "通过";
  const summaryValues = [String(total), String(passed), String(failed), "0", "0", "0", conclusion];
  const emptyOrdered = [...ordered, ...summaryValues];

  const screenshots = collectScreenshots(result, absResult);

  const parts = nowParts();
  const fileBase = `测试报告-${safeName(topic)}-${parts.year}${parts.month}${parts.day}-${parts.hour}${parts.minute}${parts.second}`;
  const outPath = path.join(outDir, `${fileBase}.docx`);
  fs.mkdirSync(outDir, { recursive: true });

  const case1Name = slots.length >= 1 ? formatCaseDisplayName(1, slots[0].purpose) : "测试项1（无）";
  const case2Name = slots.length >= 2 ? formatCaseDisplayName(2, slots[1].purpose) : "测试项2（无）";
  const extraCaseSlots = slots.slice(2).map((slot, i) => ({
    caseNo: i + 3,
    slot
  }));

  await renderTemplateDocx(
    templatePath,
    outPath,
    {
      xxxxValues: [projectCode, parts.year],
      xxValues: [parts.month, parts.day],
      publishDate: dateForView(),
      changeSummary: `测试执行报告：${topic}（${passed}/${total} 通过，${failed} 失败，耗时 ${summary.duration_seconds != null ? `${summary.duration_seconds}s` : "-"}）`,
      case1Name,
      case2Name,
      extraCaseSlots
    },
    emptyOrdered,
    screenshots
  );

  console.log(
    `[gen-case-doc] 测试报告生成成功: ${path.relative(process.cwd(), outPath).split(path.sep).join("/")}（${slots.length} 条用例，${passed} 通过 / ${failed} 失败，嵌入截图 ${Object.keys(screenshots).length} 项）`
  );
}

function buildOrderedValues(slots, caseFieldCount) {
  return slots.flatMap((slot) => buildCaseOrderedValuesByTemplate(slot, caseFieldCount));
}

async function main() {
  const { positional, flags } = parseArgs(process.argv.slice(2));
  const qcoderRoot = path.resolve(flags["qcoder-root"] || path.resolve(__dirname, "../../"));

  if (flags.all) {
    const files = listSuiteFiles(qcoderRoot);
    if (!files.length) {
      console.error(`[gen-case-doc] 未找到套件 JSON（${path.join(qcoderRoot, "operators", "*", "cases")}）`);
      process.exit(1);
    }
    console.log(`[gen-case-doc] 批量模式：发现 ${files.length} 个套件`);
    let ok = 0;
    for (const f of files) {
      try {
        await generateDoc(f, flags, qcoderRoot);
        ok += 1;
      } catch (err) {
        console.error(`[gen-case-doc] 跳过 ${f}: ${err.message}`);
      }
    }
    console.log(`[gen-case-doc] 批量完成：成功 ${ok}/${files.length}`);
    return;
  }

  if (flags.result) {
    await generateReport(flags.result, flags, qcoderRoot);
    return;
  }

  const suitePath = flags["qcoder-suite"] || positional[0];
  if (!suitePath) {
    console.error(
      "用法:\n" +
        "  node scripts/gen-case-doc.js <suite.json> [--topic 主题] [--out 目录] ...   # 设计文档\n" +
        "  node scripts/gen-case-doc.js --all [--out 目录] ...                         # 批量设计文档\n" +
        "  node scripts/gen-case-doc.js --result <result.json> [--out 目录] ...        # 执行报告"
    );
    process.exit(1);
  }
  await generateDoc(suitePath, flags, qcoderRoot);
}

main().catch((err) => {
  console.error(`[gen-case-doc] 生成失败: ${err.message}`);
  process.exit(1);
});
