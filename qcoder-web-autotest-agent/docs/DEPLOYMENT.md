# 部署方法（Deployment）

本文档说明 QCoder Web AutoTest Agent 的部署方法：单机部署、真机接入、NL 用例生成器、CI/CD 集成与注意事项。

## 1. 部署架构

```text
┌───────────────────────────────────────────────────────────────┐
│                 执行节点（测试机 / CI Runner）                    │
│                                                               │
│  NL 用例生成器（离线，扫描 web 仓库 UI 源码）                      │
│    generator/generate_case.py                                 │
│        │  生成 operators/{op}/cases/generated/*.json           │
│        ▼                                                      │
│  run_suite.py ──► StepRunner ──► RealWebSession(Playwright)    │
│        │                          │  或 WebSession(Mock)       │
│        │                          ▼                            │
│        │                   浏览器(Chromium)                     │
│        │                     ┌────┴─────┐                      │
│        │                     ▼          ▼                      │
│  reports/<run_id>/      真实网关设备    Mock Web UI              │
│   result.json/html       (LAN 直连)    (127.0.0.1:8899)         │
│   screenshots/*.png      CM/INTL      离线/CI                   │
└───────────────────────────────────────────────────────────────┘
```

被测目标由 `--operator` + `--env` 决定：

| 组合 | 被测目标 | 场景 |
|---|---|---|
| `--operator cm --env real` | 烽火真机（如 HG3142F2） | 版本准入/回归 |
| `--operator cm --env mock` | Mock 服务 | 离线开发/CI |
| `--operator intl --env mock` | Mock 服务 | 离线开发/CI |
| `--operator intl --env real` | 国际版真机 | 有设备时 |

## 2. 单机部署（Windows / Linux / macOS）

```bash
# 1) 拷贝项目（需与 web 仓库同级或调整 generator 中源码路径）
# 2) 创建虚拟环境
python -m venv venv
venv/Scripts/activate            # Windows
source venv/bin/activate         # Linux/macOS

# 3) 安装依赖
pip install -r requirements.txt
playwright install chromium

# 4) 验证（Mock 链路，无需设备）
python mock_web_ui/server.py &          # 终端1（Windows: start python mock_web_ui/server.py）
python runner/run_suite.py --operator intl --env mock --suite smoke   # 终端2

# 5) 验证 NL 用例生成（离线）
python -m generator.generate_case --operator cm --query "测试wan连接页面vlan绑定功能"
```

### 2.1 Skill 部署（WorkBuddy / QCoder 双端）

本工具已封装为 **qcoder-web-autotest** 技能，随项目分发：

| 平台 | 部署方式 |
|---|---|
| WorkBuddy | 项目级技能已就位（`.workbuddy/skills/qcoder-web-autotest/`），打开项目会话即可自然语言触发 |
| QCoder | 将 `skill_dist/qcoder-web-autotest.zip` 导入 QCoder 技能中心（SkillHub 兼容格式）；或解压 `skill_dist/qcoder-web-autotest/` 到 skills 目录 |

验证部署是否生效：在对话中输入"测试wan连接页面vlan绑定功能"或"运行 CM 真机回归套件"，
AI 应能按 Skill 指引自动完成生成/执行/报告。

## 3. 真机接入

1. 测试机与网关设备同一局域网（设备默认 `192.168.1.1`）
2. 复制 `.env.example` 为 `.env` 并填写真机账号（敏感信息不写入代码库）：

```dotenv
QCT_CM_BASE_URL=http://192.168.1.1
QCT_CM_ADMIN_USER=<管理员账号>
QCT_CM_ADMIN_PASS=<管理员密码>
QCT_CM_USER_USER=<普通用户账号>
QCT_CM_USER_PASS=<普通用户密码>
```

`operators/cm/profile.json` 通过 `${QCT_*}` 占位符引用上述环境变量，运行时自动解析。

3. 连通性验证：

```bash
curl -s -o /dev/null -w "%{http_code}" http://192.168.1.1/   # 期望 200
python runner/run_suite.py --operator cm --env real --suite smoke
```

> 也可不写 .env，临时用 `--url http://x.x.x.x --admin-user xxx --admin-pass xxx` 覆盖。

## 4. NL 用例生成器部署

生成器**离线运行**，只依赖 web 仓库中的 UI 源码（Vue SPA 的 `content/pages/*.js`）：

- 源码路径配置：`generator/page_index.py` 中 `DEFAULT_UI_ROOTS`

```python
DEFAULT_UI_ROOTS = {
    "cm":   "<项目根>/web/web/UI/CM/fiberweb/html/src",
    "intl": "<项目根>/web/web/UI/INTL/fiberweb/html/src",
}
```

- 索引缓存在 `generator/index_cache/{operator}.json`，UI 源码更新后：

```bash
python -m generator.generate_case --operator cm --query "..." --refresh
```

- 生成产物：
  - 用例：`operators/{op}/cases/generated/{name}.json`（可直接被 runner 执行）
  - 报告：`operators/{op}/cases/generated/{name}_report.json`（token、匹配页、需求差距）

## 5. CI/CD 集成

```yaml
# GitLab CI 示例
stages: [test]
web-autotest:
  stage: test
  image: python:3.11
  before_script:
    - pip install -r requirements.txt
    - playwright install --with-deps chromium
    - python mock_web_ui/server.py &      # Mock 被测目标
    - sleep 2
  script:
    # 1) 需求用例自动生成（离线，UI 源码在仓库内）
    - python -m generator.generate_case --operator intl --query "测试wifi基础设置功能支持320MHZ频段设置"
    # 2) Mock 冒烟（无设备环境）
    - python runner/run_suite.py --operator intl --env mock --suite smoke
  artifacts:
    when: always
    paths: [reports/]
```

真机准入（有设备的内网 Runner）：

```bash
python runner/run_suite.py --operator cm --env real --suite smoke || \
  echo "准入失败，查看 reports/ 截图"
```

## 6. 目录结构

```text
qcoder-web-autotest-agent/
├── generator/               # NL 用例生成器
│   ├── page_index.py        #   UI 源码索引器（页面/元素/选项/校验规则）
│   ├── generate_case.py     #   自然语言 -> 用例 JSON（含差距检测）
│   └── index_cache/         #   索引缓存
├── operators/               # 运营商隔离配置
│   ├── cm/                  # 中国移动
│   │   ├── profile.json     #   双环境（real/mock）配置
│   │   ├── selectors.json   #   选择器
│   │   └── cases/           #   smoke/regression/mock_smoke/generated/
│   └── intl/                # 国际通用（结构同上）
├── keywords/
│   ├── real_keywords.py     # RealWebSession（真机 Playwright 会话）
│   └── web_keywords.py      # WebSession（Mock 会话）
├── runner/
│   ├── run_suite.py         # CLI 入口（--operator/--env/--suite）
│   └── report.py            # 报告输出
├── mock_web_ui/             # Mock 网关服务
└── reports/                 # 运行结果（result.json + screenshots/）
```

## 7. 注意事项

- **真机账号安全**：密码不要提交仓库，profile 用环境变量注入或本地覆盖
- **真机锁号**：连续 3 次错误密码锁定 1 分钟，负向用例间需间隔
- **危险操作**：恢复出厂、重启等用例只做**只读页面断言**，不实际触发
- **navigation 套件时长**：全菜单遍历约 10+ 分钟（每页截图 + 加载等待）
- **报告保留**：`reports/` 按时间戳累积，定期清理或由 CI artifact 管理
