const fs = require("fs");
const os = require("os");
const path = require("path");
const JSZip = require("jszip");

// 默认模板路径：优先使用环境变量；未配置时使用 e2e/templates 内置模板。
const DEFAULT_TEMPLATE_PATH = process.env.E2E_REPORT_TEMPLATE_PATH || "./templates/test-report-template.docx";
const DEFAULT_CASE_PLAN_PATH = process.env.E2E_CASE_PLAN_PATH || "./tests/case-plan.js";

function nowParts(date = new Date()) {
  const year = String(date.getFullYear());
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  const second = String(date.getSeconds()).padStart(2, "0");
  return { year, month, day, hour, minute, second };
}

function dateForView(date = new Date()) {
  const p = nowParts(date);
  return `${p.year}-${p.month}-${p.day}`;
}

function fileTimestamp(date = new Date()) {
  const p = nowParts(date);
  return `${p.year}${p.month}${p.day}-${p.hour}${p.minute}${p.second}`;
}

function safeName(value) {
  return String(value || "自动化测试")
    .replace(/[\\/:*?"<>|]/g, "-")
    .replace(/\s+/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function toCnStatus(status) {
  if (status === "passed") {
    return "通过";
  }
  if (status === "failed") {
    return "失败";
  }
  if (status === "timedOut") {
    return "超时";
  }
  if (status === "skipped") {
    return "跳过";
  }
  if (status === "interrupted") {
    return "中断";
  }
  return status || "未知";
}

function caseConclusionByStatus(status) {
  if (status === "passed") {
    return "通过";
  }
  if (status === "skipped") {
    return "跳过";
  }
  if (status === "timedOut") {
    return "超时";
  }
  if (status === "interrupted") {
    return "中断";
  }
  return "不通过";
}

function stripAnsi(text) {
  return String(text || "").replace(/\u001b\[[0-9;]*m/g, "");
}

function countByStatus(cases) {
  return {
    total: cases.length,
    passed: cases.filter((c) => c.status === "passed").length,
    failed: cases.filter((c) => c.status === "failed").length,
    skipped: cases.filter((c) => c.status === "skipped").length,
    timedOut: cases.filter((c) => c.status === "timedOut").length,
    interrupted: cases.filter((c) => c.status === "interrupted").length
  };
}

function finalConclusion(summary) {
  if (summary.failed > 0 || summary.timedOut > 0 || summary.interrupted > 0) {
    return "不通过";
  }
  if (summary.total === 0) {
    return "无结论（未执行用例）";
  }
  return "通过";
}

function splitMultiText(text) {
  return String(text || "")
    .split(/\r?\n|;/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function xmlEscape(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function toWordInlineXml(text) {
  const parts = String(text || "").split(/\r?\n/);
  return parts.map((line) => xmlEscape(line)).join("</w:t><w:br/><w:t>");
}

function regexEscape(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function replaceTokenAll(xmlText, token, value) {
  const pattern = new RegExp(regexEscape(token), "g");
  return xmlText.replace(pattern, toWordInlineXml(value));
}

// 对同一占位符按出现顺序填充值：用于 {{xxxx}} / {{xx}} / {{}} 这类重复占位符。
function replaceTokenSequence(xmlText, token, values) {
  const pattern = new RegExp(regexEscape(token), "g");
  let index = 0;
  const safeValues = Array.isArray(values) && values.length ? values : [""];

  return xmlText.replace(pattern, () => {
    const picked = index < safeValues.length ? safeValues[index] : safeValues[safeValues.length - 1];
    index += 1;
    return toWordInlineXml(picked);
  });
}

function toRelative(p) {
  return path.relative(process.cwd(), p).split(path.sep).join("/");
}

function pickError(result) {
  const errors = Array.isArray(result.errors) ? result.errors : [];
  for (const one of errors) {
    if (one && one.message) {
      return stripAnsi(one.message).trim();
    }
    if (one && one.value) {
      return stripAnsi(one.value).trim();
    }
  }
  return "";
}

function normalizeArtifacts(attachments = []) {
  const lines = [];
  for (const one of attachments) {
    if (!one || !one.path) {
      continue;
    }
    const rel = toRelative(one.path);
    lines.push(`${one.name || "artifact"}: ${rel}`);

    // 对文本附件做内联预览，便于在 DOCX 里直接看到关键明细。
    try {
      const ext = path.extname(String(one.path)).toLowerCase();
      if (ext === ".txt" && fs.existsSync(one.path)) {
        const stat = fs.statSync(one.path);
        if (stat.size > 0 && stat.size <= 30000) {
          const text = fs.readFileSync(one.path, "utf8").trim();
          if (text) {
            lines.push(`内容预览:\n${text}`);
          }
        }
      }
    } catch (error) {
      // ignore preview failures
    }
  }
  return lines;
}

function isImageAttachment(attachment) {
  if (!attachment || !attachment.path) {
    return false;
  }
  const ext = path.extname(String(attachment.path)).toLowerCase();
  return ext === ".png" || ext === ".jpg" || ext === ".jpeg";
}

function normalizeImageArtifacts(attachments = []) {
  const images = [];
  for (const one of attachments) {
    if (!isImageAttachment(one)) {
      continue;
    }
    const rawPath = String(one.path);
    const absPath = path.isAbsolute(rawPath) ? rawPath : path.resolve(process.cwd(), rawPath);
    if (!fs.existsSync(absPath)) {
      continue;
    }
    images.push({
      name: one.name || "screenshot",
      path: absPath,
      ext: path.extname(absPath).toLowerCase()
    });
  }
  return images;
}

function buildRunCommand() {
  const args = process.argv.slice(2).join(" ").trim();
  return args ? `npx playwright ${args}` : "npm test";
}

function defaultPreconditions() {
  return [
    "已完成 e2e 依赖安装并可执行 Playwright 测试",
    "已在 .env 中配置 E2E_BASE_URL、账号及必要参数",
    "测试设备/环境网络可达，登录页面可访问"
  ];
}

function buildEnvLines(baseURL) {
  return [
    `操作系统: ${os.platform()} ${os.release()}`,
    `Node.js: ${process.version}`,
    `目标地址: ${baseURL || "-"}`
  ];
}

function toBooleanMultiTerminal(value) {
  if (typeof value === "boolean") {
    return value;
  }
  const text = String(value || "").trim().toLowerCase();
  return text === "是" || text === "yes" || text === "true" || text === "1";
}

function normalizeCasePlanItem(item) {
  if (!item || typeof item !== "object") {
    return null;
  }
  const testCase = String(item.testCase || item["测试用例"] || "").trim();
  if (!testCase) {
    return null;
  }

  const testType = String(item.testType || item["测试类型"] || "通用").trim() || "通用";
  const testPage = String(item.testPage || item["测试页面"] || "").trim();
  const testContent = String(item.testContent || item["测试内容"] || "").trim();
  const multiTerminal = toBooleanMultiTerminal(
    item.multiTerminal !== undefined ? item.multiTerminal : item["多端测试"]
  );

  const steps = Array.isArray(item.steps) ? item.steps.map((one) => String(one || "").trim()).filter(Boolean) : [];
  const expected = Array.isArray(item.expected)
    ? item.expected.map((one) => String(one || "").trim()).filter(Boolean)
    : [];

  return {
    testCase,
    testType,
    testPage,
    testContent,
    multiTerminal,
    steps,
    expected
  };
}

function loadCasePlan() {
  const fullPath = path.resolve(process.cwd(), DEFAULT_CASE_PLAN_PATH);
  if (!fs.existsSync(fullPath)) {
    return [];
  }
  try {
    // eslint-disable-next-line global-require, import/no-dynamic-require
    delete require.cache[require.resolve(fullPath)];
    // eslint-disable-next-line global-require, import/no-dynamic-require
    const raw = require(fullPath);
    if (!Array.isArray(raw)) {
      return [];
    }
    return raw.map(normalizeCasePlanItem).filter(Boolean);
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn(`[self-test-report] 加载 case-plan 失败: ${error.message}`);
    return [];
  }
}

function titleLeaf(fullTitle) {
  const parts = String(fullTitle || "")
    .split(" > ")
    .map((one) => one.trim())
    .filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "";
}

function findCasePlanByTitle(casePlans, fullTitle) {
  const leaf = titleLeaf(fullTitle);
  return casePlans.find((one) => leaf === one.testCase || leaf.includes(one.testCase)) || null;
}

function buildCasePlanOrderMap(casePlans) {
  const map = new Map();
  casePlans.forEach((item, index) => {
    if (item && item.testCase) {
      map.set(item.testCase, index);
    }
  });
  return map;
}

function sortCasesByCasePlan(cases, casePlans) {
  const orderMap = buildCasePlanOrderMap(casePlans);
  return cases
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      const leftKey = left.item.casePlan && left.item.casePlan.testCase
        ? left.item.casePlan.testCase
        : null;
      const rightKey = right.item.casePlan && right.item.casePlan.testCase
        ? right.item.casePlan.testCase
        : null;

      const leftOrder = leftKey && orderMap.has(leftKey) ? orderMap.get(leftKey) : Number.MAX_SAFE_INTEGER;
      const rightOrder = rightKey && orderMap.has(rightKey) ? orderMap.get(rightKey) : Number.MAX_SAFE_INTEGER;

      if (leftOrder !== rightOrder) {
        return leftOrder - rightOrder;
      }
      return left.index - right.index;
    })
    .map((entry) => entry.item);
}

function defaultStepsByCaseName(caseName) {
  if (caseName.includes("切换启动和禁用")) {
    return [
      "进入配置页面，确认漫游参数区域默认展示状态",
      "将低信号漫游开关切换为禁用并观察阈值参数区",
      "将开关切回启用并复核参数区是否恢复显示",
      "将粘性终端漫游开关重复执行禁用/启用切换并确认联动结果"
    ];
  }
  if (caseName.includes("参数输入")) {
    return [
      "依次定位 2.4G/5G 开启漫游阈值和 2.4G/5G 强制漫游阈值输入框",
      "针对每个输入框执行正确参数、越界参数、小数参数、字母参数、特殊符号参数输入",
      "每次输入后执行保存并检查校验提示是否符合预期",
      "回填合法整数边界值后再次保存，确认错误提示消失并可正常保存"
    ];
  }
  return [
    "按测试用例定义执行页面交互流程",
    "提交关键操作并观察页面提示",
    "核对结果与预期是否一致"
  ];
}

function defaultExpectedByCaseName(caseName) {
  if (caseName.includes("切换启动和禁用")) {
    return [
      "启用状态下相关参数输入区可见",
      "禁用状态下相关参数输入区隐藏",
      "反复切换后显示/隐藏逻辑稳定无异常"
    ];
  }
  if (caseName.includes("参数输入")) {
    return [
      "合法整数参数可通过校验并保存成功",
      "越界参数触发范围校验提示",
      "小数、字母、特殊符号、空值等非法参数触发非范围校验提示"
    ];
  }
  return [
    "核心断言均通过",
    "无阻断性页面异常"
  ];
}

function scenarioByCasePlan(planItem) {
  const steps = planItem.steps.length ? planItem.steps : defaultStepsByCaseName(planItem.testCase);
  const expected = planItem.expected.length ? planItem.expected : defaultExpectedByCaseName(planItem.testCase);
  return {
    itemName: planItem.testCase,
    purpose: planItem.testContent || "按测试计划执行页面校验",
    steps,
    expected
  };
}

function toNumberedText(lines) {
  return lines.map((line, index) => `${index + 1}. ${line}`).join("\n");
}

function inferScenarioByTitle(title) {
  const lowerTitle = String(title || "").toLowerCase();

  if (lowerTitle.includes("demo page smoke") || lowerTitle.includes("demo")) {
    return {
      itemName: "Demo页面可达性校验",
      purpose: "验证目标 Web 页面可访问且基础内容可渲染，用于新工程自动化链路冒烟。",
      steps: [
        "访问配置的 demo 页面路径",
        "确认页面响应状态正常",
        "校验页面主体或指定元素可见"
      ],
      expected: [
        "页面请求成功且状态码小于400",
        "页面主体内容加载完成",
        "关键元素可见（配置了选择器时）"
      ]
    };
  }

  if (lowerTitle.includes("ssh uri") || lowerTitle.includes("lan_debug_port_ssh")) {
    return {
      itemName: "URI方式SSH开关校验",
      purpose: "验证通过 URI 调用可按参数正确开启/关闭 SSH，并对非法 key 请求进行拦截。",
      steps: [
        "使用正确 key 调用 URI 进行 SSH 开启操作",
        "使用正确 key 调用 URI 进行 SSH 关闭操作",
        "使用错误 key 调用 URI，校验设备拒绝执行"
      ],
      expected: [
        "开启请求返回成功标识（T）",
        "关闭请求返回成功标识（T）",
        "错误 key 请求返回失败标识（F）"
      ]
    };
  }

  if (lowerTitle.includes("wrong password")) {
    return {
      itemName: "错误密码登录校验",
      purpose: "验证账号存在但密码错误时，系统会拒绝登录并给出清晰错误提示，避免误进入主页面。",
      steps: [
        "打开登录页面并确认用户名、密码输入框及登录按钮可用",
        "输入有效用户名和错误密码，点击“登录”",
        "观察页面跳转、错误提示文案与主页面进入情况"
      ],
      expected: [
        "页面停留在登录页，不跳转到主页面",
        "错误提示非空且对用户可见",
        "不会触发成功登录后的业务流程"
      ]
    };
  }

  if (lowerTitle.includes("login success")) {
    return {
      itemName: "正常密码登录校验",
      purpose: "验证有效账号可正常登录并进入主页面，确保登录链路和会话链路可用。",
      steps: [
        "打开登录页面并输入有效账号密码",
        "点击“登录”并等待页面跳转",
        "校验主页面地址命中规则，必要时校验心跳接口可访问"
      ],
      expected: [
        "页面跳转到主页面且关键元素可见",
        "会话保持正常，不出现登录态异常",
        "后端心跳接口返回有效响应（已配置时）"
      ]
    };
  }

  if (lowerTitle.includes("disabled account")) {
    return {
      itemName: "禁用账号登录校验",
      purpose: "验证被禁用账号登录时的防护行为，确保系统拦截并提示用户，而非错误放行。",
      steps: [
        "打开登录页面并输入禁用账号信息",
        "点击“登录”后观察页面变化",
        "检查错误提示内容是否符合禁用账号预期"
      ],
      expected: [
        "页面保持在登录页，不进入主页面",
        "错误提示非空，且与禁用状态语义一致",
        "登录失败路径稳定可复现"
      ]
    };
  }

  if (
    lowerTitle.includes("status page real business flow") ||
    lowerTitle.includes("status page login") ||
    lowerTitle.includes("status overview") ||
    lowerTitle.includes("dhcp user list")
  ) {
    return {
      itemName: "status页面登录与进入校验",
      purpose: "验证登录后状态类页面关键链路可访问，核心状态数据可加载且展示稳定。",
      steps: [
        "完成登录并切换到状态相关菜单",
        "按顺序检查设备信息、WAN、LAN、DHCP、光功率、LLDP 等页面",
        "确认页面元素可见、接口返回正常、关键字段有值"
      ],
      expected: [
        "目标状态页面均可进入，无白屏和异常跳转",
        "关键字段可读取，接口返回码正常",
        "页面切换过程中无阻断性错误"
      ]
    };
  }

  if (lowerTitle.includes("roaming toggle low-signal")) {
    return {
      itemName: "低信号漫游开关显示/隐藏联动校验",
      purpose: "验证“低信号用户开启漫游”开关在启用/禁用切换时，2.4G/5G 开启漫游阈值输入区是否按预期显示与隐藏。",
      steps: [
        "打开漫游设置页面并确认低信号漫游阈值区默认可见",
        "将低信号漫游开关切换为“禁用”",
        "确认开启漫游阈值（2.4G/5G）输入区已隐藏",
        "将开关切换回“启用”",
        "确认开启漫游阈值输入区重新显示"
      ],
      expected: [
        "启用状态下，开启漫游阈值相关输入项可见",
        "禁用状态下，开启漫游阈值相关输入项隐藏",
        "重复切换后页面状态稳定，无异常残留显示"
      ]
    };
  }

  if (lowerTitle.includes("roaming toggle sticky-client")) {
    return {
      itemName: "粘性终端强制漫游开关显示/隐藏联动校验",
      purpose: "验证“粘性终端强制漫游RSSI阈值”开关在启用/禁用切换时，2.4G/5G 强制漫游阈值输入区是否按预期显示与隐藏。",
      steps: [
        "打开漫游设置页面并确认强制漫游阈值区默认可见",
        "将粘性终端强制漫游开关切换为“禁用”",
        "确认强制漫游阈值（2.4G/5G）输入区已隐藏",
        "将开关切换回“启用”",
        "确认强制漫游阈值输入区重新显示"
      ],
      expected: [
        "启用状态下，强制漫游阈值输入项可见",
        "禁用状态下，强制漫游阈值输入项隐藏",
        "反复切换时无渲染错位、无卡死、无异常提示"
      ]
    };
  }

  if (lowerTitle.includes("open roaming 2.4g validation matrix")) {
    return {
      itemName: "开启漫游阈值（2.4G）输入校验矩阵",
      purpose: "验证 2.4G 开启漫游阈值在启用状态下对正确值、越界值、非整数值、非数字符号值的校验行为。",
      steps: [
        "将两组漫游开关均置为“启用”，并设置其他字段为合法基线值",
        "依次输入越界值（如 -96、-39）并点击保存",
        "依次输入小数、字母、符号、空值等非法值并点击保存",
        "输入合法整数边界值与常用中间值（如 -95、-60、-40）并点击保存"
      ],
      expected: [
        "越界值触发“范围”类报错提示",
        "小数/字母/符号/空值触发“必须是整数”类报错提示",
        "合法整数可保存成功，字段错误提示清空"
      ]
    };
  }

  if (lowerTitle.includes("open roaming 5g validation matrix")) {
    return {
      itemName: "开启漫游阈值（5G）输入校验矩阵",
      purpose: "验证 5G 开启漫游阈值在启用状态下对正确值、越界值、非整数值、非数字符号值的校验行为。",
      steps: [
        "确保低信号漫游与强制漫游开关均启用，先回填其他字段合法值",
        "依次输入越界值并点击保存，观察范围校验反馈",
        "依次输入小数、字母、符号、空字符串等非法值并点击保存",
        "输入合法整数边界值与中间值并执行保存"
      ],
      expected: [
        "越界值均被拦截并提示范围错误",
        "非整数与非数字输入均被拦截并提示整数错误",
        "合法整数保存成功且页面报错提示消失"
      ]
    };
  }

  if (lowerTitle.includes("force roaming 2.4g validation matrix")) {
    return {
      itemName: "强制漫游RSSI阈值（2.4G）输入校验矩阵",
      purpose: "验证 2.4G 强制漫游阈值在启用状态下对边界值、越界值、非整数值和非常规字符输入的校验效果。",
      steps: [
        "打开页面并启用两组开关，先确保非目标字段值合法",
        "依次输入 -101、-44 等越界值并保存",
        "依次输入小数、字母、特殊符号、科学计数法文本等非法值并保存",
        "输入合法整数边界值和典型值（-100、-65、-45）并保存"
      ],
      expected: [
        "越界值触发范围校验提示",
        "非整数与非常规输入触发整数校验提示",
        "合法整数提交成功，字段错误提示清空"
      ]
    };
  }

  if (lowerTitle.includes("force roaming 5g validation matrix")) {
    return {
      itemName: "强制漫游RSSI阈值（5G）输入校验矩阵",
      purpose: "验证 5G 强制漫游阈值在启用状态下对合法输入与多类非法输入的拦截与放行逻辑。",
      steps: [
        "初始化页面并启用相关功能开关，准备合法基线值",
        "输入越界值并执行保存，检查范围提示是否准确",
        "输入小数、字母、符号、NaN 字符串、空值等非法输入并保存",
        "输入合法整数边界值与中间值并保存"
      ],
      expected: [
        "所有越界值均被范围校验拒绝",
        "所有非整数类输入均被整数校验拒绝",
        "合法整数通过保存校验并提示成功"
      ]
    };
  }

  return {
    itemName: "通用业务链路校验",
    purpose: "验证目标业务用例的主链路行为与预期一致，确保改动未引入明显回归。",
    steps: [
      "按用例定义执行自动化步骤",
      "观察页面/接口返回与关键断言结果",
      "记录执行状态、耗时与失败原因（如有）"
    ],
    expected: [
      "用例断言全部通过",
      "无阻断性报错或异常跳转",
      "关键业务结果与预期一致"
    ]
  };
}

function formatCaseDisplayName(caseNo, caseName) {
  return `测试项${caseNo}：${caseName}`;
}

function detectBrowserLabelFromTitle(title) {
  const raw = String(title || "");
  const first = raw.split(" > ")[0].trim().toLowerCase();
  if (first === "chromium") {
    return "Chromium";
  }
  if (first === "firefox") {
    return "Firefox";
  }
  if (first === "webkit") {
    return "WebKit";
  }
  return first ? first : "未知浏览器";
}

// 关键方法：返回位置之前最近的段落开始标签（<w:p ...>）位置，避免误命中 <w:pPr>。
function findParagraphStartBefore(docXml, beforeIndex) {
  const pattern = /<w:p(?:\s|>)/g;
  let hit = -1;
  let matched = pattern.exec(docXml);
  while (matched && matched.index < beforeIndex) {
    hit = matched.index;
    matched = pattern.exec(docXml);
  }
  return hit;
}

// 关键方法：提取“测试项2标题段落 + 测试项2表格”作为模板块，用于克隆测试项3+。
// 注意：不能用 lastIndexOf("<w:tbl")，否则会把测试项1表格也带进来，导致章节错位。
function extractCaseBlockByMarker(docXml, markerText) {
  const markerIndex = docXml.indexOf(markerText);
  if (markerIndex < 0) {
    return "";
  }

  const titleParagraphStart = findParagraphStartBefore(docXml, markerIndex);
  const tableStartIndex = docXml.indexOf("<w:tbl", markerIndex);
  const tableEndIndex = tableStartIndex > -1 ? docXml.indexOf("</w:tbl>", tableStartIndex) : -1;

  if (titleParagraphStart < 0 || tableStartIndex < 0 || tableEndIndex < 0) {
    return "";
  }

  return docXml.slice(titleParagraphStart, tableEndIndex + "</w:tbl>".length);
}

function pickFirstExistingMarker(docXml, candidates) {
  for (const marker of candidates) {
    if (String(docXml || "").indexOf(marker) > -1) {
      return marker;
    }
  }
  return "";
}

function resolveCaseTitleMarkers(docXml) {
  const case1Marker = pickFirstExistingMarker(docXml, [
    "{{测试用例1名称}}",
    "{{1:XXXX}}"
  ]);
  const case2Marker = pickFirstExistingMarker(docXml, [
    "{{测试用例2名称}}",
    "{{2:测试用例XXXXX}}"
  ]);
  return { case1Marker, case2Marker };
}

// 关键方法：定位“测试结果汇总”插入点。
// 业务要求是测试项3/4必须写在汇总结果上方，因此以“总用例”所在段落向上定位标题段。
function findSummaryInsertPos(docXml) {
  const summaryLabelIndex = docXml.indexOf("总用例：");
  if (summaryLabelIndex < 0) {
    return -1;
  }

  const summaryLabelPStart = findParagraphStartBefore(docXml, summaryLabelIndex);
  if (summaryLabelPStart < 0) {
    return -1;
  }

  // 优先找“测试结果”章节标题段落（Heading 2），确保汇总标题出现在所有测试项之后。
  let cursor = summaryLabelPStart;
  let guard = 0;
  while (guard < 30) {
    const paragraphStart = findParagraphStartBefore(docXml, cursor - 1);
    if (paragraphStart < 0) {
      break;
    }

    const paragraphEnd = docXml.indexOf("</w:p>", paragraphStart);
    if (paragraphEnd < 0) {
      break;
    }

    const paragraphXml = docXml.slice(paragraphStart, paragraphEnd + "</w:p>".length);
    if (
      paragraphXml.indexOf("测试结果") > -1 &&
      paragraphXml.indexOf('<w:pStyle w:val="2"') > -1
    ) {
      return paragraphStart;
    }

    cursor = paragraphStart;
    guard += 1;
  }

  return summaryLabelPStart;
}

// 关键方法：按“测试项2表格”模板复制出测试项3及以上的同版式表格，并插入到汇总区上方。
// 该实现直接复用模板原生表格样式，确保测试项3/4与测试项1/2保持完全一致。
function appendExtraCaseTables(docXml, extraCaseSlots, case2TitleMarker) {
  if (!Array.isArray(extraCaseSlots) || extraCaseSlots.length === 0) {
    return docXml;
  }

  if (!case2TitleMarker) {
    return docXml;
  }

  const caseBlockTemplate = extractCaseBlockByMarker(docXml, case2TitleMarker);
  if (!caseBlockTemplate) {
    return docXml;
  }

  const insertPos = findSummaryInsertPos(docXml);
  if (insertPos < 0) {
    throw new Error("模板缺少测试结果汇总区，无法插入扩展测试项表格");
  }

  const extraTablesXml = extraCaseSlots
    .map((item) =>
      replaceTokenAll(
        caseBlockTemplate,
        case2TitleMarker,
        formatCaseDisplayName(item.caseNo, item.slot.name)
      )
    )
    .join("");

  return `${docXml.slice(0, insertPos)}${extraTablesXml}${docXml.slice(insertPos)}`;
}

function buildCaseSlot(caseItem, index, preconditionsText, envText, runCommand) {
  if (!caseItem) {
    return {
      name: `自动化用例${index}（未执行）`,
      purpose: "本轮未采集到该用例执行记录。",
      preconditions: preconditionsText,
      env: envText,
      steps: "1. 无",
      expected: "1. 无",
      result: "实际结果：未执行",
      conclusion: "无结论",
      remarks: `复测命令：${runCommand}`
    };
  }

  const browserLabel = caseItem.browser || detectBrowserLabelFromTitle(caseItem.title);
  const testType = caseItem.casePlan && caseItem.casePlan.testType ? caseItem.casePlan.testType : "通用";
  const testBrowser = caseItem.casePlan
    ? (caseItem.casePlan.multiTerminal
      ? `需要多端测试，当前测试浏览器为${browserLabel}`
      : browserLabel)
    : browserLabel;
  const scenario = caseItem.casePlan ? scenarioByCasePlan(caseItem.casePlan) : inferScenarioByTitle(caseItem.title);
  const envWithPage = caseItem.casePlan && caseItem.casePlan.testPage
    ? `${envText}\n测试页面：${caseItem.casePlan.testPage}`
    : envText;
  const remarks = [`复测命令：${runCommand}`];
  const resultLines = [`实际结果：${toCnStatus(caseItem.status)}（耗时 ${caseItem.duration} ms）`];

  if (caseItem.location) {
    remarks.push(`用例位置：${caseItem.location}`);
  }
  remarks.push(`执行浏览器：${browserLabel}`);
  if (caseItem.retry > 0) {
    resultLines.push(`重试次数：${caseItem.retry}`);
  }
  if (caseItem.error) {
    resultLines.push(`失败原因：${caseItem.error}`);
  }
  if (caseItem.artifacts.length) {
    remarks.push(`产物：${caseItem.artifacts.join("\n")}`);
  }
  if (Array.isArray(caseItem.screenshots) && caseItem.screenshots.length) {
    remarks.push("执行截图：");
    remarks.push(`[[E2E_CASE_SCREEN_${index}]]`);
  }

  return {
    // 关键变量：name 直接写入模板“测试项”标题，必须是业务描述而非函数/文件路径。
    name: `${scenario.itemName}（${browserLabel}）`,
    testType,
    testBrowser,
    purpose: scenario.purpose,
    preconditions: preconditionsText,
    env: envWithPage,
    steps: toNumberedText(scenario.steps),
    expected: toNumberedText(scenario.expected),
    result: resultLines.join("\n"),
    conclusion: caseConclusionByStatus(caseItem.status),
    remarks: remarks.join("\n")
  };
}

// 关键方法：按模板中 {{}} 的字段顺序输出单个测试项的8个填充值。
// 顺序固定为：目的、预置条件、环境、步骤、期望、结果、结论、备注。
function buildCaseOrderedValues(slot) {
  return [
    slot.purpose,
    slot.preconditions,
    slot.env,
    slot.steps,
    slot.expected,
    slot.result,
    slot.conclusion,
    slot.remarks
  ];
}

function buildCaseOrderedValuesByTemplate(slot, caseFieldCount) {
  const classic8 = buildCaseOrderedValues(slot);
  const extended10 = [
    slot.testType || "",
    slot.purpose,
    slot.preconditions,
    slot.testBrowser || "",
    slot.env,
    slot.steps,
    slot.expected,
    slot.result,
    slot.conclusion,
    slot.remarks
  ];

  if (!Number.isFinite(caseFieldCount) || caseFieldCount <= 8) {
    return classic8;
  }
  if (caseFieldCount === 9) {
    return [slot.testType || "", ...classic8];
  }
  if (caseFieldCount >= 10) {
    if (caseFieldCount === 10) {
      return extended10;
    }
    const extraCount = caseFieldCount - 10;
    return [...extended10, ...new Array(extraCount).fill(slot.remarks || "")];
  }
  return classic8;
}

async function detectCaseFieldCountFromTemplate(templatePath) {
  try {
    const source = fs.readFileSync(templatePath);
    const zip = await JSZip.loadAsync(source);
    if (!zip.file("word/document.xml")) {
      return 8;
    }
    const docXml = await zip.file("word/document.xml").async("string");
    const markers = resolveCaseTitleMarkers(docXml);
    const marker = markers.case2Marker || markers.case1Marker;
    if (!marker) {
      return 8;
    }
    const caseBlock = extractCaseBlockByMarker(docXml, marker);
    if (!caseBlock) {
      return 8;
    }
    const matches = caseBlock.match(/\{\{\}\}/g) || [];
    const count = matches.length;
    if (count >= 8 && count <= 20) {
      return count;
    }
    return 8;
  } catch (error) {
    return 8;
  }
}

function buildMarkdown(payload) {
  const lines = [];
  lines.push(`# （${payload.topic}）测试报告`);
  lines.push("");
  lines.push(`- 项目代号：${payload.projectCode}`);
  lines.push(`- 生成时间：${payload.reportDate}`);
  lines.push(`- 报告文件：${toRelative(payload.docxPath)}`);
  lines.push("");
  lines.push("## 用例摘要");
  lines.push(`- 总用例：${payload.summary.total}`);
  lines.push(`- 通过：${payload.summary.passed}`);
  lines.push(`- 失败：${payload.summary.failed}`);
  lines.push(`- 跳过：${payload.summary.skipped}`);
  lines.push(`- 超时：${payload.summary.timedOut}`);
  lines.push(`- 中断：${payload.summary.interrupted}`);
  lines.push(`- 结论：${payload.finalConclusion}`);
  lines.push("");
  lines.push("## 用例详情");
  payload.cases.forEach((item, i) => {
    lines.push(`${i + 1}. ${item.title}`);
    lines.push(`   - 状态：${toCnStatus(item.status)}`);
    lines.push(`   - 耗时：${item.duration} ms`);
    if (item.error) {
      lines.push(`   - 错误：${item.error.replace(/\r?\n/g, " ")}`);
    }
  });
  return `${lines.join("\n")}\n`;
}

function findMaxRelationshipId(relsXml) {
  const matches = String(relsXml || "").match(/Id="rId(\d+)"/g) || [];
  let maxId = 0;
  matches.forEach((item) => {
    const one = Number(item.replace(/[^0-9]/g, ""));
    if (Number.isFinite(one) && one > maxId) {
      maxId = one;
    }
  });
  return maxId;
}

function findMaxDrawingDocPrId(docXml) {
  const matches = String(docXml || "").match(/<wp:docPr[^>]*\sid="(\d+)"/g) || [];
  let maxId = 0;
  matches.forEach((item) => {
    const matched = item.match(/id="(\d+)"/);
    const one = matched ? Number(matched[1]) : 0;
    if (Number.isFinite(one) && one > maxId) {
      maxId = one;
    }
  });
  return maxId;
}

function buildPictureRunXml(relId, docPrId, titleText) {
  const safeTitle = xmlEscape(titleText || "截图");
  const cx = 3600000;
  const cy = 2025000;
  return (
    `<w:r><w:br/></w:r>` +
    `<w:r><w:drawing>` +
    `<wp:inline distT="0" distB="0" distL="0" distR="0">` +
    `<wp:extent cx="${cx}" cy="${cy}"/>` +
    `<wp:effectExtent l="0" t="0" r="0" b="0"/>` +
    `<wp:docPr id="${docPrId}" name="Screenshot ${docPrId}" descr="${safeTitle}"/>` +
    `<wp:cNvGraphicFramePr/>` +
    `<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">` +
    `<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">` +
    `<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">` +
    `<pic:nvPicPr><pic:cNvPr id="${docPrId}" name="${safeTitle}"/>` +
    `<pic:cNvPicPr><a:picLocks noChangeAspect="1"/></pic:cNvPicPr></pic:nvPicPr>` +
    `<pic:blipFill><a:blip r:embed="${relId}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>` +
    `<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm>` +
    `<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>` +
    `</pic:pic></a:graphicData></a:graphic></wp:inline>` +
    `</w:drawing></w:r>`
  );
}

function injectScreenshotRunsIntoRemark(docXml, marker, runXml) {
  if (!marker) {
    return docXml;
  }
  const escapedMarker = marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(escapedMarker, "g");
  if (!pattern.test(docXml)) {
    return docXml;
  }
  pattern.lastIndex = 0;
  return docXml.replace(pattern, `</w:t></w:r>${runXml}<w:r><w:t>`);
}

async function renderTemplateDocx(templatePath, outputPath, replaceNamed, replaceOrdered, caseScreenshots = {}) {
  const source = fs.readFileSync(templatePath);
  const zip = await JSZip.loadAsync(source);

  if (!zip.file("word/document.xml")) {
    throw new Error("模板缺少 word/document.xml，无法填充");
  }

  let docXml = await zip.file("word/document.xml").async("string");

  docXml = replaceTokenSequence(docXml, "{{xxxx}}", replaceNamed.xxxxValues);
  docXml = replaceTokenSequence(docXml, "{{xx}}", replaceNamed.xxValues);
  docXml = replaceTokenAll(docXml, "{{补充时间}}", replaceNamed.publishDate);
  docXml = replaceTokenAll(docXml, "{{xxxxx}}", replaceNamed.changeSummary);
  const markers = resolveCaseTitleMarkers(docXml);
  docXml = appendExtraCaseTables(docXml, replaceNamed.extraCaseSlots || [], markers.case2Marker);
  if (markers.case1Marker) {
    docXml = replaceTokenAll(docXml, markers.case1Marker, replaceNamed.case1Name);
  }
  if (markers.case2Marker) {
    docXml = replaceTokenAll(docXml, markers.case2Marker, replaceNamed.case2Name);
  }

  docXml = replaceTokenSequence(docXml, "{{}}", replaceOrdered);

  const caseKeys = Object.keys(caseScreenshots || {});
  if (caseKeys.length) {
    const relsFile = "word/_rels/document.xml.rels";
    const relsXml = await zip.file(relsFile).async("string");
    let relsText = relsXml;
    let maxRid = findMaxRelationshipId(relsText);
    let maxDocPrId = findMaxDrawingDocPrId(docXml);
    let imageNo = 1;
    caseKeys.forEach((caseNoText) => {
      const caseNo = Number(caseNoText);
      const marker = `[[E2E_CASE_SCREEN_${caseNo}]]`;
      const screenshots = Array.isArray(caseScreenshots[caseNoText]) ? caseScreenshots[caseNoText] : [];
      if (!screenshots.length) {
        docXml = docXml.replace(marker, "");
        return;
      }

      const runs = [];
      screenshots.forEach((shot, index) => {
        const ext = shot.ext === ".jpeg" ? ".jpg" : shot.ext;
        const mediaName = `e2e-screenshot-${imageNo}${ext}`;
      const mediaPath = `word/media/${mediaName}`;
        const relId = `rId${maxRid + 1}`;
        maxRid += 1;
        maxDocPrId += 1;
        imageNo += 1;

        zip.file(mediaPath, fs.readFileSync(shot.path));
        const relNode = `<Relationship Id="${relId}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/${mediaName}"/>`;
        relsText = relsText.replace("</Relationships>", `${relNode}</Relationships>`);
        runs.push(
          buildPictureRunXml(relId, maxDocPrId, `测试项${caseNo}截图${index + 1}`)
        );
      });

      docXml = injectScreenshotRunsIntoRemark(docXml, marker, runs.join(""));
    });

    // 保证 jpg/jpeg 类型可被 Word 识别。
    let contentTypes = await zip.file("[Content_Types].xml").async("string");
    if (!contentTypes.includes('Extension="jpg"')) {
      contentTypes = contentTypes.replace(
        "</Types>",
        '<Default Extension="jpg" ContentType="image/jpeg"/></Types>'
      );
    }
    if (!contentTypes.includes('Extension="jpeg"')) {
      contentTypes = contentTypes.replace(
        "</Types>",
        '<Default Extension="jpeg" ContentType="image/jpeg"/></Types>'
      );
    }
    zip.file("[Content_Types].xml", contentTypes);
    zip.file(relsFile, relsText);
  }

  zip.file("word/document.xml", docXml);
  const out = await zip.generateAsync({ type: "nodebuffer" });
  fs.writeFileSync(outputPath, out);
}

class SelfTestReportReporter {
  constructor(options = {}) {
    this.options = options;
    this.cases = [];
    this.baseURL = "";
    this.casePlans = loadCasePlan();
  }

  onBegin(config) {
    const project = Array.isArray(config.projects) ? config.projects[0] : null;
    const use = project && project.use ? project.use : {};
    this.baseURL = use.baseURL || process.env.E2E_BASE_URL || "";
  }

  // 记录每条用例关键执行结果，供模板字段填充使用。
  onTestEnd(test, result) {
    const file = test.location && test.location.file ? toRelative(test.location.file) : "";
    const line = test.location && typeof test.location.line === "number" ? test.location.line : "";
    const fullTitle = test.titlePath().slice(1).join(" > ");
    const browser = detectBrowserLabelFromTitle(fullTitle);
    const matchedPlan = findCasePlanByTitle(this.casePlans, fullTitle);

    // 多端测试=否 时，仅记录 Chromium 结果，不把其他浏览器的 skip 写入报告。
    if (matchedPlan && !matchedPlan.multiTerminal && browser !== "Chromium") {
      return;
    }

    this.cases.push({
      title: fullTitle,
      browser,
      casePlan: matchedPlan,
      status: result.status,
      duration: result.duration,
      retry: result.retry || 0,
      location: file ? `${file}:${line}` : "",
      error: pickError(result),
      artifacts: normalizeArtifacts(result.attachments || []),
      screenshots: normalizeImageArtifacts(result.attachments || [])
    });
  }

  async onEnd() {
    if (process.argv.includes("--list")) {
      return;
    }

    this.cases = sortCasesByCasePlan(this.cases, this.casePlans);

    const generatedAt = new Date();
    const reportDate = dateForView(generatedAt);
    const summary = countByStatus(this.cases);
    const conclusion = finalConclusion(summary);

    const outputDir = path.resolve(process.cwd(), this.options.outputDir || "self-test-reports");
    const topic = process.env.E2E_REPORT_TOPIC || this.options.reportTopic || "Web UI自动化自测";
    const projectCode = process.env.E2E_REPORT_PROJECT_CODE || reportDate.replace(/-/g, "");
    const runCommand = buildRunCommand();

    const preconditionsList = splitMultiText(process.env.E2E_REPORT_PRECONDITIONS);
    const preconditionsText = toNumberedText(
      preconditionsList.length ? preconditionsList : defaultPreconditions()
    );
    const envText = toNumberedText(buildEnvLines(this.baseURL));

    const templatePath = path.resolve(process.env.E2E_REPORT_TEMPLATE_PATH || DEFAULT_TEMPLATE_PATH);
    if (!fs.existsSync(templatePath)) {
      // eslint-disable-next-line no-console
      console.error(`[self-test-report] 模板文件不存在: ${templatePath}`);
      return;
    }
    const caseFieldCount = await detectCaseFieldCountFromTemplate(templatePath);

    // 关键变量：slot1/slot2 对应模板原有两条测试块；
    // 第三条及后续会复制“测试项2表格模板”插入到汇总区上方，保持同版式。
    const slot1 = buildCaseSlot(this.cases[0], 1, preconditionsText, envText, runCommand);
    const slot2 = buildCaseSlot(this.cases[1], 2, preconditionsText, envText, runCommand);
    const extraCaseSlots = [];
    for (let i = 2; i < this.cases.length; i += 1) {
      extraCaseSlots.push({
        caseNo: i + 1,
        slot: buildCaseSlot(this.cases[i], i + 1, preconditionsText, envText, runCommand)
      });
    }

    // 关键变量：emptyOrderedValues 必须严格匹配“测试项表格 + 汇总区”中 {{}} 的出现顺序。
    // 支持模板每条测试项 8 字段（旧）或 10 字段（新增测试类型/测试浏览器）。
    const caseOrderedValues = []
      .concat(buildCaseOrderedValuesByTemplate(slot1, caseFieldCount))
      .concat(buildCaseOrderedValuesByTemplate(slot2, caseFieldCount));
    extraCaseSlots.forEach((item) => {
      caseOrderedValues.push(...buildCaseOrderedValuesByTemplate(item.slot, caseFieldCount));
    });

    const emptyOrderedValues = [
      ...caseOrderedValues,
      String(summary.total),
      String(summary.passed),
      String(summary.failed),
      String(summary.skipped),
      String(summary.timedOut),
      String(summary.interrupted),
      conclusion
    ];

    const parts = nowParts(generatedAt);
    const fileBase = `测试报告-${safeName(topic)}-${fileTimestamp(generatedAt)}`;
    const docxPath = path.join(outputDir, `${fileBase}.docx`);
    const mdPath = path.join(outputDir, `${fileBase}.md`);
    const caseScreenshots = {};
    this.cases.forEach((caseItem, idx) => {
      const key = String(idx + 1);
      caseScreenshots[key] = Array.isArray(caseItem.screenshots) ? caseItem.screenshots : [];
    });
    fs.mkdirSync(outputDir, { recursive: true });

    try {
      await renderTemplateDocx(
        templatePath,
        docxPath,
        {
          xxxxValues: [projectCode, parts.year],
          xxValues: [parts.month, parts.day],
          publishDate: reportDate,
          case1Name: formatCaseDisplayName(1, slot1.name),
          case2Name: formatCaseDisplayName(2, slot2.name),
          extraCaseSlots,
          changeSummary: "自动生成E2E自测报告"
        },
        emptyOrderedValues,
        caseScreenshots
      );
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error(`[self-test-report] 模板填充失败: ${error.message}`);
      return;
    }

    const payload = {
      topic,
      projectCode,
      reportDate,
      summary,
      finalConclusion: conclusion,
      cases: this.cases,
      docxPath
    };
    fs.writeFileSync(mdPath, buildMarkdown(payload), "utf8");

    // eslint-disable-next-line no-console
    console.log(`[self-test-report] 模板报告生成成功: ${toRelative(docxPath)}`);
  }
}

// 附加导出模板渲染工具函数，供 scripts/gen-case-doc.js（用例设计文档生成）复用。
// 注意：module.exports 仍为 class，Playwright reporter 配置无需变更。
SelfTestReportReporter.renderTemplateDocx = renderTemplateDocx;
SelfTestReportReporter.replaceTokenAll = replaceTokenAll;
SelfTestReportReporter.replaceTokenSequence = replaceTokenSequence;
SelfTestReportReporter.toWordInlineXml = toWordInlineXml;
SelfTestReportReporter.xmlEscape = xmlEscape;
SelfTestReportReporter.regexEscape = regexEscape;
SelfTestReportReporter.toNumberedText = toNumberedText;
SelfTestReportReporter.extractCaseBlockByMarker = extractCaseBlockByMarker;
SelfTestReportReporter.appendExtraCaseTables = appendExtraCaseTables;
SelfTestReportReporter.resolveCaseTitleMarkers = resolveCaseTitleMarkers;
SelfTestReportReporter.findParagraphStartBefore = findParagraphStartBefore;
SelfTestReportReporter.findSummaryInsertPos = findSummaryInsertPos;
SelfTestReportReporter.detectCaseFieldCountFromTemplate = detectCaseFieldCountFromTemplate;
SelfTestReportReporter.buildCaseOrderedValuesByTemplate = buildCaseOrderedValuesByTemplate;
SelfTestReportReporter.formatCaseDisplayName = formatCaseDisplayName;
SelfTestReportReporter.safeName = safeName;
SelfTestReportReporter.nowParts = nowParts;
SelfTestReportReporter.dateForView = dateForView;

module.exports = SelfTestReportReporter;
