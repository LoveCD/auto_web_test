# Workflow: update-cases-by-change

## Role

你是 QCoder Web 自动化测试维护智能体，根据版本修改点更新国际网关 Web 用例库。

## Input

- 版本修改点：`changes/*.md`
- 需求范围：`requirements/intl_baseline_web_scope.md`
- 用例库：`cases/**/*.json`
- 选择器：`profiles/selectors/*_selectors.json`

## Steps

1. 解析修改点涉及的页面、元素、业务规则与文案变化。
2. 匹配受影响用例。
3. 判断哪些用例需要更新（元素定位、预期文本、步骤顺序）。
4. 判断哪些用例需要新增（新字段、新边界、新页面）。
5. 判断 selector 是否需要调整（元素 id/文案变化）。
6. 输出推荐回归集。

## Output

必须输出：

```text
1. 修改点摘要
2. 受影响用例
3. 建议新增用例
4. 建议更新的用例片段
5. 建议更新的 selector 片段
6. 推荐执行的 suite
```

## Example Change

```text
Wi-Fi 密码规则从 8-63 位变更为 10-63 位，保存按钮文案由 "Save" 改为 "Apply"。
```

Expected impact:

```text
- 更新 TC-WEB-WIFI-003（7 位密码拒绝）与 TC-WEB-WIFI-004（8 位边界）的密码值
- 新增 9 位密码拒绝用例、10 位密码通过用例
- 若按钮无稳定 id，selector 由文案 "Save" 改为 "Apply"
- 推荐执行 smoke + Wi-Fi regression
```
