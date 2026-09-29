#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INTL 国际版真机 E2E 测试执行器 —— 老 UI（HTML 多页版）专用

目标设备: HG6163FC1 等国际版网关（login.html 独立登录页 + main.html 多页 html 架构）
用例目录: operators/intl/cases/real/html/（按页面拆分，17 个套件 67 个文件）

两线合并产物（2026-09-04）：
  本脚本 = 0828 线 html 全量执行器（8.25~9.3 深测成果）移植到 0904 基线仓库：
  - 凭据统一 QCT_INTL_* 前缀（core.config 解析，无硬编码默认密码）
  - 融合 0904 线 --scheme 自然语言协议选择（HTTP/HTTPS 自动探测，自签证书忽略校验）
  - 保留 0828 线验证过的 html 特性：SKIP（页面/菜单不存在跳过）、
    delete_wan_row(row_text) 行文本定位删除、teardown 保证性登出（设备 IP 级会话）、
    iPhone 13 移动设备模拟（tags 预留）、selectors_real_html.json 优先加载

用法:
  python runner/run_intl_real_html.py --suite status|wan|all [--scheme <协议>] [--headful] [--out DIR]
  --scheme 支持自然语言描述是否走 HTTPS/HTTP，如 "https加密访问"、"http明文"、"自动探测"；
           默认 auto：自动探测设备可达协议（HTTPS 优先，自签证书自动忽略校验）。
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Error as PWError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.config import load_dotenv, resolve_env_value  # noqa: E402
from core.intl_suite_order import ALL_FILES, LOCKOUT_IDS, SUITES  # noqa: E402


class MenuMissing(PWTimeout):
    """三级菜单项在当前固件不存在（页面缺失）——由 open_page 的菜单回退路径抛出。

    用途：--fast 会把「标准登录块 + 三级菜单」合并成单步 real.open_page。若不特判，
    菜单缺失时抛出的超时挂在 open_page 上，而执行器的「页面/菜单不存在 → 整条用例
    跳过」策略只识别 click_menu，于是「设备无此页面」会被误判为 FAIL
    （真机实测 INTL-FW-008/027/028：设备 ipv6_mac_flag=0，IPv6 MAC 过滤菜单项根本不渲染）。
    继承 PWTimeout 以保持既有超时语义（调用方仍可按超时捕获）。
    """


load_dotenv()  # 从工程根 .env 注入 QCT_INTL_* 凭据与固件文件路径（.env 不入库）

BASE_URL = os.environ.get("QCT_INTL_BASE_URL", "http://192.168.1.1")
ADMIN_USER = os.environ.get("QCT_INTL_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("QCT_INTL_ADMIN_PASS", "")  # 无默认值：缺失即空串
USER_USER = os.environ.get("QCT_INTL_USER_USER", "user")
USER_PASS = os.environ.get("QCT_INTL_USER_PASS", "")    # 同上，真机登录前须在 .env 配置

# ---------- 提速模式（--fast）----------
# 老 UI 页面固定的「睡等」占比很高（如 click_menu 每次固定 1.2+2.0+3.0=6.2s、
# navigate 固定 2.5s、login 固定 3.0s，103 条 wifi 用例合计约 30 分钟纯等待）。
# --fast 把这些固定等待改为「就绪轮询」：等到页面/控件真正就绪即返回，
# 未就绪才等到超时上限。语义不变（等的是同一件事），只是不再盲等固定时长。
FAST_MODE = False       # --fast 开启
WAIT_SCALE = 1.0        # 用例内 real.wait 的时长系数（--fast 默认 0.5）
FAST_POLL_MS = 150      # 就绪轮询间隔

# 会话复用（默认开，--no-reuse-session 关闭）：只对「声明了复用语义」的用例生效
# —— 即首个步骤为 real.ensure_login / real.open_page 的用例（--fast 下标准登录四步
# 也会被改写为 ensure_login）。若本次执行范围里存在这类用例，run 开始先登录一次并
# 存 storage_state，这些用例的 context 注入该存档 → 整个 run 只登录一次。
# 未声明复用语义的用例（未登录拦截、登录流程、错误密码等）不注入会话，行为与改动前
# 完全一致，避免把「已认证」偷偷带进本来就该处于未登录态的用例。
SESSION_REUSE = True

# 瞬时网络故障特征（网关在重启/负载抖动时会中断一次导航，稍后即恢复）。
# 这些错误只重试、不算用例失败——真机实测 2026-09-18 全量回归中 INTL-LAN-015
# 出现一次 Page.goto: net::ERR_ABORTED（同时刻本机外网也不可达），属环境抖动。
_TRANSIENT_NET = (
    "ERR_ABORTED", "ERR_CONNECTION_RESET", "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_REFUSED", "ERR_EMPTY_RESPONSE", "ERR_NETWORK_CHANGED",
    "ERR_TIMED_OUT", "ERR_SOCKET_NOT_CONNECTED", "ERR_ADDRESS_UNREACHABLE",
)

# 「标准登录四步」的**取值判据**（2026-09-18 加固，与 tools/apply_single_login.py 同源）。
# 仅比对动作/选择器会漏掉「登录本身即被测点」的用例——它们的动作序列与前置登录完全
# 相同，但 fill 的取值不是常规凭据占位符：
#   INTL-STATUS-004 用 <img src=x onerror=alert(1)> 测登录框 XSS 注入
#   INTL-LOGIN-002  用 WrongPass123 测错误密码提示
#   INTL-LOGIN-003  用空串测空用户名/空密码前端拦截
# 这类用例一旦被 --fast 改写为 ensure_login，执行器会注入已认证会话 → 首步不再是
# 「以未登录态提交被测值」，断言落点整体错位（2026-09-18 全量回归 24 失败之根因）。
STD_LOGIN_USER_VALUE = "${QCT_INTL_ADMIN_USER}"
STD_LOGIN_PASS_VALUE = "${QCT_INTL_ADMIN_PASS}"

# 用例尾部出现这些动作/选择器，说明「登录失败/账号锁定」是被测点，同样不可改写
# （INTL-SEC-002「锁定期间即使正确密码也无法登录」即使取值是常规凭据，也必须保留
#  原始登录流程——断言指向 .login_error_hint，注入会话后断言必然落空）。
LOGIN_FAIL_ACTIONS = {"real.assert_login_error", "real.assert_login_stays"}
LOGIN_FAIL_SELECTORS = ("login_error_hint",)


def _ms(value):
    """按 WAIT_SCALE 折算用例内的固定等待时长（下限 100ms）。"""
    try:
        return max(100, int(int(value) * WAIT_SCALE))
    except (TypeError, ValueError):
        return 100


# ---------- 访问协议（HTTP/HTTPS）选择：支持自然语言描述 ----------
def set_base_url(url):
    """运行期更新模块级 BASE_URL（登录页跳转均引用它）"""
    global BASE_URL
    BASE_URL = url.rstrip("/")


def parse_scheme(text):
    """自然语言解析访问协议: 返回 'https' | 'http' | 'auto'

    支持: "https" / "https加密" / "安全" / "tls" / "ssl" -> https
          "http" / "明文" / "不加密" / "非加密"          -> http
          "自动" / "auto" / "都支持" / 空                -> auto（探测，HTTPS 优先）
    """
    if not text:
        return "auto"
    t = str(text).strip().lower()
    if not t:
        return "auto"
    if any(k in t for k in ("auto", "自动", "都支持", "都可以", "both", "探测")):
        return "auto"
    # https 关键词先判（避免 'http' 子串误命中 'https'）
    if any(k in t for k in ("https", "加密", "安全", "tls", "ssl", "证书")):
        return "https"
    if any(k in t for k in ("http", "明文", "不加密", "非加密", "普通")):
        return "http"
    return "auto"


def probe_scheme(host):
    """探测设备实际可达协议：HTTPS 优先（自签证书忽略校验），失败回退 HTTP"""
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for scheme in ("https", "http"):
        try:
            req = urllib.request.Request(f"{scheme}://{host}/login.html", method="GET")
            resp = urllib.request.urlopen(req, timeout=6, context=ctx if scheme == "https" else None)
            if resp.status in (200, 301, 302, 401, 403):
                return scheme
        except Exception:
            continue
    return None


def resolve_base_url(scheme_text):
    """按自然语言协议描述解析最终 BASE_URL；auto 时自动探测"""
    m = re.match(r"^(?:https?://)?([^/]+)", BASE_URL)
    host = m.group(1) if m else "192.168.1.1"
    scheme = parse_scheme(scheme_text)
    if scheme == "auto":
        detected = probe_scheme(host)
        if not detected:
            print("[WARN] 自动探测失败（HTTPS/HTTP 均不可达），回退 HTTP")
            detected = "http"
        scheme = detected
        print(f"[SCHEME] 自动探测: 使用 {scheme.upper()} 访问 {host}")
    else:
        print(f"[SCHEME] 指定协议: 使用 {scheme.upper()} 访问 {host}")
    set_base_url(f"{scheme}://{host}")
    return BASE_URL


# 选择器按 UI 形态（固件版本）区分：本脚本固定 html，优先 selectors_real_html.json，
# 回退通用 selectors_real.json（用例以直接 CSS 为主，语义 key 为预留能力）
UI_VARIANT = "html"
_SEL_CACHE = {}


def _load_sel():
    if UI_VARIANT not in _SEL_CACHE:
        intl_dir = os.path.join(ROOT, "operators", "intl")
        path = os.path.join(intl_dir, f"selectors_real_{UI_VARIANT}.json")
        if not os.path.exists(path):
            path = os.path.join(intl_dir, "selectors_real.json")
        _SEL_CACHE[UI_VARIANT] = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    return _SEL_CACHE[UI_VARIANT]


# 虚拟选择器别名表：这类控件在 DOM 里**没有 id**，但用例侧仍统一写成 #fhId_xxx 形态
# （与真实 id 控件观感一致，读用例时不必区分两套定位风格），由执行器在此映射到真实定位方式。
# ⚠️ 表里的键**不是** DOM 中的真实 id：拿去浏览器 querySelector 查不到，必须经 resolve_sel()
#    解析——所有接收 selector 的动作已统一走它（含 _need_field / read_field / radio 族）。
# ⚠️ `selector` 的值是 **Playwright 定位语法**（可含 `:has-text()` 等扩展伪类）。
#    因此只对走 Playwright 的路径有效：`page.locator(...)`（click / fill / assert_visible /
#    assert_element_count…）与 radio 族（已改为 Locator.evaluate）；而 `_need_field` /
#    `read_field` / `assert_absent` / `assert_field_error` / `probe_disabled` 走的是
#    `document.querySelector`，**遇到 :has-text 会 SyntaxError**（报错明确，不会静默错判）。
#    要给这些动作用别名，得先把它迁到 Playwright 路径。
# 集中登记的理由同 FIELD_KINDS / FIELD_FORMATS：实现细节收在执行器，用例只写"要断言什么"。
SELECTOR_ALIASES = {
    "#fhId_WPAAlgorithms": {
        # 2026-09-22 真机 DOM 探测确认：该组 radio 自身上下无 id（group / form-item / input 全为 null），
        # 只能按 form-item 的 label 文案定位到 .el-radio-group 容器。
        "selector": 'div.el-form-item:has-text("WPA Algorithms") .el-radio-group',
        # 该组候选文案（el-radio 的**显示值**；注意 TKIPAES 的 value 是 TKIPandAES，二者不同）
        "options": ["AES", "TKIPAES"],
    },
}


def _validate_selector_aliases():
    """别名表自检：键必须是选择器形态、必须给出非空真实选择器（启动时跑一次）。"""
    for k, v in SELECTOR_ALIASES.items():
        if not (isinstance(k, str) and k.startswith(("#", ".", "["))):
            raise SystemExit(f"[FATAL] 别名表键必须是 #/. /[ 开头的选择器形态：{k!r}")
        if not (v.get("selector") or "").strip():
            raise SystemExit(f"[FATAL] 别名 {k} 缺少真实选择器")


def alias_options(key):
    """取虚拟别名声明的候选文案（如单选组的 AES/TKIPAES）；非别名返回 None。"""
    a = SELECTOR_ALIASES.get(key.strip()) if isinstance(key, str) else None
    return list(a["options"]) if a and a.get("options") else None


def resolve_sel(key):
    """把用例里的 selector 解析成真实 CSS，三条路径按优先级：

    1. 虚拟别名（SELECTOR_ALIASES）→ 控件在 DOM 无 id，映射到真实定位方式；
    2. 已具 CSS 形态（# / . / [ / : 开头）→ 原样返回；
    3. 语义 key（'login.username'）→ selectors_real*.json 查表。
    """
    if not isinstance(key, str):
        return None
    alias = SELECTOR_ALIASES.get(key.strip())
    if alias:
        return alias["selector"]
    if key.startswith(("#", ".", "[", ":")):
        return key
    parts = key.split(".")
    node = _load_sel()
    for p in parts:
        if isinstance(node, dict) and p in node:
            node = node[p]
        else:
            return None
    return node if isinstance(node, str) else None


# 敏感字段选择器：snapshot 日志里对其值打码（密钥明文不进日志）
_SECRET_SELS = ("#fhId_PreSharedKey", "#fhId_PSK", "#fhId_Password")


def _is_secret_sel(selector):
    return (selector or "").strip() in _SECRET_SELS


# 字段「读法」表：快照别名 → 读取方式。读法是字段的固有属性（adv 恒为开关、keylen 恒只记
# 长度），不属于单次调用，因此集中在执行器声明：用例的 real.snapshot 只写 fields，不再逐处
# 重复 bools/lengths。用例显式传的 bools/lengths 仍生效（并集），便于临时字段不吃表。
# 注意表按「别名」而非选择器定：同一选择器 #fhId_PreSharedKey 在 key（文本）与 keylen
# （只记长度）两种别名下读法不同，不能被选择器合并。
FIELD_KINDS = {
    "adv": "bool",     # 开关/复选框：记勾选态
    "keylen": "len",   # 只记长度：密钥明文不进快照与日志
}

# 具名格式表：正则统一登记在这里，用例侧只写 assert_field_format(selector, "mac")，
# 用例 JSON 里不再出现任何正则（可读性更好，也便于集中维护/扩展）。
# 表内统一用字符类等价表达（[0-9] 代 \d、[.] 代 \.），避免转义层级混淆。
FIELD_FORMATS = {
    "mac":      ("^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$",
                 "MAC 地址（6 组两位十六进制）"),
    "duration": ("^[0-9]+ d [0-9]+ h [0-9]+ m [0-9]+ s$",
                 "运行时间 Xd Xh Xm Xs"),
    "ipv4":     ("^([0-9]{1,3}[.]){3}[0-9]{1,3}$",
                 "IPv4 地址"),
    "ipv6":     ("^[0-9A-Fa-f:]{2,45}$",
                 "IPv6 地址（宽松匹配）"),
    "hostname": ("^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$",
                 "主机名 / 域名标签"),
    "percent":  ("^[0-9]+([.][0-9]+)?%$",
                 "百分比（不带上下界）"),
    "datetime": ("^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}(:[0-9]{2})?$",
                 "日期时间 YYYY-MM-DD HH:MM[:SS]"),
}


class PreconditionBlocked(Exception):
    """前置/环境条件不满足（如设备未开通 WAN 业务导致接口下拉无可选项）。

    语义：用例在当前设备状态下不具备可执行条件，判定为 SKIP 而非 FAIL，
    避免把"环境受限"误报成"产品缺陷"。仅在确无可选项时抛出。
    """


class IntlSession:
    def __init__(self, page, out_dir):
        self.page = page
        self.out_dir = out_dir
        self._dialogs = []
        self._unauthorized = False
        self._skip_next = 0
        # 原值快照仓库：{快照名: {别名: {selector, value}}}，由 real.snapshot/restore 维护
        self._store = {}
        page.on("dialog", lambda d: (self._dialogs.append(d.message), d.accept()))
        page.on("response", self._on_response)

    def _on_response(self, resp):
        if resp.status in (401, 403):
            self._unauthorized = True

    # ---------- 基础操作 ----------
    def _wait_visible(self, selector, timeout_ms=6000):
        """就绪轮询：等选择器可见即返回（--fast 用于替代固定睡等）。"""
        selector = resolve_sel(selector) or selector
        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            try:
                if self.page.locator(selector).first.is_visible():
                    return True
            except Exception:
                pass
            self.page.wait_for_timeout(FAST_POLL_MS)
        return False

    def _wait_until(self, predicate, timeout_ms=3000, poll_ms=FAST_POLL_MS):
        """轮询直到 predicate() 为真或超时，返回是否命中。

        用于把「点击后盲等 N ms 再校验」改为「校验命中即返回」——
        语义完全一致（仍然校验最终状态），只是不再死等固定时长。
        poll_ms 供断言类动作按用例声明的采样间隔调整（默认沿用就绪轮询间隔）。
        """
        deadline = time.time() + timeout_ms / 1000.0
        while True:
            try:
                if predicate():
                    return True
            except Exception:
                pass
            if time.time() >= deadline:
                return False
            self.page.wait_for_timeout(poll_ms)

    _READY_JS = """() => {
        const mask = Array.from(document.querySelectorAll('.el-loading-mask'))
            .some(m => m.getBoundingClientRect().width > 0);
        if (mask) return false;
        const forms = Array.from(document.querySelectorAll('.el-form'))
            .filter(f => f.getBoundingClientRect().width > 0);
        return forms.length > 0;
    }"""

    def _wait_ready(self, timeout_ms=8000):
        """就绪轮询：等目标页表单渲染完成且 loading 遮罩消失。

        超时不算失败（部分页面无 el-form，如列表页），交由后续断言的轮询兜底。
        """
        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            try:
                if self.page.evaluate(self._READY_JS):
                    return True
            except Exception:
                pass
            self.page.wait_for_timeout(FAST_POLL_MS)
        return False

    _LOADING_MASK_JS = """() => Array.from(document.querySelectorAll('.el-loading-mask'))
        .some(m => m.getBoundingClientRect().width > 0)"""

    def _wait_page_loaded(self, timeout_ms=8000, observe_ms=600, quiet_ms=300):
        """等目标页「首屏数据落地」——比 _wait_ready 可靠的就绪信号。

        为什么需要它（2026-09-18 全量回归 15 条「点了 Add 表单不出现」的根因）：
        老 UI 页面统一在 ``created()`` 里 ``openLoading()``、在 ``getData`` 回调开头
        ``closeLoading()``（ddns / portMapping / dmz / internetSettings 均如此）。
        而 ``_READY_JS`` 要求存在**可见**的 ``.el-form``——DDNS / 端口映射 / DMZ 这类
        页面唯一的表单就是 Add 表单，默认 ``v-show="visibleflag==true"`` 隐藏，
        于是 ``_wait_ready`` 永远等不到（日志表现为「就绪=False」白等到超时）。
        --fast 早先对「二级菜单（无 l3）」只 ``wait_for_timeout(150)``，页面数据仍在路上
        就继续操作，便会踩到页面自身的竞态：数据回调重建列表 → el-table
        ``@current-change`` 触发 ``editForm`` → 列表为空时 ``visibleflag=false`` 把刚展开的
        表单重新隐藏（ddns.js 的 addForm/editForm 即此实现），或表单区块尚未渲染
        （WAN 页 #fhId_ServiceList 直接找不到）。

        判据：遮罩出现 → 消失并静默 quiet_ms（多段数据请求会重置静默计时）。
        观察窗内始终未见遮罩（少数页面未用 openLoading）时，退回原有
        「等 .el-form 渲染（最多 2s）」的旧行为兜底，不做无遮罩的长盲等。
        """
        t0 = time.time()
        deadline = t0 + timeout_ms / 1000.0
        seen = False
        quiet_since = None
        while time.time() < deadline:
            try:
                masking = bool(self.page.evaluate(self._LOADING_MASK_JS))
            except Exception:
                masking = False
            if masking:
                seen, quiet_since = True, None
            elif seen:
                if quiet_since is None:
                    quiet_since = time.time()
                elif (time.time() - quiet_since) * 1000 >= quiet_ms:
                    return True
            elif (time.time() - t0) * 1000 >= observe_ms:
                break  # 该页未使用 loading 遮罩 → 走旧兜底
            self.page.wait_for_timeout(FAST_POLL_MS)
        if not seen:
            return self._wait_ready(2000)
        return False

    # 会话复用：run 开始时登录一次并存 storage_state，其余用例以该状态建 context，
    # 免去每条用例重复走登录表单（会话失效时 ensure_login 会自动重登并刷新存档）。
    _STATE_PATH = None

    def _save_session_state(self):
        """登录成功后刷新会话存档。

        作用有二：① 首次登录后立即建立存档，后续用例即可复用（不必再逐条登录）；
        ② 会话被登出类用例销毁后，下一次重登写回新存档，避免后续用例拿到失效 cookie。
        仅在登录成功时调用（expect=False 的负向登录不会污染存档）。
        """
        if not (SESSION_REUSE and IntlSession._STATE_PATH):
            return
        try:
            self.page.context.storage_state(path=IntlSession._STATE_PATH)
        except Exception:
            pass

    def _goto(self, url, timeout=20000, wait_until="domcontentloaded", attempts=3):
        """导航；对瞬时网络故障（ERR_ABORTED / ERR_CONNECTION_RESET 等）自动重试。

        网关偶发中断一次导航属环境抖动而非用例缺陷（真机实测 2026-09-18 全量回归
        出现一次 goto login.html ERR_ABORTED，同时刻本机外网也不可达）。仅对
        `_TRANSIENT_NET` 中列出的错误码重试，其余异常（超时、选择器等）原样抛出，
        不掩盖真实缺陷。退避 1s → 2s，共 attempts 次。
        """
        for k in range(attempts):
            try:
                return self.page.goto(url, timeout=timeout, wait_until=wait_until)
            except PWError as e:
                if not any(t in str(e) for t in _TRANSIENT_NET):
                    raise
                if k >= attempts - 1:
                    raise
                print(f"[net] 导航瞬时失败（第 {k + 1}/{attempts} 次）：{str(e).splitlines()[0][:120]} —— 重试")
                self.page.wait_for_timeout(1000 * (k + 1))

    def ensure_login(self):
        """确保当前 context 已登录：会话有效则直达主页，失效则完整登录一次。"""
        self._goto(f"{BASE_URL}/main.html")
        if FAST_MODE:
            self._wait_ready(6000)
        else:
            self.page.wait_for_timeout(_ms(2500))
        if "login.html" in self.page.url:
            self._goto(f"{BASE_URL}/login.html")
            self.page.wait_for_timeout(_ms(800) if FAST_MODE else _ms(2500))
            # 会话曾被登出销毁：重登由 login() 内部写回新存档，保证后续用例仍可复用
            self.login()
        return True

    def open_page(self, route, l1=None, l2=None, l3=None, expect=None):
        """深链直达目标页：一次 goto 取代「进主页 + 三级菜单点击」。

        老 UI 是 hash SPA，路由 #/network/wifiSettings/wifiBasic 可直接挂载目标页
        （真机实测 380ms 就绪，对比三级菜单点击约 7s）。落地路由与预期不符或页面
        未就绪时，自动回退到原三级菜单点击，保证与既有链路语义一致、不会因深链
        失效而误判（其他套件路由命名不同时同样走回退，零风险）。
        """
        self.page.goto(f"{BASE_URL}/main.html#{route}", timeout=20000, wait_until="domcontentloaded")
        # 就绪判定用「首屏数据落地」（loading 遮罩周期）而非「存在可见 .el-form」：
        # 后者在「唯一表单是 v-show 隐藏的 Add 表单」页面（DDNS/端口映射/DMZ/静态 IP）
        # 永远为假，会让已正确落地的深链被误判为未就绪而白跑一遍三级菜单回退
        #（真机实测 INTL-LAN-012 因此多耗约 7s）。观察窗放宽到 2.5s 以覆盖
        # 深链下 SPA 模块加载 + 组件挂载的耗时。
        ready = self._wait_page_loaded(6000, observe_ms=2500)
        if "login.html" in self.page.url:
            # 会话被登出类用例销毁：完整登录一次（login() 内部写回新存档），再深链
            self.page.goto(f"{BASE_URL}/login.html", timeout=20000, wait_until="domcontentloaded")
            self._wait_visible("#user_name", 6000)
            self.login()
            self.page.goto(f"{BASE_URL}/main.html#{route}", timeout=20000,
                           wait_until="domcontentloaded")
            ready = self._wait_page_loaded(6000, observe_ms=2500)
        landed = (self.page.url.split("#")[-1] or "").rstrip("/")
        if ready and landed == route.rstrip("/"):
            return True
        print(f"[fast] 深链 {route} 未按预期落地（实际 {landed}，就绪={ready}），回退三级菜单点击")
        try:
            self.click_menu(l1, l2, l3)
        except PWTimeout as e:
            # 回退时菜单项不存在 = 设备无此页面，交由执行器按「页面/菜单不存在」跳过
            raise MenuMissing(str(e)) from e
        return True

    def navigate(self, path):
        url = BASE_URL if path in ("/", "") else BASE_URL + path
        self.page.goto(url, timeout=20000, wait_until="domcontentloaded")
        if FAST_MODE:
            # 登录页等表单出现；其余页面等表单就绪（免盲等 2.5s）
            if "login.html" in url:
                self._wait_visible("#user_name", 6000)
            else:
                self._wait_ready(6000)
        else:
            self.page.wait_for_timeout(2500)

    def navigate_spa(self, route):
        self.page.goto(f"{BASE_URL}/main.html#{route}", timeout=20000, wait_until="domcontentloaded")
        if FAST_MODE:
            self._wait_ready(6000)
        else:
            self.page.wait_for_timeout(2500)

    def click_menu(self, l1=None, l2=None, l3=None):
        if l1:
            self.page.click(f"#{l1}", timeout=8000)
            if FAST_MODE:
                # 一级菜单展开后等二级项可点（未给 l2 则短等）
                if l2:
                    self._wait_visible(f"#{l2}", 3000)
                else:
                    self.page.wait_for_timeout(FAST_POLL_MS)
            else:
                self.page.wait_for_timeout(1200)
        if l2:
            self.page.click(f"#{l2}", timeout=8000)
            if FAST_MODE:
                if l3:
                    self._wait_visible(f"#{l3}", 3000)
                else:
                    # 二级菜单（无 l3）落到的默认子页同样要等首屏数据落地：
                    # 原先只等 FAST_POLL_MS=150ms，页面数据还在路上就继续点 Add，
                    # 会踩到「数据回调重建列表 → editForm 隐藏表单」的竞态
                    #（2026-09-18 全量回归 15 条失败根因）。
                    self._wait_page_loaded(8000)
            else:
                self.page.wait_for_timeout(2000)
        if l3:
            self.page.click(f"#{l3}", timeout=8000)
            if FAST_MODE:
                # 等首屏数据落地（原固定睡等 3s；原 _wait_ready 对「表单默认隐藏」的
                # 页面永远等不到，白耗满 8s，如 INTL-LAN-012 的 staticIPSettings）
                self._wait_page_loaded(8000)
            else:
                self.page.wait_for_timeout(3000)

    def fill(self, selector, value):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        loc.scroll_into_view_if_needed()
        loc.fill(value)

    def clear_select(self, selector):
        """把 el-select 置为「未选择」态并触发 change（构造必填校验场景）。

        老用例走 `vm.$emit('input',''); vm.$emit('change','')`：直接改
        input.value 不会让 ElementUI 重新校验，必须打组件事件。仅用于刻意构造
        非法前端态的用例（如「下拉空值时 Apply 应被拦截」）。取不到组件实例即
        失败，不静默放过——否则后续「Apply 被拦截」的断言会变成假绿。
        """
        sel = resolve_sel(selector) or selector
        self.page.locator(sel).first.wait_for(state="attached", timeout=8000)
        ok = self.page.evaluate("""(s) => {
            const el = document.querySelector(s);
            if (!el) return false;
            const root = el.classList.contains('el-select') ? el : el.closest('.el-select');
            const vm = el.__vue__ || (root && root.__vue__);
            if (!vm) return false;
            vm.$emit('input', '');
            vm.$emit('change', '');
            return true;
        }""", sel)
        if not ok:
            raise AssertionError(
                f"未取到下拉组件实例，无法构造「未选择」态：{selector}")
        return True

    def set_input_files(self, selector, path):
        """文件选择：针对 <input type=file>（如 el-upload 的隐藏 input），不弹原生对话框"""
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="attached", timeout=8000)
        loc.set_input_files(path)

    # ElementUI 原生控件视觉隐藏时的可视包装层（按真机页面代码逐族补齐：
    # el-switch 的 checkbox 隐藏 input → div.el-switch；el-radio 的 radio 隐藏
    # input（el-radio__original）→ label.el-radio）
    _EL_NATIVE_WRAPPER = (
        ("e => e.tagName === 'INPUT' && e.type === 'checkbox'"
         " && e.classList.contains('el-switch__input')", "div.el-switch"),
        ("e => e.tagName === 'INPUT' && e.type === 'radio'"
         " && e.classList.contains('el-radio__original')", "label.el-radio"),
    )

    def _el_native_wrapper(self, sel):
        """id/类挂在 ElementUI 视觉隐藏的原生控件上时，返回可视容器 locator
        （first 防同 id 双渲染）；目标不是同族隐藏原生控件或容器不存在时返回 None。"""
        loc = self.page.locator(sel)
        n = loc.count()
        if n == 0:
            return None
        for js_check, wrap_css in self._EL_NATIVE_WRAPPER:
            if loc.first.evaluate(js_check):
                for i in range(1, min(n, 3)):
                    if not loc.nth(i).evaluate(js_check):
                        return None
                wrap = self.page.locator(f"{wrap_css}:has({sel})")
                return wrap.first if wrap.count() else None
        return None

    def click(self, selector):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        wrapper = self._el_native_wrapper(sel)
        if wrapper is not None:
            # 隐藏原生控件过不了可见性检查，直接点可视容器（语义=切换开关/选单选项）
            wrapper.wait_for(state="visible", timeout=8000)
            wrapper.scroll_into_view_if_needed()
            wrapper.click(force=True)
            return True
        loc.wait_for(state="visible", timeout=8000)
        loc.scroll_into_view_if_needed()
        # 焦点仍在输入框时先失焦再点，否则设备端失焦校验/重渲染流程会吞掉本次点击
        #（WAN-007 根因，原仅限复选框/单选框；APP-114/115 Apply 同族证据：同值手动保存成功、
        # 自动化步骤 PASS 但 8s 轮询内保存从未发生 → 泛化到所有点击，失焦后才等 300ms）
        blurred = self.page.evaluate(
            "() => { const ae = document.activeElement;"
            " if (ae && /^(INPUT|TEXTAREA)$/.test(ae.tagName)) { ae.blur(); return true; }"
            " return false; }")
        if blurred:
            self.page.wait_for_timeout(_ms(300))
        loc.click(force=True)

    def wait(self, ms):
        self.page.wait_for_timeout(_ms(ms))

    # ---------- 登录/登出 ----------
    def login(self, role="admin", expect=True):
        # 凭据来自 .env：admin 用 QCT_INTL_ADMIN_*，其余角色用 QCT_INTL_USER_*（勿硬编码密码）
        self._role = role  # 供会话超时自愈时按原角色重登（见 heal_login_timeout）
        username = ADMIN_USER if role == "admin" else USER_USER
        password = ADMIN_PASS if role == "admin" else USER_PASS
        self.page.fill("#user_name", username)
        self.page.fill("#loginpp", password)
        self.page.click("#login_btn")
        # --fast：直接等跳转完成（wait_for_url 命中即返回），不先盲等 3s
        if not FAST_MODE:
            self.page.wait_for_timeout(3000)
        if expect:
            self.page.wait_for_url(re.compile(r"main\.html#/"), timeout=15000)
            # 登录成功即刷新会话存档：后续用例可直接复用，无需再逐条登录
            self._save_session_state()
            return True
        else:
            return "/login.html" in self.page.url

    # 设备端会话过期弹窗：<el-message-box> 内含 "Login timeout, please log in again!"
    # 注意：可见性判定**不能用 offsetParent**——ElementUI 的 message-box 是
    # `position: fixed`，而 fixed 元素的 offsetParent 恒为 null，会导致永远检不出
    #（2026-09-18 用忠实 DOM 复刻的探针抓到）；改用 computed style + 边界盒。
    _LOGIN_TIMEOUT_JS = """() => {
        const shown = (el) => {
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') === 0) return false;
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        };
        const boxes = Array.from(document.querySelectorAll('.el-message-box, .el-dialog, .el-message'));
        for (const b of boxes) {
            if (shown(b) && /login\\s*timeout/i.test(b.innerText || '')) return true;
        }
        return false;
    }"""

    def heal_login_timeout(self):
        """自愈「设备端会话超时」：关弹窗 → 整页回登录页 → 按原角色重登。

        老 UI 在会话过期时弹「Warning / Login timeout, please log in again!」
        模态框，其遮罩会挡住页面元素，使后续断言/点击**全部超时**（真机实测
        INTL-LAN-015 第 14 步重进页面后断言 #fhId_DHCPHours 不可见，失败截图
        即该弹窗；20.3s 全是等待）。若不处理，会把设备侧会话过期误判成用例缺陷。

        仅对 admin 会话自愈：非 admin（普通用户越权类用例）重登会写回 admin
        会话存档，污染后续用例的复用会话，故直接返回 False 交由原逻辑失败。
        返回是否发生了自愈。
        """
        if getattr(self, "_role", "admin") != "admin":
            return False
        try:
            if not self.page.evaluate(self._LOGIN_TIMEOUT_JS):
                return False
        except Exception:
            return False
        # 关弹窗：ElementUI message-box 的确定按钮文案为 "OK"；点不到也不阻塞，
        # 下一步整页回登录页会连弹窗一起丢掉
        try:
            self.page.get_by_role("button", name="OK").first.click(timeout=3000)
        except Exception:
            pass
        # 会话已失效：整页回登录页并完整登录一次（login() 内部写回新会话存档）
        self.page.goto(f"{BASE_URL}/login.html", timeout=20000, wait_until="domcontentloaded")
        self.page.wait_for_timeout(_ms(800) if FAST_MODE else _ms(2500))
        self.login()
        return True

    def logout(self):
        # 优先适配 HG6163FC1：头部 div.fh-logout 内的 <a>Logout</a> + Confirm 按钮；
        # 注意：点击事件绑在内层 <a> 上，点外层 div 不会触发退出。
        # 兼容旧版下拉式退出（.el-dropdown-link.header_admin + #fhId_logout）
        try:
            direct = self.page.locator(".fh-logout a")
            if direct.count() and direct.first.is_visible():
                direct.first.click()
            else:
                self.page.click(".el-dropdown-link.header_admin", timeout=8000)
                self.page.wait_for_timeout(_ms(1000))
                self.page.click("#fhId_logout", timeout=8000)
            self.page.wait_for_timeout(_ms(1500))
            # 处理退出确认框（"Exit confirmation"：ElementUI message-box，优先选 primary 按钮；
            # 兼容旧版文本 Confirm/OK 按钮）
            primary = self.page.locator(".el-message-box:visible .el-button--primary")
            if primary.count() and primary.first.is_visible():
                primary.first.click()
            else:
                handled = False
                box = self.page.locator(".el-message-box:visible")
                if box.count():
                    box.locator("button").last.click()
                    handled = True
                else:
                    for cand in ("text=Confirm", "text=OK", "text=确定"):
                        btn = self.page.locator(f"button:has({cand})")
                        if btn.count() and btn.first.is_visible():
                            btn.first.click()
                            handled = True
                            break
                if not handled:
                    raise AssertionError("未找到退出确认按钮")
            self.page.wait_for_timeout(_ms(2500))
            self.page.wait_for_url(re.compile(r"login\.html"), timeout=15000)
            return True
        except Exception:
            print("[warn] logout 未正常完成，回退为直接跳转登录页（设备端会话可能未注销，影响后续未授权用例）")
            self.page.goto(f"{BASE_URL}/login.html", timeout=15000)
            self.page.wait_for_timeout(_ms(1500))

    # ---------- 断言 ----------
    def assert_visible(self, selector):
        sel = resolve_sel(selector) or selector
        # --fast 快路径：老 UI 常把 id 挂在视觉隐藏的原生控件上（el-switch / el-radio
        # 的内层 input，如 #fhId_Enable），直接对原生控件 wait_for(visible) 会白等满
        # 15s 超时才回退到容器层（真机实测 INTL-WIFI-001 因此多耗约 15s）。
        # 先用一次非阻塞 JS 预判：原生控件可见、或「同族隐藏原生控件 + 容器可见」→ 立即
        # 通过；未命中再走原来的「等待 + 容器回退」逻辑。判据与 _EL_NATIVE_WRAPPER
        # 严格一一对应，不放宽任何一条，确保不会把本该失败的断言放过去。
        if FAST_MODE:
            try:
                if self.page.evaluate("""(s) => {
                        const vis = (n) => { if (!n) return false;
                            const r = n.getBoundingClientRect();
                            return r.width > 0 && r.height > 0; };
                        const el = document.querySelector(s);
                        if (!el) return false;
                        if (vis(el)) return true;
                        let wrap = null;
                        if (el.tagName === 'INPUT' && el.type === 'checkbox'
                            && el.classList.contains('el-switch__input')) wrap = 'div.el-switch';
                        else if (el.tagName === 'INPUT' && el.type === 'radio'
                            && el.classList.contains('el-radio__original')) wrap = 'label.el-radio';
                        if (!wrap) return false;
                        return vis(el.closest(wrap));
                    }""", sel):
                    return True
            except Exception:
                pass  # selector 含 Playwright 专有伪类（:has-text 等）时 querySelector 不可用，走原逻辑
        try:
            self.page.locator(sel).wait_for(state="visible", timeout=15000)
            return True
        except PWTimeout:
            # ElementUI 组件：id 挂在视觉隐藏的原生控件上时，回退断言可视容器层；
            # 容器也不可见/不存在时照旧失败
            wrapper = self._el_native_wrapper(sel)
            if wrapper is not None:
                wrapper.wait_for(state="visible", timeout=15000)
                return True
            raise
        except Exception as e:
            if "strict mode violation" in str(e):
                # 多匹配（文本/重复 id selector 一拖多）兜底：wait_for 遇多匹配立即
                # 抛 strict violation，取首个等可见；首个也不可见时照旧失败
                elements = self.page.locator(sel).all()
                if elements:
                    elements[0].wait_for(state="visible", timeout=15000)
                    return True
            raise

    def assert_hidden(self, selector):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        if loc.count() == 0:
            return True
        try:
            loc.wait_for(state="hidden", timeout=5000)
            return True
        except PWTimeout:
            return False

    def assert_url_contains(self, substring):
        self.page.wait_for_url(re.compile(re.escape(substring)), timeout=10000)
        return True

    def assert_input_value(self, selector, value):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        return str(loc.input_value()) == str(value)

    def assert_input_value_not(self, selector, value):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        return str(loc.input_value()) != str(value)

    def skip_if_filled(self, selector, steps):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        value = str(loc.input_value() or "").strip()
        if value:
            self._skip_next = int(steps)
        return True

    # ---------- 开关 / 可编辑性 / 选项存在性（环境受限用例的 SKIP 前置）----------
    def _switch_state(self, sel):
        """读取 el-switch 开/关：优先 is-checked 类，回退内部 checkbox.checked。不可读返回 None。"""
        return self.page.evaluate("""(s) => {
            const el = document.querySelector(s);
            if (!el) return null;
            const sw = el.classList.contains('el-switch') ? el : el.closest('.el-switch');
            if (sw) return sw.classList.contains('is-checked');
            const inp = el.querySelector('input[type=checkbox]');
            return inp ? !!inp.checked : null;
        }""", sel)

    def set_switch(self, selector, on=True):
        """把 el-switch 幂等设为指定状态（已是目标态则不动）。

        用于无线开关这类"用例要求先处于某状态"的控件：单纯 click 是切换语义，
        设备残留状态不同会让同一用例时对时错。切换后复读校验，读不到状态即失败。
        """
        sel = resolve_sel(selector) or selector
        # 老 UI 的 setItemId('Enable') 把 id 挂在 el-switch 内层真实 checkbox 上
        # （<input class="el-switch__input">），该 input 被 ElementUI 隐藏（opacity/尺寸为 0）。
        # 因此这里不能等「目标可见」，只能等「已挂载」，再改为点击可见的 .el-switch 包装元素。
        self.page.locator(sel).first.wait_for(state="attached", timeout=8000)
        cur = self._switch_state(sel)
        if cur is None:
            raise AssertionError(f"开关 {selector} 状态不可读（不是 el-switch 控件？）")
        if cur == bool(on):
            return True
        # 用临时属性标记可见的 .el-switch 包装元素（真实 input 不可点），点完即清理
        marker = "data-fh-switch-click"
        marked = self.page.evaluate("""([s, m]) => {
            document.querySelectorAll('[' + m + ']').forEach(n => n.removeAttribute(m));
            const el = document.querySelector(s);
            if (!el) return false;
            const sw = el.classList.contains('el-switch') ? el : el.closest('.el-switch');
            if (!sw) return false;
            sw.setAttribute(m, '1');
            return true;
        }""", [sel, marker])
        if not marked:
            raise AssertionError(f"开关 {selector} 找不到可点击的 el-switch 包装元素")
        target = self.page.locator(f"[{marker}]").first
        try:
            target.wait_for(state="visible", timeout=8000)
            target.scroll_into_view_if_needed()
            target.click()
        finally:
            self.page.evaluate("(m) => { document.querySelectorAll('[' + m + ']')"
                               ".forEach(n => n.removeAttribute(m)); }", marker)
        # 轮询等开关状态生效（命中即返回，最长 2.5s；替代盲等 1s）
        self._wait_until(lambda: self._switch_state(sel) == bool(on), 2500)
        if self._switch_state(sel) != bool(on):
            raise AssertionError(f"开关 {selector} 切换后状态不符，期望 {'开' if on else '关'}")
        return True

    def _checkbox_state(self, sel):
        """读取 el-checkbox 勾选态：id 常挂在隐藏的内层真实 checkbox 上。不可读返回 None。"""
        return self.page.evaluate("""(s) => {
            const el = document.querySelector(s);
            if (!el) return null;
            const i = (el.tagName === 'INPUT') ? el : el.querySelector('input');
            return i ? !!i.checked : null;
        }""", sel)

    def click_checkbox(self, selector, on=None, state_from=None, field=None):
        """幂等设置 el-checkbox 勾选态（或 on=None 时纯切换并校验状态变化）。

        与 set_switch 同源问题：老 UI setItemId('X') 把 id 挂在 el-checkbox 内层
        隐藏的真实 input 上，直接点击会超时；须点击可见的 .el-checkbox 包装元素。
        state_from/field：从 localStorage 记录值读取目标态（用于"恢复原状态"
        的清理步骤，原状态只有在运行期才知道，无法写死在 JSON 里）。
        """
        sel = resolve_sel(selector) or selector
        self.page.locator(sel).first.wait_for(state="attached", timeout=8000)
        if state_from:
            on = self.page.evaluate(
                """([k, f]) => {
                    let o = null;
                    try { o = JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) {}
                    if (!o) o = window['__' + k] || null;
                    if (!o || o[f] === undefined || o[f] === null) throw new Error('记录值 ' + k + '.' + f + ' 缺失，无法恢复');
                    return !!o[f];
                }""", [state_from, field])
        cur = self._checkbox_state(sel)
        if cur is None:
            raise AssertionError(f"复选框 {selector} 状态不可读（不是 el-checkbox 控件？）")
        if on is not None and cur == bool(on):
            return True
        marker = "data-fh-checkbox-click"
        marked = self.page.evaluate("""([s, m]) => {
            document.querySelectorAll('[' + m + ']').forEach(n => n.removeAttribute(m));
            const el = document.querySelector(s);
            if (!el) return false;
            const box = el.classList.contains('el-checkbox') ? el : el.closest('.el-checkbox');
            if (!box) return false;
            box.setAttribute(m, '1');
            return true;
        }""", [sel, marker])
        if not marked:
            raise AssertionError(f"复选框 {selector} 找不到可点击的 el-checkbox 包装元素")
        target = self.page.locator(f"[{marker}]").first
        try:
            target.wait_for(state="visible", timeout=8000)
            target.scroll_into_view_if_needed()
            target.click()
        finally:
            self.page.evaluate("(m) => { document.querySelectorAll('[' + m + ']')"
                               ".forEach(n => n.removeAttribute(m)); }", marker)
        # 轮询等勾选态变化（命中即返回，最长 2.5s；替代盲等 0.8s）
        self._wait_until(lambda: self._checkbox_state(sel) != cur, 2500)
        new = self._checkbox_state(sel)
        if on is not None and new != bool(on):
            raise AssertionError(f"复选框 {selector} 未能置为 {'勾选' if on else '取消'}态，当前={new}")
        if on is None and new == cur:
            raise AssertionError(f"复选框 {selector} 点击后状态未变化")
        return True

    def select_option_dynamic(self, selector, key, field):
        """按运行期记录值恢复 el-select：从 localStorage/window 读取 label 后真实点选。

        用于"记录原值 → 变更 → 恢复原值"类用例中 el-select 的恢复段——
        原值只有运行期才知道，无法写成静态 option_text；直接 evaluate 改
        input.value 又不会更新 Vue model。本动作展开面板后用 Playwright
        真实点击匹配 label 的选项（合成点击收不起 clickoutside，真实事件才有效），
        已是目标值时幂等跳过，选完复读校验。
        """
        sel = resolve_sel(selector) or selector
        label = self.page.evaluate(
            """([k, f]) => {
                let o = null;
                try { o = JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) {}
                if (!o) o = window['__' + k] || null;
                if (!o || o[f] === undefined || o[f] === null) throw new Error('记录值 ' + k + '.' + f + ' 缺失，无法恢复');
                return String(o[f]);
            }""", [key, field])
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        try:
            if (loc.input_value() or "").strip() == label:
                return True
        except Exception:
            pass
        loc.click()
        self.page.wait_for_timeout(FAST_POLL_MS if FAST_MODE else 1200)
        panel = self.page.locator(".el-select-dropdown:visible").last
        panel.wait_for(state="visible", timeout=5000)
        item = panel.get_by_text(label, exact=True).first
        item.click()
        self.page.wait_for_timeout(_ms(1200))
        cur = (loc.input_value() or "").strip()
        if cur != label:
            raise AssertionError(f"动态恢复下拉 {selector} 失败：期望 {label!r}，实际 {cur!r}")
        return True

    def _is_disabled(self, sel):
        el_disabled = self.page.evaluate("""(s) => {
            const el = document.querySelector(s);
            if (!el) return false;
            const inner = el.querySelector('input, textarea');
            return el.disabled === true || (inner && inner.disabled === true)
                || el.classList.contains('is-disabled') || !!el.closest('.is-disabled');
        }""", sel)
        return bool(el_disabled)

    def probe_disabled(self, selectors, label=None):
        """记录一组控件的可编辑性（只打印到日志，不做断言）。

        用于「行为固化」类步骤：控件是否置灰随局方/机型而变，用例只留痕供报告
        核对，不把观察结果当缺陷判失败（老用例把它写进 window.__closeState，
        报告里根本读不到，等于白记）。判据复用 _is_disabled，不另立标准。
        """
        pairs = []
        for raw in selectors:
            sel = resolve_sel(raw) or raw
            if self.page.locator(sel).count() == 0:
                pairs.append(f"{raw}=不存在")
                continue
            pairs.append(f"{raw}={'禁用' if self._is_disabled(sel) else '可编辑'}")
        print(f"[info] probe {label or 'disabled'}: " + "; ".join(pairs))
        return True

    def skip_if_disabled(self, selector, steps):
        """控件为禁用态时跳过后续 steps 步。

        用于"可编辑性随局方/机型变化"的用例（如 Domain 仅 5 类 COMMON 局方可改）：
        不可编辑属环境差异，判定 SKIP 而非 FAIL。
        """
        sel = resolve_sel(selector) or selector
        self.page.locator(sel).first.wait_for(state="visible", timeout=8000)
        if self._is_disabled(sel):
            print(f"[info] skip_if_disabled: {selector} 为禁用态，跳过后续 {steps} 步")
            self._skip_next = int(steps)
        return True

    def skip_if_option_absent(self, selector, option_text, steps):
        """下拉中不存在指定选项时跳过后续 steps 步（机型/局方能力差异，如 11ax 制式）。

        区别于 select_option：后者在选项缺失时抛超时异常判 FAIL，本动作把它降级为 SKIP。
        """
        sel = resolve_sel(selector) or selector
        self.page.locator(sel).first.wait_for(state="visible", timeout=8000)
        if not self.assert_option_present(sel, option_text):
            print(f"[info] skip_if_option_absent: {selector} 无选项 {option_text!r}，跳过后续 {steps} 步")
            self._skip_next = int(steps)
        return True

    def _blur_active_input(self):
        """若焦点仍在输入框则主动失焦。

        真机（HG6163FC1 等）ElementUI 表单校验触发时机为 blur：用例常见的
        fill → wait → assert 序列不会产生 blur，校验提示永不渲染，导致负向
        用例被误判为失败（实测：手动失焦后 'Please enter 8-32 characters.' 等
        提示立即出现且文案与用例预期一致）。故断言前统一补一次失焦。
        """
        try:
            return bool(self.page.evaluate(
                "() => { const ae = document.activeElement;"
                " if (ae && /^(INPUT|TEXTAREA)$/.test(ae.tagName)) { ae.blur(); return true; }"
                " return false; }"))
        except Exception:
            return False

    def assert_text_contains(self, selector, text):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        actual = loc.inner_text() or ""
        if text in actual:
            return True
        # 首判未命中：先补一次失焦触发 blur 校验，再轮询等待提示渲染；
        # 提示确实不存在（真实缺陷）时仍会失败，不会掩盖问题。
        if self._blur_active_input():
            for _ in range(6):
                self.page.wait_for_timeout(_ms(500))
                actual = self.page.locator(sel).inner_text() or ""
                if text in actual:
                    return True
        raise AssertionError(f"text {text!r} not found in {selector}, actual: {actual[:120]!r}")

    def assert_text_not_contains(self, selector, text):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        actual = loc.inner_text() or ""
        if text in actual:
            raise AssertionError(f"text {text!r} unexpectedly found in {selector}")
        return True

    def assert_html_not_contains(self, selector, texts):
        """断言元素「源码 HTML」不含给定子串（assert_text_not_contains 的源码版）。

        与 assert_text_not_contains 的差别在读取口径：后者读渲染后的 inner_text，
        若 payload 真被解析成 <img onerror=...> 元素，它的属性不会出现在
        inner_text 里，断言会「假通过」。本动作读 innerHTML，专用于安全类用例
        验证「注入串没有被反射进 DOM 源码」。

        texts：子串列表，任一命中即失败。
        """
        sel = resolve_sel(selector) or selector
        self.page.locator(sel).first.wait_for(state="attached", timeout=8000)
        html = self.page.evaluate(
            "(s) => { const el = document.querySelector(s);"
            " return el ? (el.innerHTML || '') : ''; }", sel)
        hit = [t for t in (texts or []) if t in html]
        if hit:
            raise AssertionError(
                f"源码含不应出现的片段：{selector} 命中 {hit}")
        return True

    def _login_error_hint(self):
        # HG6163FC1 为 class（div.login_error_hint），旧版为 id（#login_error_hint）
        for sel in (".login_error_hint", "#login_error_hint"):
            loc = self.page.locator(sel)
            if loc.count():
                return loc.first
        return self.page.locator("#login_error_hint")

    def assert_login_error(self):
        self._login_error_hint().wait_for(state="visible", timeout=8000)
        return True

    def assert_login_stays(self):
        # 空用户名/空密码等前端校验拦截：停留登录页且错误提示隐藏
        if "/login.html" not in self.page.url:
            return False
        err = self._login_error_hint()
        if err.count() == 0:
            return True
        return not err.is_visible()

    def assert_element(self, selector):
        return self.assert_visible(selector)

    def assert_page(self, component="main"):
        self.page.locator("#app").wait_for(state="visible", timeout=8000)
        return True

    # ---------- 下拉 ----------
    def select_option(self, selector, option_text):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        # ElementUI 下拉的只读输入框 value 即当前选中项文本：已是目标值就跳过展开面板
        #（真机"启用规则"默认已选 Enable，APP-114/115 实锤再点面板不展开）
        try:
            if loc.input_value().strip() == option_text:
                return True
        except Exception:
            pass
        blurred = self.page.evaluate(
                    "() => { const ae = document.activeElement;"
                    " if (ae && /^(INPUT|TEXTAREA)$/.test(ae.tagName)) { ae.blur(); return true; }"
                    " return false; }")
        if blurred:
                    self.page.wait_for_timeout(_ms(300))
        loc.click()
        # 面板展开是异步动画：交给下面 panel.wait_for 轮询，不必盲等 1.5s
        self.page.wait_for_timeout(FAST_POLL_MS if FAST_MODE else 1500)                                  # ← 加这里：先等面板展开
        # 页面上所有下拉的面板常驻 DOM，收起的面板选项是隐藏的；全局 :has-text 会命中别处
        # 关闭面板里的同名选项（APP-114/115：14 个 'Enable' 选项全隐藏）。只在展开的面板里找。
        panel = self.page.locator(".el-select-dropdown:visible").first
        panel.wait_for(state="visible", timeout=5000)
        # 前置条件判定：面板已展开但一个可选项都没有 → 当前设备状态下用例不具备
        # 可执行条件（典型：设备未开通 WAN 业务，接口/服务下拉为空），判定 SKIP
        # 而非 FAIL，避免把环境受限误报为产品缺陷。
        if panel.locator(".el-select-dropdown__item").count() == 0:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(_ms(300))
            raise PreconditionBlocked(
                f"下拉 {selector} 展开后无可选项（设备未开通相关业务/接口，环境受限）")
        opt = panel.locator(f".el-select-dropdown__item:has-text('{option_text}')").first
        opt.wait_for(state="visible", timeout=5000)
        opt.click()
        self.page.wait_for_timeout(_ms(500))
        return True

    def assert_option_present(self, selector, option_text):
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        loc.click()
        self.page.wait_for_timeout(_ms(800))
        opts = self.page.locator(".el-select-dropdown__item")
        texts = [o.inner_text().strip() for o in opts.all() if o.is_visible()]
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(_ms(400))
        return option_text in texts

    # ---------- 时间范围选择 ----------
    def select_time_range(self, selector, start, end):
        """通用时间范围选择：点开时间弹层，按参数点选开始/结束的时与分，点 OK 确认。
        时间值由用例传入（start/end 如 "00:00"/"23:59"），改值只改用例，无需改执行器。"""
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        loc.wait_for(state="visible", timeout=8000)
        loc.click()
        self.page.wait_for_timeout(600)
        picker = self.page.locator(".el-time-range-picker:visible")
        picker.wait_for(state="visible", timeout=5000)
        for cell_idx, value in ((0, start), (1, end)):
            hh, mm = value.split(":")
            cell = picker.locator(".el-time-range-picker__cell").nth(cell_idx)
            wrappers = cell.locator(".el-time-spinner__wrapper:visible")
            for col_idx, label in ((0, hh), (1, mm)):
                li = wrappers.nth(col_idx).locator(f'li.el-time-spinner__item:text-is("{label}")')
                li.wait_for(state="visible", timeout=5000)
                li.scroll_into_view_if_needed()
                classes = li.get_attribute("class") or ""
                if "disabled" in classes.split():
                    raise AssertionError(f"时间项 {label} 在弹层中处于禁用状态，无法选择")
                li.click()
                self.page.wait_for_timeout(200)
        confirm = picker.locator(".el-time-panel__btn.confirm")
        confirm.wait_for(state="visible", timeout=5000)
        confirm.click()
        self.page.wait_for_timeout(500)
        self.page.locator(".el-time-range-picker").wait_for(state="hidden", timeout=5000)
        return True

    # ---------- 确认框 ----------
    def delete_wan_row(self, row_text, optional=False):
        """删除 WAN 表格行：勾选行 checkbox 后点表格上方 Delete 按钮。

        HG6163FC1 无逐行删除图标（.del_wan_icon 不存在），删除统一走表格顶部按钮。
        注意：checkbox 点击是“切换”语义（已勾选再点会取消），且页面刷新/重渲染可能吞掉点击，
        因此必须幂等勾选 + 点击后验证，最终未勾选则显式失败。
        optional=True 时行不存在则静默跳过（返回 False），用于"清理旧残留（若有）"类前置步骤，
        保证用例可重复执行（如 VLAN 99 预置 WAN 用例重跑前先删旧条目）。
        """
        row = self.page.locator("tr.el-table__row", has_text=row_text)
        if optional and row.count() == 0:
            # 容错等待一次重渲染再确认（列表可能异步加载）
            self.page.wait_for_timeout(_ms(1500))
            if row.count() == 0:
                print(f"[info] optional 删除：行 {row_text} 不存在，跳过")
                return False
        row.first.wait_for(state="visible", timeout=8000)
        cb = row.first.locator(".el-checkbox")
        cb.first.wait_for(state="visible", timeout=8000)
        for _ in range(4):
            checked = cb.first.evaluate(
                "el => { const i = el.querySelector('input'); return i ? i.checked : null; }")
            if checked:
                break
            cb.first.click(force=True)
            self.page.wait_for_timeout(_ms(900))
        else:
            raise AssertionError(f"无法勾选 WAN 行 {row_text}：连续点击后 checkbox 仍未选中")
        self.page.click("#fhId_Delete", timeout=8000)
        self.page.wait_for_timeout(_ms(1200))
        return True

    def delete_wan_row_if_exists(self, row_text):
        """若 WAN 列表存在匹配 row_text 的行则删除（内部处理确认框），不存在则静默跳过。

        用于跨用例预置数据的幂等清理：如 INTL-WAN-012 预置的 VLAN 99 WAN
        刻意不删除，本用例重跑时先清理旧条目避免 VLAN 重复校验拦截。
        """
        row = self.page.locator("tr.el-table__row", has_text=row_text)
        if row.count() == 0:
            self.page.wait_for_timeout(_ms(1500))
        if row.count() == 0:
            print(f"[info] delete_wan_row_if_exists: 行 {row_text} 不存在，跳过删除")
            # 跳过删除属正常分支：返回 True（None 亦可），避免执行器把 False 判为断言失败
            return True
        self.delete_wan_row(row_text)
        box = self.page.locator(".el-message-box")
        box.wait_for(state="visible", timeout=8000)
        box.locator("button").last.click()
        self.page.wait_for_timeout(_ms(2500))
        if self.page.locator("tr.el-table__row", has_text=row_text).count():
            raise AssertionError(f"删除后行 {row_text} 仍存在")
        return True

    def delete_row_at(self, index=-1, if_count_gt=None):
        """按行号删除表格行（index 支持 -1 表示末行）。

        if_count_gt 为行数保护阈值：当前行数 <= 该值时跳过删除，
        用于"仅清理本次新增残留、不动出厂默认规则"的场景。
        """
        rows = self.page.locator("tr.el-table__row")
        n = rows.count()
        if if_count_gt is not None and n <= if_count_gt:
            return True
        if n == 0:
            raise AssertionError("表格无行可删")
        target = rows.nth(index if index >= 0 else n + index)
        cb = target.locator(".el-checkbox")
        cb.first.wait_for(state="visible", timeout=8000)
        for _ in range(4):
            checked = cb.first.evaluate(
                "el => { const i = el.querySelector('input'); return i ? i.checked : null; }")
            if checked:
                break
            cb.first.click(force=True)
            self.page.wait_for_timeout(_ms(900))
        else:
            raise AssertionError(f"无法勾选第 {index} 行：连续点击后 checkbox 仍未选中")
        self.page.click("#fhId_Delete", timeout=8000)
        self.page.wait_for_timeout(_ms(1200))
        return True

    # ---------- 确认框 ----------
    def assert_confirm_visible(self, keyword=""):
        box = self.page.locator(".el-message-box")
        box.wait_for(state="visible", timeout=8000)
        if keyword:
            return keyword in (box.inner_text() or "")
        return True

    def click_confirm(self, accept=True):
        box = self.page.locator(".el-message-box")
        box.wait_for(state="visible", timeout=8000)
        btns = box.locator("button")
        if accept:
            btns.last.click()
        else:
            btns.nth(btns.count() - 2).click()
        self.page.wait_for_timeout(_ms(1500))
        return True

    def close_boxes(self):
        """容错关闭所有可见的 ElementUI message-box（有则点最后一个按钮，无则跳过）。
        设备对 WAN 校验/保存结果常用模态弹窗提示，遮罩会拦截后续页面点击。
        """
        if FAST_MODE:
            # 保存类用例前置等待被缩短，弹窗可能尚未出现：先轮询最多 2.5s 等它出现，
            # 避免漏关导致遮罩拦截后续菜单导航/点击（比盲等更稳且通常更快）。
            for _ in range(12):
                if self.page.locator(".el-message-box:visible").count():
                    break
                self.page.wait_for_timeout(200)
        for _ in range(3):
            box = self.page.locator(".el-message-box:visible")
            if not box.count():
                return True
            btns = box.first.locator("button")
            if btns.count():
                btns.last.click()
            else:
                box.first.locator(".el-message-box__headerbtn").click()
            # 关闭后轮询弹窗消失即返回（替代盲等 0.8s ×最多 3 轮）
            self._wait_until(
                lambda: self.page.locator(".el-message-box:visible").count() == 0, 1500)
        return True

    def press_key(self, key="Escape"):
        """发送真实键盘按键（默认 Escape）。

        典型用途：收起用例步骤里被展开的 ElementUI el-select 下拉面板。
        注意 ElementUI 的 clickoutside 监听 document 上成对的 mousedown/mouseup
        并校验事件来源，evaluate 内派发的合成 click / mousedown / mouseup 均不生效
        （真机实测：body.click() 与合成事件后面板数不变）；Playwright 的
        keyboard.press 产生的是受信任的真实事件，Escape 可正常收起面板。
        不收起的话，后续的菜单导航/Cancel 点击会被展开的面板拦截。
        """
        self.page.keyboard.press(key)
        self.page.wait_for_timeout(_ms(500))
        return True

    def click_blank(self):
        """真实鼠标点击页面空白处：收起被展开的 ElementUI el-select 下拉面板。

        ElementUI 的 clickoutside 监听 document 上成对的 mousedown/mouseup 并校验
        事件来源，evaluate 内派发的合成 click / mousedown / mouseup 均不生效
        （真机实测：body.click() 与合成事件后面板数不变）；只有 Playwright 的
        真实输入事件（mouse.click / keyboard.press）能触发收起。

        空白点在页面内动态扫描（命中 documentElement/body 才算空白），避免硬编码
        坐标误点顶部菜单（实测 (800,60) 恰好是 fhId_security_L1 菜单项）。
        面板没收起会拦截后续的菜单导航与 Cancel 点击（真机复现：INTL-WIFI-042
        面板未收起时 Cancel 后页面不重拉设备参数，频宽显示停在修改值上）。
        """
        pt = self.page.evaluate("""() => {
            const w = window.innerWidth, h = window.innerHeight;
            for (let y = Math.floor(h / 2); y > 20; y -= 40) {
                for (let x = w - 20; x > 20; x -= 40) {
                    const e = document.elementFromPoint(x, y);
                    if (e && (e === document.documentElement || e === document.body)) {
                        return {x: x, y: y};
                    }
                }
            }
            return null;
        }""")
        if not pt:
            return True  # 找不到空白点（页面被弹窗铺满等），交由后续步骤自行处理
        self.page.mouse.click(int(pt["x"]), int(pt["y"]))
        self.page.wait_for_timeout(_ms(600))
        return True

    def close_dialog(self):
        """容错关闭可能打开的新建/编辑表单弹窗（有则关，无则跳过）。
        用于用例前置，避免上一用例残留的表单状态污染本用例。
        """
        for sel in (".el-dialog__headerbtn", "#fhId_Cancel"):
            loc = self.page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                self.page.wait_for_timeout(_ms(800))
        return True

    def assert_confirm_hidden(self):
        box = self.page.locator(".el-message-box")
        if box.count() == 0:
            return True
        try:
            box.wait_for(state="hidden", timeout=5000)
            return True
        except PWTimeout:
            return False

    # ---------- 声明式断言（ElementUI 适配，收敛用例内联脚本）----------
    #
    # 背景：WIFI 四页 + STATUS 曾把断言写成 real.evaluate 内联脚本（278 条、约 18.9 万
    # 字符），副作用有三：①用例不可读、无法 diff/lint；②helper `rd/cb` 被逐条复制
    # 150+ 次；③gen_intl_word 把 `script=...` 原样渲染进用例文档，JS 占文档正文 42%。
    #
    # 这里把高频形态收敛成「选择器 + 期望值」的声明式动作。设计约束：
    #   - 只新增、不修改既有动作签名，保证老用例零回归；
    #   - 全部走真实 DOM 读取（原生控件取 value，容器取 innerText），与老脚本同判据；
    #   - 失败信息带「期望/实际」，直接进 result.json，便于定位。

    _READ_FIELD_JS = """(s) => {
        const el = document.querySelector(s);
        if (!el) return null;
        const i = (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') ? el
                  : el.querySelector('input,textarea');
        return (i ? i.value : (el.innerText || '')).trim();
    }"""

    _VIS_JS = """(s) => {
        const el = document.querySelector(s);
        if (!el) return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
    }"""

    _IS_SELECT_JS = """(s) => {
        const el = document.querySelector(s);
        return !!(el && (el.classList.contains('el-select') || el.closest('.el-select')));
    }"""

    def read_field(self, selector):
        """读取字段当前值：原生控件取 value，容器取 innerText；元素不存在返回 None。"""
        return self.page.evaluate(self._READ_FIELD_JS, resolve_sel(selector) or selector)

    def _need_field(self, selector, timeout_ms=8000, optional=False):
        """等待元素出现并读取其值；超时抛 AssertionError（信息含选择器）。

        optional=True：元素缺失时返回 None 而不抛错。用于「该字段按设备形态可能
        不渲染」的用例（如 PON 设备才有序列号/光路状态），断言侧据此跳过校验，
        取代老用例里的 `!el || (...)` 写法。
        """
        deadline = time.time() + timeout_ms / 1000.0
        sel = resolve_sel(selector) or selector
        val = None
        while True:
            try:
                val = self.page.evaluate(self._READ_FIELD_JS, sel)
            except Exception:
                val = None
            if val is not None:
                return val
            if time.time() >= deadline:
                if optional:
                    return None
                raise AssertionError(f"未找到元素：{selector}")
            self.page.wait_for_timeout(FAST_POLL_MS)

    def assert_field_value(self, selector, value):
        """断言字段值严格等于期望值（替代「const v = rd(x); if (v !== exp) throw ...」）。"""
        actual = self._need_field(selector)
        if actual != str(value):
            raise AssertionError(
                f"字段值不符：{selector} 期望 {value!r}，实际 {actual!r}")
        return True

    def assert_field_value_wait(self, selector, value, timeout_ms=12000, poll_ms=500):
        """轮询等待字段值变为期望值（替代「Promise 轮询回读固定值」类脚本）。

        与 assert_field_value 不同：后者只读一次即断言，本动作针对「保存后页面
        异步重拉数据、值不会立刻到位」的场景，在 timeout_ms 内反复读取直到相等。
        老用例里 24×500ms 的 JS Promise 轮询即此语义。
        """
        value = str(value)
        deadline = time.time() + max(0, timeout_ms) / 1000.0
        actual = self._need_field(selector)
        while actual != value and time.time() < deadline:
            self.page.wait_for_timeout(poll_ms)
            actual = self._need_field(selector)
        if actual != value:
            raise AssertionError(
                f"字段值不符：{selector} 期望 {value!r}，实际 {actual!r}"
                f"（等待 {timeout_ms}ms 后仍不符）")
        return True

    def assert_field_nonempty(self, selector, optional=False):
        """断言字段有值（非空字符串）。

        optional=True：字段未渲染时视为通过（用例显式声明该字段可缺省）。
        """
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        if not actual:
            raise AssertionError(f"字段为空：{selector}")
        return True

    def assert_field_matches(self, selector, pattern, optional=False):
        """断言字段值匹配正则（用例给 pattern，如 ^(Auto Selected|channel\\s*\\d+)$）。

        optional=True：字段未渲染时视为通过。
        """
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        if not re.search(pattern, actual):
            raise AssertionError(
                f"字段值不匹配：{selector} 正则 {pattern!r}，实际 {actual!r}")
        return True

    def assert_field_not_matches(self, selector, pattern, optional=False):
        """断言字段值「不」匹配正则（assert_field_matches 的镜像）。

        典型：密钥用例的前置校验「当前安全模式不是 None / Enterprise」——
        pattern 写 '^(None|.*Enterprise.*)$' 即可表达「排除这两种」。
        optional=True：字段未渲染时视为通过。
        """
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        if re.search(pattern, actual):
            raise AssertionError(
                f"字段值不应匹配：{selector} 正则 {pattern!r}，实际 {actual!r}")
        return True

    def assert_field_not_equals(self, selector, value, ignore_case=False, optional=False):
        """断言字段值「不」严格等于给定值（assert_field_value 的镜像）。

        取代旧写法 assert_field_not_matches(selector, "^ERROR$") —— 纯等值排除，
        不需要正则。ignore_case=True 时忽略大小写比较。
        optional=True：字段未渲染时视为通过。
        """
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        a, exp = actual.strip(), str(value)
        hit = (a.lower() == exp.lower()) if ignore_case else (a == exp)
        if hit:
            raise AssertionError(f"字段值不应等于 {value!r}：{selector} 实际 {actual!r}")
        return True

    def assert_field_in(self, selector, values, ignore_case=False, optional=False):
        """断言字段值恰好等于给定列表中的某一项（全等，非子串）。

        取代旧写法 assert_field_matches(selector, "^(EPON|GPON)$") —— 枚举校验，
        不需要正则。只认全等，不做子串包含。
        optional=True：字段未渲染时视为通过。
        """
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        a = actual.strip()
        pool = [str(v) for v in values]
        if ignore_case:
            ok = a.lower() in [v.lower() for v in pool]
        else:
            ok = a in pool
        if not ok:
            raise AssertionError(
                f"字段值不在允许集合内：{selector} 实际 {actual!r}，允许 {pool}")
        return True

    def assert_field_contains(self, selector, texts, mode="any", ignore_case=False,
                              optional=False):
        """断言字段值包含给定子串（mode="any" 任一命中即通过，"all" 需全部命中）。

        取代旧写法 assert_field_matches(selector, "(?i)(us|Auto)") —— 纯子串判断，
        不需要正则；ignore_case=True 对应旧正则的 (?i) 前缀。
        optional=True：字段未渲染时视为通过。
        """
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        a = actual.strip()
        pool = [str(t) for t in texts]
        if ignore_case:
            low = a.lower()
            hits = [t for t in pool if t.lower() in low]
        else:
            hits = [t for t in pool if t in a]
        need_all = (mode == "all")
        ok = (len(hits) == len(pool)) if need_all else bool(hits)
        if not ok:
            raise AssertionError(
                f"字段值缺少{'全部' if need_all else '任一'}子串："
                f"{selector} 实际 {actual!r}，期望含 {pool}")
        return True

    def assert_field_not_contains(self, selector, texts, ignore_case=False, optional=False):
        """断言字段值「不」包含给定子串中的任何一个（assert_field_contains 的镜像）。

        取代旧写法 assert_field_not_matches(selector, "^(None|.*Enterprise.*)$")
        —— 前置校验「当前值既不是 None、也不含 Enterprise」，不需要正则。
        optional=True：字段未渲染时视为通过。
        """
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        a = actual.strip()
        pool = [str(t) for t in texts]
        if ignore_case:
            low = a.lower()
            hits = [t for t in pool if t.lower() in low]
        else:
            hits = [t for t in pool if t in a]
        if hits:
            raise AssertionError(
                f"字段值不应包含 {hits}：{selector} 实际 {actual!r}")
        return True

    def assert_field_number(self, selector, min=None, max=None, suffix=None,
                            integer=False, optional=False):
        """断言字段值是数字（可带单位后缀与上下界），纯字符判断、不依赖正则。

        取代旧的正则写法三种形态：纯数字 / 带 % 的百分比 / 百分比且不超过 100，
        分别用 integer=True、suffix="%"、max=100 + suffix="%" 表达。
        integer=True 只接受整数；min/max 为闭区间边界（按数值比较）。
        optional=True：字段未渲染时视为通过。
        """
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        body = actual.strip()
        if suffix:
            if not body.endswith(suffix):
                raise AssertionError(
                    f"字段值缺少单位 {suffix!r}：{selector} 实际 {actual!r}")
            body = body[:-len(suffix)].strip()
        digits = body.replace(".", "", 1)
        bad = (not body) or (not digits.isdigit()) or body.startswith(".") or body.endswith(".")
        if bad:
            raise AssertionError(
                f"字段值不是合法数字：{selector} 实际 {actual!r}")
        if integer and ("." in body):
            raise AssertionError(
                f"字段值应为整数：{selector} 实际 {actual!r}")
        num = float(body)
        if (min is not None) and num < min:
            raise AssertionError(
                f"字段值小于下限 {min}：{selector} 实际 {actual!r}")
        if (max is not None) and num > max:
            raise AssertionError(
                f"字段值超过上限 {max}：{selector} 实际 {actual!r}")
        return True

    def assert_field_any_of(self, selector, equals=None, prefix_number=None,
                            ignore_case=False, optional=False):
        """断言字段值命中「若干允许形态之一」，不需要正则。

        取代旧的「枚举 或 前缀+数字」写法：用例给 equals=["Auto Selected"]、
        prefix_number=["channel"]，语义 = 值全等于 equals 任一项，
        或形如「前缀 + 数字」（如 "channel 6"、"channel1"）。
        optional=True：字段未渲染时视为通过。
        """
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        a = actual.strip()
        eq = [str(v) for v in (equals or [])]
        pre = [str(v) for v in (prefix_number or [])]
        if ignore_case:
            ok = a.lower() in [v.lower() for v in eq]
        else:
            ok = a in eq
        if not ok:
            for p in pre:
                if a.startswith(p) and a[len(p):].strip().isdigit():
                    ok = True
                    break
        if not ok:
            raise AssertionError(
                f"字段值不符合任一允许形态：{selector} 实际 {actual!r}，"
                f"允许 equals={eq} / prefix+数字={pre}")
        return True

    def assert_field_format(self, selector, format, optional=False):
        """断言字段值符合「具名格式」（格式表 FIELD_FORMATS，用例侧不写正则）。

        用例写法：{"action": "real.assert_field_format",
                   "selector": "#fhId_MAC_Address", "format": "mac"}
        可用格式见 FIELD_FORMATS：mac / duration / ipv4 / ipv6 / hostname /
        percent / datetime。要加新格式只改表，不动用例。
        optional=True：字段未渲染时视为通过。
        """
        spec = FIELD_FORMATS.get(format)
        if spec is None:
            raise AssertionError(
                f"未知字段格式 {format!r}，可用：{sorted(FIELD_FORMATS)}")
        actual = self._need_field(selector, optional=optional)
        if actual is None:
            return True
        if not re.search(spec[0], actual.strip()):
            raise AssertionError(
                f"字段值不符合格式 [{format}]（{spec[1]}）："
                f"{selector} 实际 {actual!r}")
        return True

    def assert_field_length(self, selector, length, timeout_ms=0, poll_ms=500):
        """断言字段值的「字符长度」——密钥类字段专用，避免明文进日志。

        与 assert_field_matches 的关键差别：后者把实际值写进失败信息，
        密钥字段一旦不符就会把明文打进报告。本动作只读 len()，失败信息也只
        含长度（与 snapshot 的 lengths 读法同源）。timeout_ms>0 时轮询等待，
        语义同 assert_field_value_wait / assert_checkbox_checked。
        """
        want = int(length)

        def hit():
            value = self._need_field(selector)
            return value is not None and len(value) == want

        if self._wait_until(hit, timeout_ms, poll_ms):
            return True
        actual = len(self._need_field(selector) or "")
        suffix = f"（等待 {timeout_ms}ms 后仍不符）" if timeout_ms else ""
        raise AssertionError(
            f"字段长度不符{suffix}：{selector} 期望 {want}，实际 {actual}")

    def assert_field_plain_text(self, selector, contains=None, tag=None):
        """断言字段内容以「文本」呈现，没有被解析成 HTML 元素。

        安全类用例专用：注入 <img src=x onerror=alert(1)> 后，前端若正确转义，
        字段里只有文本节点、原始串能在可见文本里读到；若转义失效则多出元素节点。

        - tag：只校验该标签的子元素数是否为 0（如 'img'）；省略则要求字段内
          **没有任何**元素子节点（更严格，字段本身是纯文本节点时用）。
        - contains：可选，再断言可见文本含该片段。
        """
        sel = resolve_sel(selector) or selector
        res = self.page.evaluate("""(a) => {
            const el = document.querySelector(a.sel);
            if (!el) return {found: false};
            const picked = a.tag ? el.querySelectorAll(a.tag).length
                                 : el.querySelectorAll('*').length;
            return {found: true, count: picked,
                    text: (el.innerText || el.textContent || '')};
        }""", {"sel": sel, "tag": tag})
        if not res.get("found"):
            raise AssertionError(f"未找到元素：{selector}")
        if res["count"]:
            what = f"<{tag}> 子元素" if tag else "子元素"
            raise AssertionError(
                f"字段内容含 {res['count']} 个{what}（期望纯文本）：{selector}")
        if contains is not None and contains not in (res.get("text") or ""):
            raise AssertionError(
                f"字段文本不含期望片段：{selector} 期望含 {contains!r}，"
                f"实际 {res.get('text')!r}")
        return True

    def assert_element_count(self, selector, equals=None, gt=None, min=None):
        """断言匹配 selector 的元素个数（典型用途：表格行数）。

        只给一个条件即可：equals（严格等于）/ gt（大于）/ min（不少于）。
        用于「列表条数相对出厂基线增减」这类断言——基线值只有在运行期才知道，
        无法用静态文本断言表达。
        """
        n = self.page.locator(resolve_sel(selector) or selector).count()
        if equals is not None and n != int(equals):
            raise AssertionError(
                f"元素个数不符：{selector} 期望 {equals}，实际 {n}")
        if gt is not None and not n > int(gt):
            raise AssertionError(
                f"元素个数不符：{selector} 期望大于 {gt}，实际 {n}")
        if min is not None and n < int(min):
            raise AssertionError(
                f"元素个数不符：{selector} 期望不少于 {min}，实际 {n}")
        return True

    def assert_present(self, selector):
        """断言元素存在于 DOM 且可见（含 ElementUI 原生控件被包在可见容器内的场景）。"""
        try:
            self.assert_visible(selector)
            return True
        except Exception:
            raise AssertionError(f"元素不存在或不可见：{selector}")

    def assert_absent(self, selector):
        """断言元素不存在（或不可见）。"""
        sel = resolve_sel(selector) or selector
        loc = self.page.locator(sel)
        if loc.count() == 0:
            return True
        if self.page.evaluate(self._VIS_JS, sel):
            raise AssertionError(f"元素存在且可见（期望不存在）：{selector}")
        return True

    def assert_hash(self, suffix=None, contains=None, equals=None):
        """断言当前 hash 路由。hash 路由 SPA 中比 wait_for_url 更精确、更快，
        且不会因为「只改 hash 不触发导航」而空等超时。"""
        h = self.page.evaluate("() => location.hash || ''")
        if equals is not None and h != equals:
            raise AssertionError(f"hash 不符：期望 {equals!r}，实际 {h!r}")
        if suffix is not None and not h.endswith(suffix):
            raise AssertionError(f"hash 后缀不符：期望以 {suffix!r} 结尾，实际 {h!r}")
        if contains is not None and contains not in h:
            raise AssertionError(f"hash 不含期望片段：期望含 {contains!r}，实际 {h!r}")
        return True

    def assert_switch(self, selector, on=True):
        """断言 el-switch 开/关（复用 _switch_state 的判据，与 set_switch 同源）。"""
        state = self._switch_state(selector)
        if state is None:
            raise AssertionError(f"未取到开关状态：{selector}")
        if bool(state) != bool(on):
            raise AssertionError(
                f"开关状态不符：{selector} 期望 {'开' if on else '关'}，"
                f"实际 {'开' if state else '关'}")
        return True

    def _radio_scope(self, selector):
        """单选组的查找作用域（Playwright Locator）。

        ⚠️ 必须走 Playwright，不能用 `page.evaluate` + `document.querySelector`：
        别名表里的定位方式含 `:has-text(...)`（**Playwright 扩展伪类，浏览器原生
        querySelector 不认**），传进 evaluate 会直接 SyntaxError（2026-09-22 真机踩到）。
        selector 省略时用 body，语义等价于原来的 document 范围。
        """
        if selector:
            loc = self.page.locator(selector).first
            if loc.count() == 0:
                raise AssertionError(f"未找到作用域：{selector}")
            return loc
        return self.page.locator("body").first

    def assert_radio_checked(self, selector=None, label=None, checked=True):
        """断言 el-radio 选中态。

        - 给 label：在 selector（省略则全页）范围内找文案相同的 .el-radio；
        - 不给 label：selector 直接指向某个 .el-radio 或其内部 input。
        selector 可写虚拟别名（如 #fhId_WPAAlgorithms），从而把 label 匹配范围
        收窄到该组，避免同名文案落在别的组里。
        """
        sel = resolve_sel(selector) or selector
        res = self._radio_scope(sel).evaluate("""(el, a) => {
            const scope = el;
            let radio = null;
            if (a.label) {
                radio = Array.from(scope.querySelectorAll('.el-radio'))
                    .filter(r => r.getBoundingClientRect().width > 0)
                    .find(r => ((r.innerText || '').trim() === a.label));
            } else {
                const el = scope.querySelector('.el-radio') || scope;
                radio = el.classList.contains('el-radio') ? el
                        : el.closest('.el-radio');
            }
            if (!radio) return {found: false, msg: '未找到目标 el-radio'};
            const box = radio.classList.contains('is-checked')
                || !!radio.querySelector('.el-radio__input.is-checked');
            const inp = radio.querySelector('input[type=radio]');
            return {found: true, checked: box || !!(inp && inp.checked),
                    text: (radio.innerText || '').trim()};
        }""", {"label": label})
        if not res.get("found"):
            raise AssertionError(
                f"未找到单选项：selector={selector!r} label={label!r}（{res.get('msg')}）")
        if bool(res.get("checked")) != bool(checked):
            raise AssertionError(
                f"单选状态不符：{res.get('text')!r} 期望 "
                f"{'选中' if checked else '未选中'}，实际 "
                f"{'选中' if res.get('checked') else '未选中'}")
        return True

    def assert_radio_one_of(self, labels=None, selector=None):
        """断言一组 el-radio 文案中「恰好选中一个」。

        用于射频 Enable/Disable 这类单选：哪一项该选取决于设备当前配置
        （该 SSID 射频是否打开），写死某一项会随设备配置时对时错，
        因此只校验「恰选其一」（等价于老脚本里的 `if (on === off) throw`）。

        候选文案两种给法（等价，二者取一）：
          - 显式给 labels；
          - selector 写虚拟别名（如 #fhId_WPAAlgorithms），候选文案从别名表取
            —— 用例侧因此只写选择器，与其它步骤形态一致。
        selector 省略表示全页范围，此时必须显式给 labels。
        """
        sel = resolve_sel(selector) or selector
        if not labels:
            labels = alias_options(selector)
            if not labels:
                raise AssertionError(
                    f"assert_radio_one_of 缺少候选文案：selector={selector!r} 既未显式给 "
                    f"labels，也不在虚拟别名表（SELECTOR_ALIASES）中")
        res = self._radio_scope(sel).evaluate("""(el, a) => {
            const scope = el;
            const on = [];
            for (const label of a.labels) {
                const r = Array.from(scope.querySelectorAll('.el-radio'))
                    .filter(x => x.getBoundingClientRect().width > 0)
                    .find(x => ((x.innerText || '').trim() === label));
                if (!r) return {found: false, msg: '未找到 el-radio：' + label};
                const box = r.classList.contains('is-checked')
                    || !!r.querySelector('.el-radio__input.is-checked');
                const inp = r.querySelector('input[type=radio]');
                if (box || !!(inp && inp.checked)) on.push(label);
            }
            return {found: true, on: on};
        }""", {"labels": list(labels)})
        if not res.get("found"):
            raise AssertionError(
                f"单选控件缺失：selector={selector!r} labels={list(labels)!r}"
                f"（{res.get('msg')}）")
        picked = res.get("on") or []
        if len(picked) != 1:
            raise AssertionError(
                f"单选状态异常：{list(labels)} 中选中 {picked or '无'}"
                f"（应恰好选中其一）")
        return True

    def assert_checkbox_checked(self, selector, on=True, timeout_ms=0, poll_ms=500):
        """断言 el-checkbox 选中态（与 click_checkbox 同判据）。

        timeout_ms=0：读一次即断言（默认，原行为）。
        timeout_ms>0：轮询等到勾选态命中即返回——替代用例里「24×500ms 的 JS
        Promise 轮询」。保存后页面异步重拉设备参数，勾选态不会立刻到位
        （元素也可能尚未挂载），故未命中时继续采样而非立即判失败。
        参数名与语义同 assert_field_value_wait / assert_unchanged，调用方写法一致。
        """
        if self._wait_until(lambda: self._checkbox_state(selector) == bool(on),
                            timeout_ms, poll_ms):
            return True
        state = self._checkbox_state(selector)
        if state is None:
            raise AssertionError(f"未取到复选状态：{selector}")
        suffix = f"（等待 {timeout_ms}ms 后仍不符）" if timeout_ms else ""
        raise AssertionError(
            f"复选状态不符{suffix}：{selector} 期望 {'选中' if on else '未选中'}，"
            f"实际 {'选中' if state else '未选中'}")

    def assert_disabled(self, selector, disabled=True):
        """断言控件禁用态。

        注意老 UI 的坑（2026-09-16 实测）：el-select 被 :disabled 禁用时只置**内层
        input** 的 disabled，不给 .el-select 容器加 is-disabled 类。故这里按
        「自身 disabled || 内层控件 disabled || 容器 is-disabled」三选一判定，
        与 _is_disabled 同源，避免误判。
        """
        actual = self._is_disabled(selector)
        if bool(actual) != bool(disabled):
            raise AssertionError(
                f"禁用态不符：{selector} 期望 {'禁用' if disabled else '可编辑'}，"
                f"实际 {'禁用' if actual else '可编辑'}")
        return True

    def _read_option_items(self, selector):
        """展开下拉 → 读回可见选项文案 → 收起面板。

        assert_option_set 与「条件选项集 / 条件取值」类断言共用这一段：
        老用例里每个校验选项集的脚本都要重抄一遍「click 展开 + 过滤
        offsetParent + 读 innerText + blur 收起」，这里收成一处。
        """
        sel = resolve_sel(selector) or selector
        self.page.locator(sel).first.wait_for(state="visible", timeout=8000)
        self._blur_active_input()
        self.page.evaluate(self._CLICK_JS, sel)
        self.page.wait_for_timeout(FAST_POLL_MS if FAST_MODE else 800)
        items = self.page.evaluate("""() => Array.from(
                document.querySelectorAll('.el-select-dropdown__item'))
            .filter(i => { const r = i.getBoundingClientRect();
                           return r.width > 0 && r.height > 0; })
            .map(i => (i.innerText || '').trim())""")
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(_ms(300))
        return items

    def assert_option_set(self, selector, equals=None, contains=None,
                          allow_extra=True, unique=True, no_empty=True,
                          min_count=1, count=None):
        """断言下拉选项集合。

        用例只声明期望集合，不再自己展開面板 + 过滤 offsetParent + 比对：
          - equals：期望集合完全一致（allow_extra=False 时严格相等）
          - contains：期望集合是实际集合的子集
          - count：选项数量精确等于该值（min_count 只管下限）
          - unique/no_empty/min_count：去重、无空文案、最少项数
        """
        items = self._read_option_items(selector)
        if count is not None and len(items) != int(count):
            raise AssertionError(
                f"下拉选项数量不符：{selector} 期望 {count} 项，"
                f"实际 {len(items)} 项 {items}")
        if len(items) < int(min_count):
            raise AssertionError(
                f"下拉选项不足：{selector} 至少期望 {min_count} 项，实际 {len(items)} 项 {items}")
        if no_empty and any(not t for t in items):
            raise AssertionError(f"下拉存在空文案选项：{selector} 实际 {items}")
        if unique and len(set(items)) != len(items):
            dup = sorted({t for t in items if items.count(t) > 1})
            raise AssertionError(f"下拉存在重复项：{selector} 重复 {dup}")
        if contains:
            missing = [t for t in contains if t not in items]
            if missing:
                raise AssertionError(
                    f"下拉缺少期望选项：{selector} 缺少 {missing}，实际 {items}")
        if equals:
            missing = [t for t in equals if t not in items]
            extra = [t for t in items if t not in equals]
            if missing or (extra and not allow_extra):
                raise AssertionError(
                    f"下拉选项集不符：{selector} 缺少 {missing}，多出 {extra}，实际 {items}")
        return True

    def assert_option_set_cond(self, selector, by_selector, cases):
        """期望选项集取决于另一字段取值时，先选分支再断言。

        用例声明多个分支，取「第一条 pattern 命中 by_selector 当前值」的分支；
        无 pattern 的那条作兜底。典型：保护间隔选项集随制式变化——ax/be 制式
        要求 0.8/1.6/3.2us/Auto，其余制式要求 0.4/0.8us/Auto。

        cases 形如 [{"pattern": "(?i)(ax|be)", "contains": [...]},
                    {"contains": [...]}]，
        每条的其余参数与 assert_option_set 完全一致（contains/equals/count/
        min_count/unique/no_empty/allow_extra）。
        """
        value = self._need_field(by_selector)
        for branch in cases:
            pattern = branch.get("pattern")
            if pattern is None or re.search(pattern, value or ""):
                opts = {k: v for k, v in branch.items() if k != "pattern"}
                return self.assert_option_set(selector, **opts)
        raise AssertionError(
            f"选项集断言无命中分支：{by_selector} 当前值 {value!r}，"
            f"cases 中缺少无 pattern 的兜底分支")

    def assert_field_value_if_option(self, selector, option_text,
                                    if_present, if_absent):
        """断言「字段取值随下拉是否含某选项而不同」。

        典型：换频宽/监管域后信道列表刷新——列表仍含 channel 36 时配置应保留，
        不含时须回退 Auto Selected（R4/N5）。先按 assert_option_set 的方式展开
        读选项，再据此定期望值，避免把条件分支写死在用例里。
        """
        items = self._read_option_items(selector)
        present = option_text in items
        want = if_present if present else if_absent
        actual = self._need_field(selector)
        if actual != str(want):
            raise AssertionError(
                f"条件取值不符：{selector} 选项{'含' if present else '不含'} "
                f"{option_text!r} → 期望 {want!r}，实际 {actual!r}（选项集 {items}）")
        return True

    def assert_field_in_options(self, selector):
        """断言字段当前值属于它自己的下拉选项集（不能是列表外的非法值）。

        典型：换频宽/监管域后信道列表刷新——当前值要么是保留的手动信道、
        要么回退 Auto Selected，绝不能是刷新后已不合法的旧值。期望集是运行期
        才知道的，故无法用 assert_option_set 的静态 contains 表达。
        """
        items = self._read_option_items(selector)
        actual = self._need_field(selector)
        if actual not in items:
            raise AssertionError(
                f"字段取值不在合法选项集内：{selector} 当前值 {actual!r}，"
                f"合法集 {items}")
        return True

    def assert_field_error(self, selector, text=None):
        """断言字段的校验错误提示。

        必须先失焦：老 UI 的 ElementUI 校验只在 blur 时触发，而执行器 fill 不含
        blur，未失焦时读到的是上一条陈旧提示（2026-09-16 探针踩过）。
        text 省略时只断言「存在错误提示」。
        """
        self._blur_active_input()
        self.page.wait_for_timeout(_ms(600))
        actual = self.page.evaluate("""(s) => {
            const el = document.querySelector(s);
            if (!el) return null;
            const item = el.closest('.el-form-item');
            const box = item || document;
            const errs = Array.from(box.querySelectorAll('.el-form-item__error'))
                .map(e => (e.innerText || '').trim()).filter(Boolean);
            return errs.length ? errs.join(' | ') : '';
        }""", resolve_sel(selector) or selector)
        if actual is None:
            raise AssertionError(f"未找到字段：{selector}")
        if not actual:
            raise AssertionError(f"未出现校验提示（期望 {text!r}）：{selector}")
        if text is not None and text not in actual:
            raise AssertionError(
                f"校验提示不符：{selector} 期望含 {text!r}，实际 {actual!r}")
        return True

    # ---------- 原值快照 / 回滚（用例清理阶段的公共机制）----------
    #
    # 老用例把「记住设备原值 → 改配置 → 回读一致 → 恢复原值」写成了 140 条内联脚本，
    # 用 localStorage/window 手工维护快照。它的问题：快照存在浏览器里（刷新/中断即丢、
    # 跨 run 可能读到陈旧值）、每个字段一段重复代码。这里改由执行器持有快照。

    def snapshot(self, name, fields, bools=None, lengths=None):
        """记录一组字段的当前值。

        fields 形如 {"std": "#fhId_OperatingStandards"}。
        读取方式默认由 FIELD_KINDS 按别名决定：布尔类（开关/复选框，如 SSID 广播）记勾选态，
        长度类（典型：预共享密钥）只记长度、明文不进快照与日志，其余记文本值；
        用例显式传的 bools/lengths 与表取并集。
        """
        if not isinstance(fields, dict) or not fields:
            raise AssertionError("snapshot 需要非空 fields（{别名: 选择器}）")
        bool_keys = set(bools or []) | {k for k in fields
                                       if FIELD_KINDS.get(k) == "bool"}
        len_keys = set(lengths or []) | {k for k in fields
                                        if FIELD_KINDS.get(k) == "len"}
        snap = {}
        for key, raw_sel in fields.items():
            # 别名只在此处解析一次：快照内存真实选择器，消费侧（assert_unchanged /
            # assert_snapshot_diff / restore）读的就是这份，无需各自再解析。
            selector = resolve_sel(raw_sel) or raw_sel
            if key in bool_keys:
                state = self._checkbox_state(selector)
                if state is None:
                    raise AssertionError(f"未取到勾选态：{selector}（字段 {key}）")
                snap[key] = {"selector": selector, "value": bool(state), "kind": "bool"}
            elif key in len_keys:
                snap[key] = {"selector": selector,
                             "value": len(self._need_field(selector) or ""),
                             "kind": "len"}
            else:
                snap[key] = {"selector": selector,
                             "value": self._need_field(selector), "kind": "text"}
        self._store[name] = snap
        # 兼容原有实现：老脚本的记录侧同时写
        #   window['__<name>'] = o;  localStorage.setItem('<name>', JSON.stringify(o))
        # 供 select_option_dynamic / click_checkbox(state_from=) 这类「运行期取值」动作读取。
        # 这里按原样补写一份「别名 → 纯值」表（不含内部的选择器/读法字段），
        # 使这些消费侧动作保持零改动、与改造前行为一致。
        self.page.evaluate(
            """([k, o]) => {
                window['__' + k] = o;
                try { localStorage.setItem(k, JSON.stringify(o)); } catch (e) {}
                return true;
            }""",
            [name, {k: rec["value"] for k, rec in snap.items()}])
        print(f"[info] snapshot {name}: " + ", ".join(
            f"{k}=" + (f"<{rec['value']} 字符>" if rec["kind"] == "len"
                       else ("***" if _is_secret_sel(rec["selector"])
                             else repr(rec["value"])))
            for k, rec in snap.items()))
        return True

    def snapshot_has(self, name):
        return name in self._store

    def _snap(self, name):
        snap = self._store.get(name)
        if not snap:
            names = ", ".join(self._store) or "（空）"
            raise AssertionError(f"未记录快照 {name!r}（已记录：{names}）")
        return snap

    def _snap_diff(self, snap, keys):
        """比对快照，返回不一致明细（空列表=全部一致）。"""
        bad = []
        for key in keys:
            rec = snap.get(key)
            if rec is None:
                raise AssertionError(f"快照中无字段 {key!r}")
            if rec["kind"] == "bool":
                actual = self._checkbox_state(rec["selector"])
                if actual is None:
                    raise AssertionError(f"未取到勾选态：{rec['selector']}（字段 {key}）")
                actual = bool(actual)
            elif rec["kind"] == "len":
                actual = len(self._need_field(rec["selector"]) or "")
            else:
                actual = self._need_field(rec["selector"])
            if actual != rec["value"]:
                bad.append(f"{key}: 期望 {rec['value']!r} 实际 {actual!r}")
        return bad

    def assert_unchanged(self, name, fields=None, timeout_ms=0, poll_ms=500):
        """断言快照内字段与记录时一致（用于「重进页面回读一致」）。

        fields 限定只校验子集——老用例里「只断言某单个字段恢复原值」的语义不能被
        悄悄放大成「整组字段都没变」，否则会把本就合法的其他字段变更误报为失败。
        timeout_ms>0 时轮询等待（替代用例里 24×500ms 的 JS Promise 轮询）：页面
        保存后是异步重拉数据，值不会立刻到位。
        """
        snap = self._snap(name)
        keys = list(fields) if fields else list(snap)
        deadline = time.time() + max(0, timeout_ms) / 1000.0
        bad = self._snap_diff(snap, keys)
        while bad and time.time() < deadline:
            self.page.wait_for_timeout(poll_ms)
            bad = self._snap_diff(snap, keys)
        if bad:
            suffix = f"（等待 {timeout_ms}ms 后仍未一致）" if timeout_ms else ""
            raise AssertionError(f"字段与快照不一致（{name}）{suffix}：" + "；".join(bad))
        return True

    def restore(self, name, fields=None):
        """把快照内的字段恢复为记录值（值一致则跳过，避免无谓的表单脏写）。

        el-select 走真实交互（点开面板选中文案）而非直接改 input.value——后者不会
        同步 ElementUI/Vue 的 model，点了 Apply 也写不进设备。开关/复选框走
        set_switch（幂等）。
        """
        snap = self._snap(name)
        keys = list(fields) if fields else list(snap)
        for key in keys:
            rec = snap.get(key)
            if rec is None:
                raise AssertionError(f"快照 {name!r} 中无字段 {key!r}")
            sel, want = rec["selector"], rec["value"]
            if rec["kind"] == "len":
                # 长度类字段（如预共享密钥）只记录了长度、不含明文，无法据此恢复；
                # 老用例同策略：不恢复（密钥由页面自身回显，不该由用例改写）。
                print(f"[info] restore: {key}（{sel}）为「仅长度」字段，跳过恢复")
                continue
            if rec["kind"] == "bool":
                if self._checkbox_state(sel) != want:
                    self.set_switch(sel, want)
                    self.page.wait_for_timeout(_ms(400))
                if self._checkbox_state(sel) != want:
                    raise AssertionError(
                        f"恢复失败：{key}（{sel}）期望 {want!r}，实际 "
                        f"{self._checkbox_state(sel)!r}")
                continue
            # 字段被置灰时无法通过 UI 恢复（老用例同策略：直接 return true 跳过）。
            # 典型：制式切到 b/g 后频宽被强制 20MHz 并禁用，此时不应判用例失败。
            if self.page.locator(sel).count() and self._is_disabled(sel):
                print(f"[info] restore: {key}（{sel}）为禁用态，跳过恢复")
                continue
            cur = self._need_field(sel)
            if cur == want:
                continue
            is_select = self.page.evaluate(self._IS_SELECT_JS, sel)
            if is_select:
                self.select_option(sel, want)
            else:
                self.fill(sel, want)
            now = self._need_field(sel)
            if now != want:
                raise AssertionError(
                    f"恢复失败：{key}（{sel}）期望 {want!r}，实际 {now!r}")
        return True

    def assert_changed(self, name, fields=None, timeout_ms=0, poll_ms=500):
        """断言快照内字段与记录时「不同」（用于「确认修改已生效」）。

        与 assert_unchanged 互为镜像：这里要求至少一个字段发生变化，否则说明
        前端脏值未生效、后续的 Cancel 丢弃 / 回读验证无从谈起。fields 限定校验
        子集；timeout_ms>0 时轮询等待（保存后异步重拉，值不会立刻到位）。
        """
        snap = self._snap(name)
        keys = list(fields) if fields else list(snap)
        deadline = time.time() + max(0, timeout_ms) / 1000.0
        bad = self._snap_diff(snap, keys)  # bad=不一致字段（即「已变化」）
        while bad and time.time() < deadline:
            self.page.wait_for_timeout(poll_ms)
            bad = self._snap_diff(snap, keys)
        # 「变了」= 存在不一致字段；「没变」= 全部一致（bad 为空）
        if not bad:
            suffix = f"（等待 {timeout_ms}ms 后仍无变化）" if timeout_ms else ""
            raise AssertionError(
                f"字段与快照仍一致，修改未生效（{name}）{suffix}")
        return True

    def assert_snapshot_diff(self, name_a, name_b, fields=None):
        """断言两个快照（如 SSID-1 vs SSID-2）在指定字段上至少一项不同。

        用于「切换重填确实生效」这类跨快照比较——两个快照都是执行器内存里记录的
        设备取值，比较它们之间的差异，而非与当前页面值比较。fields 缺省比较两快照
        共有的全部字段。
        """
        a = self._snap(name_a)
        b = self._snap(name_b)
        keys = list(fields) if fields else [k for k in a if k in b]
        diffs = [k for k in keys
                 if k in a and k in b and a[k]["value"] != b[k]["value"]]
        if not diffs:
            raise AssertionError(
                f"快照 {name_a} 与 {name_b} 在字段 {keys} 上完全相同，"
                f"无法验证切换生效（配置无差异）")
        return True

    def select_option_diff(self, selector):
        """选中下拉中「与当前值不同」的任意一项（用于构造变更场景）。

        替代用例里「展开面板 → 过滤可见项 → 取第一个不同项 → 点击」的一整段脚本。
        返回选中的选项文案，供用例后续断言引用不到时排查。
        """
        sel = resolve_sel(selector) or selector
        self.page.locator(sel).first.wait_for(state="visible", timeout=8000)
        cur = self.read_field(sel) or ""
        self._blur_active_input()
        self.page.evaluate(self._CLICK_JS, sel)
        self.page.wait_for_timeout(FAST_POLL_MS if FAST_MODE else 800)
        items = self.page.evaluate("""() => Array.from(
                document.querySelectorAll('.el-select-dropdown__item'))
            .filter(i => { const r = i.getBoundingClientRect();
                           return r.width > 0 && r.height > 0; })
            .map(i => (i.innerText || '').trim())""")
        target = next((t for t in items if t and t != cur), None)
        if target is None:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(_ms(300))
            raise PreconditionBlocked(
                f"下拉 {selector} 无「与当前值不同」的可选项（当前 {cur!r}，共 {len(items)} 项）")
        self.page.locator(
            f".el-select-dropdown:visible .el-select-dropdown__item:has-text('{target}')"
        ).first.click()
        self.page.wait_for_timeout(_ms(500))
        print(f"[info] select_option_diff: {selector} {cur!r} -> {target!r}")
        return target

    def select_option_first(self, selector):
        """选中下拉中的「第一项」（用例不关心具体文案，只要求落在列表首项）。

        用于下拉项文案随设备配置变化的场景：SSID 列表会因双频合一开关/重新下发
        变成 2/3/4（甚至不含 1），此时用例写死 option_text='1' 会直接超时判 FAIL。
        已处于首项时幂等跳过。
        """
        sel = resolve_sel(selector) or selector
        self.page.locator(sel).first.wait_for(state="visible", timeout=8000)
        cur = (self.read_field(sel) or "").strip()
        self._blur_active_input()
        self.page.evaluate(self._CLICK_JS, sel)
        self.page.wait_for_timeout(FAST_POLL_MS if FAST_MODE else 800)
        items = self.page.evaluate("""() => Array.from(
                document.querySelectorAll('.el-select-dropdown__item'))
            .filter(i => { const r = i.getBoundingClientRect();
                           return r.width > 0 && r.height > 0; })
            .map(i => (i.innerText || '').trim())""")
        items = [t for t in items if t]
        if not items:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(_ms(300))
            raise PreconditionBlocked(
                f"下拉 {selector} 展开后无可选项（设备未开通相关业务/接口，环境受限）")
        target = items[0]
        if cur == target:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(_ms(300))
            print(f"[info] select_option_first: {selector} 已是首项 {target!r}，跳过")
            return target
        self.page.locator(
            f".el-select-dropdown:visible .el-select-dropdown__item:has-text('{target}')"
        ).first.click()
        self.page.wait_for_timeout(_ms(500))
        print(f"[info] select_option_first: {selector} {cur!r} -> {target!r}")
        return target

    _CLICK_JS = """(s) => {
        const el = document.querySelector(s);
        if (!el) throw new Error('未找到 ' + s);
        const i = (el.tagName === 'INPUT') ? el : el.querySelector('input,textarea');
        const t = i || el;
        t.blur && t.blur();
        t.click();
        return true;
    }"""

    # ---------- 其它 ----------
    # real.evaluate 的 helper 预注入：按需补 `rd/cb/...`，已被脚本自己声明的跳过。
    # 这样老脚本（自带 const rd = ...）语义分毫不变，新脚本则不必再复制上百字符。
    _EVAL_HELPERS = {
        "rd": "((s) => { const el = document.querySelector(s); if (!el) return null;"
              " const i = (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') ? el"
              " : el.querySelector('input,textarea');"
              " return (i ? i.value : (el.innerText || '')).trim(); })",
        "cb": "((s) => { const el = document.querySelector(s); if (!el) return null;"
              " const i = (el.tagName === 'INPUT') ? el : el.querySelector('input');"
              " return i ? !!i.checked : null; })",
        "vis": "((s) => { const el = document.querySelector(s); if (!el) return false;"
               " const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; })",
        "txt": "((s) => { const el = document.querySelector(s);"
               " return el ? (el.innerText || '').trim() : null; })",
        "hash": "(() => location.hash || '')",
        "lsGet": "((k) => { try { return JSON.parse(localStorage.getItem(k) || 'null'); }"
                 " catch (e) { return null; } })",
        "lsSet": "((k, v) => { try { localStorage.setItem(k, JSON.stringify(v));"
                 " return true; } catch (e) { return false; } })",
    }

    def _eval_helper_prelude(self, body):
        lines = []
        for name, js in self._EVAL_HELPERS.items():
            if re.search(r'\b(?:const|let|var)\s+%s\b' % re.escape(name), body):
                continue  # 脚本自己声明了同名变量 → 让 JS 作用域规则生效，不注入
            lines.append(f"const {name} = {js};")
        return "\n".join(lines)

    def inject_vue_data(self, key, value, root="#app", max_depth=8):
        """把值写进 Vue 组件树中「持有该数据字段」的组件（激励动作，非断言）。

        动机：声明式断言只能读 DOM，无法制造「数据源里带恶意串」的激励。
        安全类用例需要绕过接口直接改组件数据，再看渲染是否被正确转义
        （等价于老用例里那段 walk(comp) 找 _data 持有者的内联脚本）。

        从 root 的 __vue__ 起深度优先查找 _data/$data 含 key 的组件并赋值。
        找不到持有者即失败——页面结构变了就该暴露，不能静默通过。
        """
        res = self.page.evaluate("""(a) => {
            const root = document.querySelector(a.root);
            const vm = root && root.__vue__;
            if (!vm) return {ok: false, msg: '未取到 Vue 实例 ' + a.root};
            let target = null;
            function walk(comp, depth) {
                if (target || !comp || depth > a.depth) return;
                const d = comp._data || comp.$data || {};
                if (Object.prototype.hasOwnProperty.call(d, a.key)) {
                    target = comp;
                    return;
                }
                for (const child of comp.$children || []) walk(child, depth + 1);
            }
            walk(vm, 0);
            if (!target) return {ok: false, msg: '组件树中未找到数据字段 ' + a.key};
            target[a.key] = a.value;
            return {ok: true};
        }""", {"root": root, "key": key, "value": value,
               "depth": int(max_depth)})
        if not res.get("ok"):
            raise AssertionError(f"注入 Vue 数据失败：{res.get('msg')}")
        return True

    def evaluate(self, script):
        body = (script or "").strip()
        if not body:
            raise AssertionError("real.evaluate 需要 script 参数")
        body = body.rstrip().rstrip(";").rstrip()
        prelude = self._eval_helper_prelude(body)
        wrapped = "() => {\n%s\nreturn (%s)();\n}" % (prelude, body)
        return self.page.evaluate(wrapped)

    def screenshot(self, name):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, f"{name}.png")
        # --fast：整页截图较慢（103 张合计约 1~2 分钟），提速模式改为视口截图
        self.page.screenshot(path=path, full_page=not FAST_MODE)
        return path

    def no_dialog(self):
        return len(self._dialogs) == 0

    def assert_unauthorized(self):
        # 未登录访问受保护页面时，数据接口应返回 401/403
        return self._unauthorized

    def assert_unauth_redirect(self):
        # 未登录访问受保护页面：应跳转登录页（URL 含 login.html 或登录表单可见）
        # SPA 重定向由前端拿到 401 后异步触发，轮询等待最长 10s（兼容设备端会话注销延迟）
        deadline = time.time() + 10
        while time.time() < deadline:
            if "/login.html" in self.page.url:
                return True
            for sel in ("#user_name", "#wraplogin_CM", "#fh_login_container"):
                loc = self.page.locator(sel)
                if loc.count() and loc.first.is_visible():
                    return True
            self.page.wait_for_timeout(_ms(1000))
        # 失败诊断：区分会话仍有效（数据接口 200）与未授权保护失效
        print(f"[warn] assert_unauth_redirect 失败：最终URL={self.page.url}，捕获到401/403={self._unauthorized}")
        return False


ACTION_MAP = {
    "real.navigate": lambda s, a: s.navigate(a["path"]),
    "real.navigate_spa": lambda s, a: s.navigate_spa(a["route"]),
    "real.login": lambda s, a: s.login(a.get("role", "admin"), a.get("expect", True)),
    "real.ensure_login": lambda s, a: s.ensure_login(),
    "real.open_page": lambda s, a: s.open_page(a["route"], a.get("l1"), a.get("l2"),
                                              a.get("l3"), a.get("expect")),
    "real.logout": lambda s, a: s.logout(),
    "real.fill": lambda s, a: s.fill(a["selector"], a["value"]),
    "real.clear_select": lambda s, a: s.clear_select(a["selector"]),
    "real.set_input_files": lambda s, a: s.set_input_files(a["selector"], a["path"]),
    "real.click": lambda s, a: s.click(a["selector"]),
    "real.wait": lambda s, a: s.wait(a["ms"]),
    "real.click_menu": lambda s, a: s.click_menu(a.get("l1"), a.get("l2"), a.get("l3")),
    "real.assert_visible": lambda s, a: s.assert_visible(a["selector"]),
    "real.assert_hidden": lambda s, a: s.assert_hidden(a["selector"]),
    "real.assert_url_contains": lambda s, a: s.assert_url_contains(a["substring"]),
    "real.assert_input_value": lambda s, a: s.assert_input_value(a["selector"], a["value"]),
    "real.assert_input_value_not": lambda s, a: s.assert_input_value_not(a["selector"], a["value"]),
    "real.skip_if_filled": lambda s, a: s.skip_if_filled(a["selector"], a.get("steps", 1)),
    "real.skip_if_disabled": lambda s, a: s.skip_if_disabled(a["selector"], a.get("steps", 0)),
    "real.probe_disabled": lambda s, a: s.probe_disabled(a["selectors"], a.get("label")),
    "real.skip_if_option_absent": lambda s, a: s.skip_if_option_absent(
        a["selector"], a["option_text"], a.get("steps", 0)),
    "real.set_switch": lambda s, a: s.set_switch(a["selector"], a.get("on", True)),
    "real.assert_text_contains": lambda s, a: s.assert_text_contains(a["selector"], a["text"]),
    "real.assert_text_not_contains": lambda s, a: s.assert_text_not_contains(a["selector"], a["text"]),
    "real.assert_html_not_contains": lambda s, a: s.assert_html_not_contains(
        a["selector"], a["texts"]),
    "real.assert_login_error": lambda s, a: s.assert_login_error(),
    "real.assert_login_stays": lambda s, a: s.assert_login_stays(),
    "real.assert_page": lambda s, a: s.assert_page(a.get("component", "main")),
    "real.assert_element": lambda s, a: s.assert_element(a["selector"]),
    "real.select_option": lambda s, a: s.select_option(a["selector"], a["option_text"]),
    "real.select_option_dynamic": lambda s, a: s.select_option_dynamic(a["selector"], a["key"], a["field"]),
    "real.click_checkbox": lambda s, a: s.click_checkbox(a["selector"], a.get("on"), a.get("state_from"), a.get("field")),
    "real.select_time_range": lambda s, a: s.select_time_range(a["selector"], a["start"], a["end"]),
    "real.assert_option_present": lambda s, a: s.assert_option_present(a["selector"], a["option_text"]),
    "real.assert_confirm_visible": lambda s, a: s.assert_confirm_visible(a.get("keyword", "")),
    "real.delete_wan_row": lambda s, a: s.delete_wan_row(a["row_text"], a.get("optional", False)),
    "real.delete_wan_row_if_exists": lambda s, a: s.delete_wan_row_if_exists(a["row_text"]),
    "real.delete_row_at": lambda s, a: s.delete_row_at(a.get("index", -1), a.get("if_count_gt")),
    "real.click_confirm": lambda s, a: s.click_confirm(a.get("accept", True)),
    "real.assert_confirm_hidden": lambda s, a: s.assert_confirm_hidden(),
    "real.press_key": lambda s, a: s.press_key(a.get("key", "Escape")),
    "real.click_blank": lambda s, a: s.click_blank(),
    "real.close_boxes": lambda s, a: s.close_boxes(),
    "real.close_dialog": lambda s, a: s.close_dialog(),
    "real.evaluate": lambda s, a: s.evaluate(a["script"]),
    "real.inject_vue_data": lambda s, a: s.inject_vue_data(
        a["key"], a["value"], a.get("root", "#app"), a.get("max_depth", 8)),
    # 声明式断言（ElementUI 适配；替代 real.evaluate 内联脚本）
    "real.read_field": lambda s, a: s.read_field(a["selector"]),
    "real.assert_field_value": lambda s, a: s.assert_field_value(a["selector"], a["value"]),
    "real.assert_field_value_wait": lambda s, a: s.assert_field_value_wait(
        a["selector"], a["value"], a.get("timeout_ms", 12000), a.get("poll_ms", 500)),
    "real.assert_field_nonempty": lambda s, a: s.assert_field_nonempty(
        a["selector"], a.get("optional", False)),
    "real.assert_field_matches": lambda s, a: s.assert_field_matches(
        a["selector"], a["pattern"], a.get("optional", False)),
    "real.assert_field_not_matches": lambda s, a: s.assert_field_not_matches(
        a["selector"], a["pattern"], a.get("optional", False)),
    "real.assert_field_not_equals": lambda s, a: s.assert_field_not_equals(
        a["selector"], a["value"], a.get("ignore_case", False), a.get("optional", False)),
    "real.assert_field_in": lambda s, a: s.assert_field_in(
        a["selector"], a["values"], a.get("ignore_case", False), a.get("optional", False)),
    "real.assert_field_contains": lambda s, a: s.assert_field_contains(
        a["selector"], a["texts"], a.get("mode", "any"), a.get("ignore_case", False),
        a.get("optional", False)),
    "real.assert_field_not_contains": lambda s, a: s.assert_field_not_contains(
        a["selector"], a["texts"], a.get("ignore_case", False), a.get("optional", False)),
    "real.assert_field_number": lambda s, a: s.assert_field_number(
        a["selector"], a.get("min"), a.get("max"), a.get("suffix"),
        a.get("integer", False), a.get("optional", False)),
    "real.assert_field_any_of": lambda s, a: s.assert_field_any_of(
        a["selector"], a.get("equals"), a.get("prefix_number"),
        a.get("ignore_case", False), a.get("optional", False)),
    "real.assert_field_format": lambda s, a: s.assert_field_format(
        a["selector"], a["format"], a.get("optional", False)),
    "real.assert_field_length": lambda s, a: s.assert_field_length(
        a["selector"], a["length"], a.get("timeout_ms", 0), a.get("poll_ms", 500)),
    "real.assert_present": lambda s, a: s.assert_present(a["selector"]),
    "real.assert_absent": lambda s, a: s.assert_absent(a["selector"]),
    "real.assert_field_plain_text": lambda s, a: s.assert_field_plain_text(
        a["selector"], a.get("contains"), a.get("tag")),
    "real.assert_element_count": lambda s, a: s.assert_element_count(
        a["selector"], a.get("equals"), a.get("gt"), a.get("min")),
    "real.assert_hash": lambda s, a: s.assert_hash(
        a.get("suffix"), a.get("contains"), a.get("equals")),
    "real.assert_switch": lambda s, a: s.assert_switch(a["selector"], a.get("on", True)),
    "real.assert_radio_checked": lambda s, a: s.assert_radio_checked(
        a.get("selector"), a.get("label"), a.get("checked", True)),
    "real.assert_radio_one_of": lambda s, a: s.assert_radio_one_of(
        a.get("labels"), a.get("selector")),
    "real.assert_checkbox_checked": lambda s, a: s.assert_checkbox_checked(
        a["selector"], a.get("on", True)),
    "real.assert_disabled": lambda s, a: s.assert_disabled(
        a["selector"], a.get("disabled", True)),
    "real.assert_option_set": lambda s, a: s.assert_option_set(
        a["selector"], a.get("equals"), a.get("contains"),
        a.get("allow_extra", True), a.get("unique", True),
        a.get("no_empty", True), a.get("min_count", 1), a.get("count")),
    "real.assert_option_set_cond": lambda s, a: s.assert_option_set_cond(
        a["selector"], a["by_selector"], a["cases"]),
    "real.assert_field_value_if_option": lambda s, a: s.assert_field_value_if_option(
        a["selector"], a["option_text"], a["if_present"], a["if_absent"]),
    "real.assert_field_in_options": lambda s, a: s.assert_field_in_options(a["selector"]),
    "real.assert_field_error": lambda s, a: s.assert_field_error(
        a["selector"], a.get("text")),
    "real.snapshot": lambda s, a: s.snapshot(a["name"], a["fields"], a.get("bools"),
                                             a.get("lengths")),
    "real.assert_unchanged": lambda s, a: s.assert_unchanged(
        a["name"], a.get("fields"), a.get("timeout_ms", 0), a.get("poll_ms", 500)),
    "real.assert_changed": lambda s, a: s.assert_changed(
        a["name"], a.get("fields"), a.get("timeout_ms", 0), a.get("poll_ms", 500)),
    "real.assert_snapshot_diff": lambda s, a: s.assert_snapshot_diff(
        a["name_a"], a["name_b"], a.get("fields")),
    "real.restore": lambda s, a: s.restore(a["name"], a.get("fields")),
    "real.select_option_diff": lambda s, a: s.select_option_diff(a["selector"]),
    "real.select_option_first": lambda s, a: s.select_option_first(a["selector"]),
    "real.screenshot": lambda s, a: s.screenshot(a["name"]),
    "real.no_dialog": lambda s, a: s.no_dialog(),
    "real.assert_unauthorized": lambda s, a: s.assert_unauthorized(),
    "real.assert_unauth_redirect": lambda s, a: s.assert_unauth_redirect(),
}


def route_from_menu(l1, l2, l3):
    """由三级菜单 id 推导 hash SPA 路由。

    老 UI 菜单 id 与路由同源：fhId_network_L1 / fhId_wifiSettings_L2 /
    fhId_wifiBasic_L3 → /network/wifiSettings/wifiBasic。推导失败（命名不按此规律）
    返回 None，调用方保持原三级菜单点击不变。
    """
    def _clean(x, suffix):
        x = (x or "").strip()
        if x.startswith("fhId_"):
            x = x[len("fhId_"):]
        if suffix and x.endswith(suffix):
            x = x[: -len(suffix)]
        return x

    parts = [_clean(l1, "_L1"), _clean(l2, "_L2"), _clean(l3, "_L3")]
    if not all(parts):
        return None
    return "/" + "/".join(parts)


def _is_std_login_block(steps):
    """是否为用例开头的「标准登录四步」：访问登录页 → 填用户名 → 填密码 → 点登录。

    取值判据（2026-09-18 加固）：两个 fill 的 value 必须**严格等于**常规凭据占位符
    ``${QCT_INTL_ADMIN_USER}`` / ``${QCT_INTL_ADMIN_PASS}``。只比对动作/选择器会把
    「登录框 XSS 注入」「错误密码」「空用户名」这类以登录为被测点的用例误判成前置
    登录，进而在 --fast 下被改写成 ensure_login、并被注入已认证会话。
    判据与 tools/apply_single_login.py::is_std_login_block 保持一致。
    """
    h = steps[:4]
    return bool(len(h) == 4
                and h[0].get("action") == "real.navigate" and h[0].get("path") == "/login.html"
                and h[1].get("action") == "real.fill" and h[1].get("selector") == "#user_name"
                and h[1].get("value") == STD_LOGIN_USER_VALUE
                and h[2].get("action") == "real.fill" and h[2].get("selector") == "#loginpp"
                and h[2].get("value") == STD_LOGIN_PASS_VALUE
                and h[3].get("action") == "real.click" and h[3].get("selector") == "#login_btn")


def _has_login_failure_semantics(steps):
    """尾部断言是否指向「登录失败/账号锁定」——是则登录是被测点，不可改写/不可注入会话。

    与 tools/apply_single_login.py::_has_login_failure_semantics 同源。
    """
    for s in steps[4:]:
        if s.get("action") in LOGIN_FAIL_ACTIONS:
            return True
        if any(x in str(s.get("selector", "")) for x in LOGIN_FAIL_SELECTORS):
            return True
    return False


def _uses_shared_session(case):
    """该用例是否声明「复用会话」语义（首个步骤为 ensure_login / open_page）。

    --fast 会把标准登录四步改写为 ensure_login，故四步块同样计入。
    只有这类用例才注入已认证会话；未登录拦截 / 登录流程 / 错误密码等用例不注入，
    始终以「干净上下文」执行。

    尾部有登录失败/锁定断言的用例（INTL-SEC-002 等）同样不注入：它们的断言落在
    「未登录/被锁定」状态上，注入已认证会话会使断言落点整体错位。
    """
    steps = case.get("steps") or []
    if not steps:
        return False
    act = steps[0].get("action")
    if act in ("real.ensure_login", "real.open_page"):
        return True
    return bool(FAST_MODE and _is_std_login_block(steps)
                and not _has_login_failure_semantics(steps))


def _fast_rewrite_case(case):
    """--fast 专属的用例改写（不改动断言内容与保存/清理逻辑）：

    1) 用例开头的「标准登录四步」（navigate /login.html → fill #user_name →
       fill #loginpp → click #login_btn）合并为单步 real.ensure_login：
       会话已认证时直达主页（约 1s），失效时才完整登录一次。
       login 套件（用例验证登录本身）不改写；取值非常规凭据（XSS/错误密码/空值）或
       尾部断言登录失败/锁定的用例同样不改写——登录即被测点（见 _is_std_login_block
       与 _has_login_failure_semantics 的取值/语义判据）。
    2) 登录块之后紧跟的三级菜单导航合并为「深链直达」（real.open_page）：
       一次 goto 到 #/network/wifiSettings/xxx，实测 380ms 就绪（点菜单约 7s）。
       深链落地路由不符时自动回退点菜单，其他套件命名不同也零风险。
    3) 断言脚本轮询间隔 500ms→300ms，次数上限 24→40，总超时仍为 12s，
       设备已生效时能更早返回。
    """
    steps = case.get("steps", [])
    cid = str(case.get("id", ""))
    if (not cid.startswith("INTL-LOGIN") and _is_std_login_block(steps)
            and not _has_login_failure_semantics(steps)):
        steps = [{"action": "real.ensure_login",
                  "desc": "确保已登录（会话复用：run 开始登录一次并注入会话；失效自动重登）"}] + steps[4:]

    # 2) 登录块之后紧跟的三级菜单导航合并为「深链直达」单步：一次 goto 取代
    #    「进主页 + 点三级菜单」（真机实测 380ms 就绪 vs 菜单约 7s）。落地路由
    #    不符时 open_page 自动回退点菜单，语义不变；断言步骤全部保留。
    if steps and steps[0].get("action") == "real.ensure_login" and len(steps) > 1:
        for j in range(1, min(len(steps), 4)):
            if steps[j].get("action") != "real.click_menu":
                continue
            # 仅当菜单点击紧跟登录块（j==1）时合并，避免丢弃中间步骤
            if j != 1:
                break
            route = route_from_menu(steps[j].get("l1"), steps[j].get("l2"), steps[j].get("l3"))
            if not route:
                break
            expect = None
            for k in range(j + 1, min(len(steps), j + 4)):
                if steps[k].get("action") == "real.assert_url_contains":
                    expect = steps[k].get("substring")
                    break
            merged = {"action": "real.open_page", "route": route,
                      "l1": steps[j].get("l1"), "l2": steps[j].get("l2"),
                      "l3": steps[j].get("l3"), "expect": expect,
                      "desc": f"深链直达 {route}（一次跳转取代主页+三级菜单；未按预期落地则自动回退）"}
            # open_page 自身处理「会话失效则登录一次」，故这里把 ensure_login 一并去掉，
            # 避免多一次「先进主页再跳深链」的冗余导航（每条用例约省 0.5~1s）。
            steps = [merged] + steps[j + 1:]
            break

    def _rw(s):
        if s.get("action") == "real.evaluate" and isinstance(s.get("script"), str):
            sc = s["script"]
            if "setTimeout(tick, 500)" in sc:
                # 轮询间隔 500→300ms，次数上限 24→40，总超时仍 12s（写法含/不含空格均覆盖）
                sc = sc.replace("setTimeout(tick, 500)", "setTimeout(tick, 300)")
                sc = re.sub(r"n\s*>\s*24", "n > 40", sc)
                return {**s, "script": sc}
        return s

    return {**case, "steps": [_rw(s) for s in steps]}


def _dump_result(summary, out_dir, planned=None, partial=False):
    """写 result.json（先写临时文件再原子替换，避免读到半截文件）。

    partial=True 时标记为「中途快照」——供增量落盘使用，让运行被 Ctrl+C / kill
    终止时仍保留已完成用例的结果（此前只在全部跑完时落盘，中断即全丢）。
    """
    snap = dict(summary)
    if planned is not None:
        snap["planned"] = planned
    snap["partial"] = partial
    snap["end"] = datetime.now().isoformat()
    try:
        snap["duration_s"] = round(
            (datetime.now() - datetime.fromisoformat(snap["start"])).total_seconds(), 1)
    except Exception:
        pass
    executed = snap.get("total", 0) - snap.get("skip", 0)
    snap["pass_rate"] = round(snap.get("pass", 0) / executed * 100, 1) if executed else 0
    path = os.path.join(out_dir, "result.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def run_case(session, case, out_dir):
    case_id = case.get("id", "case")
    steps = case.get("steps", [])
    # 清理步骤：desc 以“清理：”开头的第一个步骤起到用例结尾，无论测试步骤成败都要执行。
    # 防止用例中途失败时留在真机上的残留配置（如新建的 WAN 连接）越积越多。
    main_steps, cleanup_steps = [], []
    for i, s in enumerate(steps):
        if (s.get("desc") or "").startswith("清理"):
            cleanup_steps = steps[i:]
            break
        main_steps.append(s)
    result = {
        "id": case_id,
        "title": case.get("title", ""),
        "priority": case.get("priority", "P1"),
        "tags": case.get("tags", []),
        "status": "PASS",
        "steps": [],
        "error": None,
        "start": datetime.now().isoformat(),
    }
    # 会话超时自愈次数上限（每个用例独立计数；session 每用例新建）
    healed = 0
    for i, step in enumerate(main_steps):
        action = step.get("action")
        desc = step.get("desc", "")
        step_result = {"index": i + 1, "action": action, "desc": desc, "status": "PASS", "error": None}
        # 计数只在当前用例的 session 上（每用例独立新建），未用完也不会泄漏到下一用例
        if getattr(session, "_skip_next", 0) > 0:
            session._skip_next -= 1
            step_result["status"] = "SKIP"
            step_result["error"] = "上一步条件命中，跳过本步"
            result["steps"].append(step_result)
            continue
        try:
            if action in ACTION_MAP:
                ok = ACTION_MAP[action](session, step)
                if ok is False:
                    raise AssertionError(f"action {action} returned False")
                # screenshot 动作：把截图路径记录到 detail（供报告嵌入）
                if action == "real.screenshot" and isinstance(ok, str):
                    step_result["detail"] = ok
            else:
                raise AssertionError(f"unknown action: {action}")
        except Exception as e:
            # 会话超时自愈：设备端会话过期会弹「Login timeout」模态框，遮罩挡住页面
            # 使断言/点击超时。关弹窗 + 重登 + **重试本步一次**，避免把设备侧会话
            # 过期误判为用例缺陷（真机实测 INTL-LAN-015 复现，约 1/3 概率）。
            if healed < 2 and session.heal_login_timeout():
                healed += 1
                try:
                    ok = ACTION_MAP[action](session, step)
                    if ok is False:
                        raise AssertionError(f"action {action} returned False")
                    if action == "real.screenshot" and isinstance(ok, str):
                        step_result["detail"] = ok
                    step_result["note"] = "设备端会话超时，已自动重新登录并重试本步"
                    result["steps"].append(step_result)
                    continue
                except Exception as e2:
                    e = e2
            # 页面不存在策略：导航菜单缺失（当前固件无该页面）→ 整条用例跳过而非失败。
            # real.open_page 是 --fast 对「标准登录块 + 三级菜单」的合并形态，其菜单
            # 回退失败（MenuMissing）必须与直接 click_menu 同策略；否则 --fast 会把
            # 「设备无此页面」从 SKIP 变成 FAIL（INTL-FW-008/027/028 的 ipv6MacFilter）。
            if (isinstance(e, MenuMissing)
                    or (action == "real.click_menu" and isinstance(e, PWTimeout))):
                step_result["status"] = "SKIP"
                step_result["error"] = f"页面/菜单不存在，跳过: {type(e).__name__}: {str(e)[:200]}"
                result["status"] = "SKIP"
                result["error"] = f"step {i + 1} [{action}]: 页面/菜单不存在（设备无此页面），跳过用例"
                result["steps"].append(step_result)
                break
            if isinstance(e, PreconditionBlocked):
                step_result["status"] = "SKIP"
                step_result["error"] = f"前置条件不满足，跳过: {str(e)[:200]}"
                result["status"] = "SKIP"
                result["error"] = f"step {i + 1} [{action}]: {str(e)[:200]}"
                result["steps"].append(step_result)
                break
            step_result["status"] = "FAIL"
            step_result["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            result["status"] = "FAIL"
            result["error"] = f"step {i + 1} [{action}]: {type(e).__name__}: {str(e)[:300]}"
            try:
                step_result["screenshot"] = session.screenshot(f"FAIL_{case_id}_{i + 1}")
            except Exception:
                pass
            result["steps"].append(step_result)
            break
        result["steps"].append(step_result)
    # 清理阶段：主步骤 PASS/FAIL/SKIP 都执行。清理失败只在原结论为 PASS 时降级为 FAIL
    #（与原“清理步骤失败=用例失败”语义一致），已 FAIL/SKIP 的用例结论不被清理结果改写。
    for j, step in enumerate(cleanup_steps, start=len(main_steps) + 1):
        action = step.get("action")
        desc = step.get("desc", "")
        step_result = {"index": j, "action": action, "desc": desc, "status": "PASS",
                       "error": None, "phase": "cleanup"}
        try:
            if action in ACTION_MAP:
                ok = ACTION_MAP[action](session, step)
                if ok is False:
                    raise AssertionError(f"action {action} returned False")
            else:
                raise AssertionError(f"unknown action: {action}")
        except Exception as e:
            if isinstance(e, PreconditionBlocked):
                # 清理阶段因环境受限无法执行：不构成用例失败，仅记 SKIP
                step_result["status"] = "SKIP"
                step_result["error"] = f"前置条件不满足: {str(e)[:200]}"
                result["steps"].append(step_result)
                continue
            step_result["status"] = "FAIL"
            step_result["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            if result["status"] == "PASS":
                result["status"] = "FAIL"
                result["error"] = f"cleanup step {j} [{action}]: {type(e).__name__}: {str(e)[:300]}"
            try:
                step_result["screenshot"] = session.screenshot(f"FAIL_{case_id}_{j}")
            except Exception:
                pass
        result["steps"].append(step_result)
    result["end"] = datetime.now().isoformat()
    return result


def main():
    _validate_selector_aliases()
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="all", help="login|wan|status|reboot|security|wifi|lan|route|firewall|remote|voip|system|status_rest|network_rest|app_rest|all")
    ap.add_argument("--ui", default="html", help="UI 形态：html|new_ui|globe（用例目录 operators/intl/cases/real/<ui>/）")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--out", default=None, help="报告输出根目录（默认 reports/intl/<ui>/）")
    ap.add_argument("--cases", default=None, help="只跑指定用例 ID（逗号分隔，如 INTL-WAN-009,INTL-WAN-CRUD-001）")
    ap.add_argument("--exclude", default=None,
                    help="排除套件名或用例文件名（逗号分隔，如 reboot 或 reboot.json,login.json）；"
                         "--suite all 时用于裁剪全量回归范围")
    ap.add_argument("--fast", action="store_true",
                    help="提速模式：页面就绪轮询替代固定睡等 + 深链直达目标页 + real.wait 按 --wait-scale 折算"
                         "（登录会话复用已默认开启，如需关闭用 --no-reuse-session）")
    ap.add_argument("--wait-scale", type=float, default=None,
                    help="用例内 real.wait 的时长系数（默认：--fast 时 0.5，否则 1.0）")
    ap.add_argument("--no-reuse-session", action="store_true",
                    help="关闭登录会话复用（默认开启）：关闭后以 ensure_login 开头的用例"
                         "会在各自 context 内单独登录一次；未登录拦截类用例不受此开关影响")
    args = ap.parse_args()
    global UI_VARIANT, FAST_MODE, WAIT_SCALE, SESSION_REUSE
    UI_VARIANT = args.ui
    FAST_MODE = bool(args.fast)
    SESSION_REUSE = not args.no_reuse_session
    WAIT_SCALE = args.wait_scale if args.wait_scale is not None else (0.5 if FAST_MODE else 1.0)
    if FAST_MODE:
        print(f"[FAST] 提速模式：就绪轮询替代固定睡等；real.wait 系数={WAIT_SCALE}")
    # 报告按 UI 形态分目录归档。默认目录必须与报告生成器 tools/gen_intl_word.py
    # 的 REPORTS_DIR_HTML / REPORTS_DIR_NEW 保持一致，否则不加 --out 执行时结果会落到
    # 生成器永远不查的目录，导致「本轮已执行但报告找不到结果」。
    if args.out is None:
        _default_out = {"html": "reports/intl_real_html"}.get(args.ui, "reports/intl_real")
        args.out = os.path.join(ROOT, *_default_out.split("/"))

    cases_dir = os.path.join(ROOT, "operators", "intl", "cases", "real", args.ui)
    if not os.path.isdir(cases_dir):
        sys.exit(f"[err] 用例目录不存在: {cases_dir}（--ui {args.ui} 尚未建用例）")
    # 每个页面一个独立 json 文件：suite 名映射到该模块下各页面用例文件列表。
    # 顺序的唯一来源见 core.intl_suite_order（报告生成器同源引用，
    # 保证「报告测试项顺序 == 实际执行顺序」，避免两处各写一份顺序导致漂移）。
    suites = SUITES
    if args.suite == "all":
        # 副作用隔离排序：只读/低副作用套件在前，网络配置类（wifi/lan/firewall）居中，
        # 高危套件（system：恢复出厂/固件升级/管理端口/管理账号）与登录锁定类
        # （login/security）置末，避免其副作用波及其它套件造成级联失败。
        files = list(ALL_FILES)
    else:
        if args.suite not in suites:
            # 套件名拼错、或该套件已被移除（如 2026-09-18 删除的 mobile），给出可选清单而非 KeyError
            sys.exit(f"[err] 未知套件: {args.suite}；可选：{', '.join(suites)} 或 all")
        files = suites[args.suite]

    # --exclude：按套件名（映射到该套件全部文件）或用例文件名排除，all 与单套件均生效
    if args.exclude:
        ex_keys = {x.strip() for x in args.exclude.split(",") if x.strip()}
        ex_files = set()
        for k in ex_keys:
            ex_files.update(suites.get(k, []) or [])
            ex_files.add(k if k.endswith(".json") else f"{k}.json")
        dropped = [f for f in files if f in ex_files]
        files = [f for f in files if f not in ex_files]
        if dropped:
            print(f"[EXCLUDE] 已排除套件/文件: {', '.join(dropped)}")
        else:
            print(f"[EXCLUDE] 警告：--exclude {args.exclude} 未匹配到任何文件，未生效")

    all_cases = []
    for f in files:
        p = os.path.join(cases_dir, f)
        if os.path.exists(p):
            all_cases.extend(json.load(open(p, encoding="utf-8")))

    # 凭据占位符注入：用例中不硬编码账号密码，从环境变量/.env 读取。
    # 统一走 core.config.resolve_env_value 解析 ${VAR}/${VAR:-default}，
    # 覆盖用例中实际使用的 ${QCT_INTL_ADMIN_USER}/${QCT_INTL_ADMIN_PASS} 等前缀
    # （旧实现只替换 ${INTL_*}，与新用例命名不一致，会导致真机登录填入字面占位符）。
    def _inject(obj):
        if isinstance(obj, dict):
            return {k: _inject(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_inject(v) for v in obj]
        if isinstance(obj, str):
            return resolve_env_value(obj)
        return obj
    all_cases = _inject(all_cases)

    # 登录锁定用例（SEC-001/SEC-002）必须放最后：触发锁定后会影响后续用例
    _lockout_ids = LOCKOUT_IDS
    normal_cases = [c for c in all_cases if c.get("id") not in _lockout_ids]
    lockout_cases = [c for c in all_cases if c.get("id") in _lockout_ids]
    all_cases = normal_cases + lockout_cases

    # --cases 过滤：只跑指定用例（锁定用例排序逻辑仍然生效）。
    # 支持精确 ID（INTL-WAN-009）与 ID 前缀（INTL-WIFI-0 → 052~0xx），后者便于按批跑。
    if args.cases:
        keys = [c.strip() for c in args.cases.split(",") if c.strip()]
        # 形如 ...-052 / ...-001 的按精确 ID，其余按前缀（如 INTL-WIFI-0）
        exact = {k for k in keys if re.search(r"-\d{3}$", k)}
        prefix = tuple(k for k in keys if k not in exact)
        all_cases = [c for c in all_cases
                     if c.get("id") in exact or (prefix and str(c.get("id", "")).startswith(prefix))]
        print(f"[cases] --cases 过滤后 {len(all_cases)} 条（精确 {len(exact)} 个 / 前缀 {prefix or '无'}）")
        if not all_cases:
            sys.exit(f"[err] --cases 未匹配到任何用例: {args.cases}")

    os.makedirs(args.out, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(args.out, ts)
    os.makedirs(out_dir, exist_ok=True)

    summary = {"total": 0, "pass": 0, "fail": 0, "skip": 0, "cases": [], "start": datetime.now().isoformat()}
    # 会话复用按「用例是否声明复用语义」决定：本次范围内只要有用例以 ensure_login /
    # open_page 开头，就整轮只登录一次（未声明者不受影响，仍走各自原步骤）。
    reuse_cases = [c for c in all_cases if _uses_shared_session(c)]
    session_reuse_on = bool(SESSION_REUSE and reuse_cases)
    with sync_playwright() as p:
        # HTTPS 自签证书场景需忽略校验；纯 HTTP 场景该参数无副作用
        browser = p.chromium.launch(headless=not args.headful,
                                    args=["--ignore-certificate-errors"])
        # 会话复用：run 开始时登录一次，保存 storage_state 供声明了复用语义的用例注入，
        # 免去逐条用例重走登录表单（103 条 wifi 用例原先需 102 次登录 ≈ 8 分钟纯浪费）。
        if session_reuse_on:
            IntlSession._STATE_PATH = os.path.join(out_dir, "_session_state.json")
            _boot = browser.new_context(viewport={"width": 1600, "height": 900})
            _bpage = _boot.new_page()
            _bsess = IntlSession(_bpage, out_dir)
            _bpage.goto(f"{BASE_URL}/login.html", timeout=20000, wait_until="domcontentloaded")
            _bsess._wait_visible("#user_name", 8000)
            _bsess.login()
            _boot.storage_state(path=IntlSession._STATE_PATH)
            _boot.close()
            print(f"[SESSION] 已完成一次登录并保存会话存档；本次 {len(reuse_cases)}/{len(all_cases)} "
                  f"条用例复用该会话（其余用例保持各自独立登录/未登录前置）", flush=True)
        for case in all_cases:
            summary["total"] += 1
            t0 = datetime.now()
            if FAST_MODE:
                case = _fast_rewrite_case(case)
            # 每个用例使用独立 context，隔离页面状态
            # 设备形态：tags 含 device:mobile（或 device=mobile）→ Chrome 设备模拟（iPhone 13 移动视口/UA/触摸）
            # 注：2026-09-18 删除 mobile.json 后暂无用例使用本分支；且已删的 5 条手机端用例当时
            # 打的是 module:mobile 标签（非 device:mobile），因此从未真正触发过移动端模拟——
            # 若后续重启手机端用例，用例侧必须显式声明 device:mobile 才能生效。
            tags = case.get("tags", []) or []
            if case.get("device") == "mobile" or "device:mobile" in tags:
                ctx_kwargs = dict(p.devices["iPhone 13"])
            else:
                ctx_kwargs = {"viewport": {"width": 1600, "height": 900}}
            # 页面状态仍按用例隔离，只复用「已认证会话」这一件事，且仅注入给声明了复用
            # 语义的用例（首个步骤为 ensure_login / open_page）；未登录拦截、登录流程、
            # 错误密码等用例不注入，避免把它们本该处于的未登录态悄悄改成已登录。
            _first_act = (case.get("steps") or [{}])[0].get("action")
            if (session_reuse_on and IntlSession._STATE_PATH
                    and _first_act in ("real.ensure_login", "real.open_page")):
                ctx_kwargs["storage_state"] = IntlSession._STATE_PATH
            context = browser.new_context(**ctx_kwargs)
            page = context.new_page()
            session = IntlSession(page, out_dir)
            try:
                res = run_case(session, case, out_dir)
            except Exception as e:
                res = {"id": case.get("id"), "title": case.get("title"), "status": "ERROR",
                       "error": str(e)[:300], "steps": []}
            # 成功用例若未显式截图，自动补一张成果截图
            if res["status"] == "PASS":
                has_shot = any(st.get("detail") for st in res.get("steps", []))
                if not has_shot:
                    try:
                        shot = session.screenshot(f"OK_{case.get('id','case')}")
                        step = {"index": len(res.get("steps", [])) + 1, "action": "real.screenshot",
                                "desc": "用例成果截图", "status": "PASS", "detail": shot}
                        res.setdefault("steps", []).append(step)
                    except Exception:
                        pass
            context.close()
            # 每条用例耗时统计（秒，保留 1 位小数）
            res["duration_s"] = round((datetime.now() - t0).total_seconds(), 1)
            res["start"] = t0.isoformat()
            summary["cases"].append(res)
            if res["status"] == "PASS":
                summary["pass"] += 1
            elif res["status"] == "SKIP":
                summary["skip"] += 1
            else:
                summary["fail"] += 1
            print(f"[{res['status']}] {res['id']} - {res['title']} ({res['duration_s']}s) "
                  f"[{summary['total']}/{len(all_cases)}]", flush=True)
            if res.get("error"):
                print(f"    -> {res['error']}")
            # 增量落盘：每条用例结束即写 result.json，中途终止也能保住已完成结果
            _dump_result(summary, out_dir, planned=len(all_cases), partial=True)
        browser.close()

    summary["end"] = datetime.now().isoformat()
    summary["duration_s"] = round((datetime.now() - datetime.fromisoformat(summary["start"])).total_seconds(), 1)
    executed = summary["total"] - summary["skip"]
    summary["pass_rate"] = round(summary["pass"] / executed * 100, 1) if executed else 0
    result_file = _dump_result(summary, out_dir, planned=len(all_cases), partial=False)
    print(f"\n=== INTL 老 UI 真机测试完成 ===")
    print(f"总数: {summary['total']}  通过: {summary['pass']}  失败: {summary['fail']}  "
          f"跳过: {summary['skip']}  通过率: {summary['pass_rate']}%")
    print(f"结果: {result_file}")
    return summary


if __name__ == "__main__":
    main()
