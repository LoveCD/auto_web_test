# Workflow: update-cases-by-change

## Role

你是 QCoder Web 自动化测试维护智能体，根据版本变更 log 记录自动分析受影响的用例。

## Input

- 变更 log：`changes/*.md` 或 `changes/*.txt`
- 需求范围：`requirements/intl_baseline_web_api_scope.md`、`requirements/intl_baseline_web_scope.md`
- 用例库：`cases/**/*.json`（API）、`cases/**/*.yaml`（Web UI）
- Profile：`profiles/*.json`（API）、`profiles/*.yaml`（Web UI selector）

## 输入格式自动识别

变更 log 不需要固定模板格式，AI 自动解析以下任意格式：

### 格式 1：版本 release notes

```text
## V2.1.0
- 修改 Wi-Fi 密码最小长度从 8 改为 10
- 新增频段选择功能（2.4G/5G/自动）
- 修复 WAN 连接模式切换问题
```

### 格式 2：提交记录

```text
feat: add band select dropdown on wifi page
fix: password minimum length changed to 10
refactor: WAN mode switching logic
```

### 格式 3：结构化变更说明（用 _template.md 填写）

包含变更类型、旧值/新值表格等，分析精度最高。

### 格式 4：自然语言描述

一句话描述变更，如"Wi-Fi 密码规则从 8-63 改为 10-63"。

## 变更类型识别

AI 从 changelog 中识别以下变更类型：

### 类型 1：UI 结构变更（selector 层）
- 关键词：页面重构、元素新增/删除、id 改名、框架迁移
- **影响**：selector profile 需更新，相关断言用例需更新

### 类型 2：业务规则变更（逻辑层）
- 关键词：校验规则、长度变化、格式要求、新增配置项
- **影响**：边界用例需更新，可能需新增用例

### 类型 3：API 契约变更（接口层）
- 关键词：接口路径、字段增删改、状态码、响应体
- **影响**：API 用例需更新，profile 的 api_paths 需更新

### 类型 4：页面路由变更
- 关键词：URL 路径、新增页面、页面合并/拆分
- **影响**：page_routes 需更新，导航用例需更新

### 类型 5：安全策略变更
- 关键词：锁定阈值、会话超时、密码策略、HTTPS
- **影响**：安全基线用例需更新（锁定状态机、会话管理、越权访问）

### 类型 6：多语言/文案变更
- 关键词：新增语言、文案调整、i18n
- **影响**：文本断言用例需更新（不得依赖固定文本断言，改用结构性 selector），需新增语言切换用例

### 类型 7：持久化策略变更
- 关键词：恢复出厂策略、升级配置迁移、重启保持
- **影响**：持久化一致性用例需更新，需新增对应状态验证用例

## Steps

1. 解析 changelog，提取变更条目（自动去掉 markdown 装饰和 commit 前缀）。
2. 根据关键词推断受影响模块（Login/Status/WiFi/WAN/System）。
3. 识别变更类型（UI 结构 / 业务规则 / API 契约 / 页面路由）。
4. 匹配受影响用例（同时扫描 JSON 和 YAML 用例）。
5. 判断哪些用例需要更新。
6. 判断哪些用例需要新增。
7. 判断哪些用例需要废弃（如有）。
8. 判断 profile 是否需要调整。
9. 输出推荐回归集。

## Output

必须输出：

```text
1. 解析到的变更条目（逐条列出）
2. 变更摘要（变更类型 + 涉及模块）
3. 受影响用例列表（用例 ID + 影响原因）
4. 建议新增用例（含 YAML/JSON 片段）
5. 建议更新用例（含修改前/后对比）
6. 建议废弃用例（如有）
7. Profile 更新建议
8. 推荐执行的 suite（smoke + 哪些 regression 模块）
9. 分析置信度（高/中/低）
```

## 分析置信度说明

| 置信度 | 输入条件 | 说明 |
|---|---|---|
| 高 | changelog 条目 ≥3 条 + 能匹配到具体建议规则 | 有足够信息做精确分析 |
| 中 | changelog 条目 ≥1 条 | 能识别模块和方向，但可能缺细节 |
| 低 | 输入过短或无有效条目 | 只能做模块级推断 |

低置信度时，AI 应主动追问："请提供更详细的变更 log，如具体的字段名、规则变化值等，以提高分析精度。"

## 内置变更规则匹配

系统内置以下关键词→建议映射，自动从 changelog 中匹配：

| 关键词 | 匹配规则 | 自动建议 |
|---|---|---|
| password/密码 + 8→10 | 密码最小长度变化 | 更新边界用例 + 新增 9 位拒绝用例 |
| band/频段 | 频段选择功能 | 新增 band 字段用例 |
| applied/生效 | API 响应新增字段 | 新增 applied 断言 |
| reboot/重启 | 重启流程变化 | 验证重启流程用例 + 重启后配置保持用例 |
| pppoe/dhcp/wan mode | WAN 模式变化 | 更新 WAN 模式切换用例 |
| firmware/固件/升级 | 固件升级功能 | 新增升级流程用例 + 升级后版本/配置断言 |
| lock/锁定/lockout | 登录锁定策略变化 | 新增锁定状态机用例（N 次失败→锁定→锁定中正确密码拒绝→解锁） |
| factory/恢复出厂/reset | 恢复出厂策略变化 | 新增恢复出厂一致性用例（配置回默认 + 重新登录） |
| session/会话/timeout | 会话策略变化 | 新增会话超时/退出后访问用例 |
| language/语言/i18n/多语言 | 多语言功能变化 | 新增语言切换用例；检查文本断言依赖 |

扩展规则：在 `agent_cli.py` 的 `CHANGE_RULES` 列表中添加新规则即可。
