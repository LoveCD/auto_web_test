#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真机探针：采集 wifiBasic（2.4G 基础设置页）的实际运行态。

用途：为「通用版用例落成 JSON」提供事实依据——局方、能力位、各控件当前值、
下拉选项集、Domain 是否禁用、元素 id 挂载的节点类型（input / div），
避免用猜测写断言。

一次性工具，采集完成后可删除。
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import load_dotenv  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

load_dotenv()
BASE = os.environ.get("QCT_INTL_BASE_URL", "http://192.168.1.1").rstrip("/")
USER = os.environ.get("QCT_INTL_ADMIN_USER", "admin")
PASS = os.environ.get("QCT_INTL_ADMIN_PASS", "")

SELS = {
    "Enable": "#fhId_Enable",
    "selSSID": "#fhId_selSSID",
    "OperatingStandards": "#fhId_OperatingStandards",
    "RegulatoryDomain": "#fhId_RegulatoryDomain",
    "OperatingChannelBandwidth": "#fhId_OperatingChannelBandwidth",
    "Channel": "#fhId_Channel",
    "GuardInterval": "#fhId_GuardInterval",
    "mruEnable": "#fhId_mruEnable",
    "AutoChannel": "#fhId_AutoChannel",
    "NoAutoChannel": "#fhId_NoAutoChannel",
    "onApply": "#fhId_onApply",
    "onDelete": "#fhId_onDelete",
}

READ_JS = """(sels) => {
  const out = {};
  for (const [k, s] of Object.entries(sels)) {
    const el = document.querySelector(s);
    if (!el) { out[k] = { exists: false }; continue; }
    const inner = el.querySelector('input, textarea');
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    out[k] = {
      exists: true,
      tag: el.tagName.toLowerCase(),
      cls: (el.className || '').toString().slice(0, 90),
      idOnInput: /^(INPUT|TEXTAREA)$/.test(el.tagName),
      innerTag: inner ? inner.tagName.toLowerCase() : null,
      value: (inner ? inner.value : el.innerText || '').trim().slice(0, 60),
      disabled: el.disabled === true || inner && inner.disabled === true
                || el.classList.contains('is-disabled')
                || !!el.closest('.is-disabled'),
      visible: rect.width > 0 && rect.height > 0 && style.display !== 'none'
               && style.visibility !== 'hidden',
      readonly: inner ? inner.readOnly : null,
    };
  }
  return out;
}"""

OPT_JS = """(sel) => {
  const out = [];
  document.querySelectorAll('.el-select-dropdown').forEach(p => {
    const r = p.getBoundingClientRect();
    const vis = r.width > 0 && r.height > 0 && window.getComputedStyle(p).display !== 'none';
    if (!vis) return;
    p.querySelectorAll('.el-select-dropdown__item').forEach(i => {
      out.push({ text: i.innerText.trim(), disabled: i.classList.contains('is-disabled') });
    });
  });
  return out;
}"""

SWITCH_JS = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const inp = el.querySelector('input[type=checkbox]');
  const sw = el.classList.contains('el-switch') ? el : el.closest('.el-switch');
  return {
    isCheckedClass: sw ? sw.classList.contains('is-checked') : null,
    inputChecked: inp ? inp.checked : null,
  };
}"""


def main():
    info = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
        page = ctx.new_page()
        page.goto(f"{BASE}/login.html", timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.fill("#user_name", USER)
        page.fill("#loginpp", PASS)
        page.click("#login_btn")
        page.wait_for_timeout(3500)
        print("[1] 登录后 URL:", page.url)

        # 设备上下文
        info["device_data"] = page.evaluate("""() => {
            const g = (window.g_device_data || window.top && window.top.g_device_data) || {};
            const keys = ['operator_name', 'wifi_cap', 'user', 'meshEnble', 'MeshMode'];
            const out = {};
            keys.forEach(k => { if (k in g) out[k] = g[k]; });
            out._all_top_keys = Object.keys(g).slice(0, 40);
            return out;
        }""")

        # 进页面
        for mid in ("#fhId_network_L1", "#fhId_wifiSettings_L2", "#fhId_wifiBasic_L3"):
            try:
                page.click(mid, timeout=8000)
                page.wait_for_timeout(2500)
            except Exception as e:
                print(f"[warn] 菜单 {mid} 点击失败: {type(e).__name__}")
        page.wait_for_timeout(2500)
        info["url"] = page.url

        info["controls"] = page.evaluate(READ_JS, SELS)
        info["switch_Enable"] = page.evaluate(SWITCH_JS, "#fhId_Enable")

        # 逐下拉采集选项
        ops = {}
        for name in ("OperatingStandards", "RegulatoryDomain",
                     "OperatingChannelBandwidth", "Channel", "GuardInterval"):
            sel = SELS[name]
            try:
                el = page.locator(sel).first
                if el.count() == 0:
                    ops[name] = "NOT_FOUND"
                    continue
                el.scroll_into_view_if_needed()
                el.click()
                page.wait_for_timeout(1200)
                ops[name] = page.evaluate(OPT_JS, sel)
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
            except Exception as e:
                ops[name] = f"ERR {type(e).__name__}: {str(e)[:120]}"
        info["options"] = ops

        # 页面是否处于只读（Mesh）态：找告警文案
        info["mesh_warn"] = page.evaluate(
            "() => document.body.innerText.includes('Multi-AP is enabled')")
        page.screenshot(path="/tmp/probe_wifibasic.png", full_page=True)
        browser.close()

    print(json.dumps(info, ensure_ascii=False, indent=2))
    with open("/tmp/probe_wifibasic.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print("\n[ok] 结果已写入 /tmp/probe_wifibasic.json")


if __name__ == "__main__":
    main()
