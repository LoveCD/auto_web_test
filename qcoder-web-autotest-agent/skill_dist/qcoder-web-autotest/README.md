# QCoder Web AutoTest Agent

运营商网关 Web UI 端到端自动化测试技能（QCoder SkillHub 兼容格式）。

## 能力

- **双运营商**：CM（中国移动）/ INTL（国际），目录化扩展
- **双环境**：真机 Playwright（`--env real`，含截图）/ 离线 Mock（`--env mock`，无设备可跑）
- **自然语言生成用例**：`python -m generator.generate_case --operator cm --query "测试wan连接页面vlan绑定功能"`
- **全菜单遍历截图**：navigation 套件自动展开 L1→L2→L3 菜单逐页截图
- 冒烟 / 回归套件执行、JSON/HTML 报告、失败自动截图

## 快速开始

```bash
cd qcoder-web-autotest-agent
pip install -r requirements.txt
playwright install chromium

# 真机冒烟（设备 192.168.1.1 可达时）
python runner/run_suite.py --operator cm --env real --suite smoke

# 离线 Mock
python mock_web_ui/server.py
python runner/run_suite.py --operator cm --env mock --suite mock_smoke

# 自然语言生成用例
python -m generator.generate_case --operator cm --query "测试wifi基础设置功能支持320MHZ频段设置"
```

## 文档

- `docs/USAGE.md` — 完整使用方法（命令矩阵 / NL 生成器 / 用例规范）
- `docs/DEPLOYMENT.md` — 部署方法
- `docs/IMPLEMENTATION_EFFECTS.md` — 实现效果与覆盖矩阵
- `SKILL.md` — 本技能操作指南

## 版本

v2.0.0 — 双运营商重构 + 真机适配 + NL 用例生成器 + 双端（WorkBuddy/QCoder）封装
