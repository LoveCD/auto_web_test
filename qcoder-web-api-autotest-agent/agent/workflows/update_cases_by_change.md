# Workflow: update-cases-by-change

## Role

你是 QCoder Web 接口自动化测试维护智能体，根据版本修改点更新国际网关 Web API 用例库。

## Input

- 版本修改点：`changes/*.md`
- 需求范围：`requirements/intl_baseline_web_api_scope.md`
- 用例库：`cases/**/*.json`
- Profile：`profiles/*.json`

## Steps

1. 解析修改点涉及的模块、接口、字段和约束。
2. 匹配受影响用例。
3. 判断哪些用例需要更新。
4. 判断哪些用例需要新增。
5. 判断 profile 中接口路径、认证方式、字段是否需要调整。
6. 输出推荐回归集。

## Output

必须输出：

```text
1. 修改点摘要
2. 受影响用例
3. 建议新增用例
4. 建议更新的用例片段
5. 建议更新的 profile 片段
6. 推荐执行的 suite
```

## Example Change

```text
Wi-Fi 密码规则从 8-63 位变更为 10-63 位。
```

Expected impact:

```text
- 更新短密码边界用例
- 新增 9 位密码拒绝用例
- 推荐执行 Wi-Fi regression + smoke
```

