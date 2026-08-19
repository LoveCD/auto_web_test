QCoder Web AutoTest Agent 增量补丁包
========================================================
补丁版本 : commit 0ced2d5   基线版本 : commit 801d3c6
范围 : 测试用例设计规则对齐业界主流(家庭网关 Web 自动化)
--------------------------------------------------------
包含文件(7个,目录结构与仓库一致):
  SKILL.md / agent_cli.py
  agent/workflows/generate_cases.md
  agent/workflows/coverage_review.md
  agent/workflows/select_regression.md
  agent/workflows/update_cases_by_change.md
  keywords/web_keywords.py
--------------------------------------------------------
主要变更:
1. generate_cases.md
   - BVA三点法(上点/内点/离点),禁止只测越界拒绝
   - 等价类/状态迁移(登录锁定)/并发会话规则
   - CRUD一致性 write-read-verify(改后回读断言)
   - 未授权访问/配置恢复/参数关联判定表/参数化
   - i18n多语言/容量上限/性能阈值规则
   - 受控tags词表/P2判定标准/等待与并行约束
   - 新增"嵌入式家庭网关专项测试规则"章节
2. coverage_review.md
   - 覆盖Web UI(YAML)用例库;专项维度
     crud/persist/security/i18n/perf/capacity/compat
   - BVA完整性核查、tags词表规范核查
3. select_regression.md
   - 用例库输入补YAML;flaky治理规则
   - 持久化/认证变更强制包含对应用例
4. update_cases_by_change.md + agent_cli.py
   - 变更类型4类扩到7类(安全策略/多语言/持久化策略)
   - CHANGE_RULES 6条扩到10条(lock/factory/session/language)
5. keywords/web_keywords.py
   - web.login显式断言 expect:true/false,兼容旧用例
6. SKILL.md
   - NEVER规则6条扩到8条
   - Selector优先级表调整(text型降级,i18n友好)
--------------------------------------------------------
升级步骤:
1. 解压本包到目标仓库根目录,目录结构合并覆盖
2. 纯Python/MD文件,无新增依赖,无需pip安装
3. 验证: ast.parse(agent_cli.py) 应通过
   python agent_cli.py coverage-review 正常输出
   python agent_cli.py update-cases --change changes/v1.0.1_wifi_change.md
4. 回归验证(Mock网关需启动):
   run-web-suite --suite smoke --profile intl_gateway_web
   run-web-suite --suite regression --profile intl_gateway_web
--------------------------------------------------------
注意事项:
- 目标环境需与基线801d3c6一致,自改文件请先对比
- 若改过agent_cli.py/web_keywords.py,覆盖前比对差异
- 用例库cases/、profiles/、Mock网关不在补丁范围
