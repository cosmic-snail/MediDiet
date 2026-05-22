# MediDiet 测试文档

版本：0.1.4
目标读者：测试人员、QA、代码 reviewer、后续维护开发者。

## 1. 测试目标

当前测试集用于验证推荐引擎核心逻辑是否符合 MVP 设计：

- 领域模型使用枚举和 `ConceptCode`，避免自由文本业务匹配。
- 输入边界值和非法值能被拒绝。
- 规则包可以表达慢病、禁忌、营养标签和复杂上限。
- 安全门禁能把高风险和低置信度场景转人工审核。
- 下一餐营养目标能考虑当天摄入和滚动窗口。
- 菜单匹配能硬排除不安全候选并稳定排序。
- 推荐引擎能输出推荐、拒绝、人工审核三类路径。
- 输出 trace 包含结构化整数 code，便于审计和测试。
- 扩展端口能稳定表达外部系统请求和领域事件。

测试集不证明：

- 医学阈值已经临床有效。
- 真实图片识别准确。
- 真实外卖平台数据可靠。
- 生产服务性能、并发、鉴权、隐私合规已经完成。

## 2. 测试运行方式

运行后端与知识库全量测试：

```bash
PYTHONPATH=src:knowledge/src pytest tests/ knowledge/tests/ --rootdir=. -q
```

运行指定测试文件：

```bash
PYTHONPATH=src:knowledge/src pytest tests/test_safety.py -v --rootdir=.
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_store.py -v --rootdir=.
```

运行指定测试用例：

```bash
PYTHONPATH=src:knowledge/src pytest tests/test_engine.py::RecommendationEngineTest::test_routes_safety_events_to_human_review -v --rootdir=.
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_store.py::TestRuleStoreVersioning::test_publish_version -v --rootdir=.
```

运行前端原型测试与构建检查：

```bash
cd apps/mini-program-prototype
npm run test
npm run build
```

当前后端与知识库全量测试数量：254 个（含 2 个默认跳过的真实 LLM smoke test）。普通全量测试默认离线运行。

当前前端原型测试数量：60 个。前端测试默认离线运行，通过 mocked `fetch` 覆盖 HTTP adapter 行为。

## 3. 测试文件总览

| 测试文件 | 覆盖模块 | 主要风险 |
| --- | --- | --- |
| `tests/test_domain.py` | `domain.py` | 数据模型类型错误、非法值、字符串混用。 |
| `tests/test_rules.py` | `rules.py` | 规则包缺失、阈值表达错误、滚动窗口错误。 |
| `tests/test_safety.py` | `safety.py` | 过敏/禁忌未阻断、低置信度未转人工、日志缺失。 |
| `tests/test_nutrition.py` | `nutrition.py` | 今日摄入聚合错误、每日/滚动/单餐限额错误。 |
| `tests/test_planner.py` | `planner.py` | 营养目标未转成正确标签和建议。 |
| `tests/test_matcher.py` | `matcher.py` | 菜单排除错误、排序错误、排除 code 缺失。 |
| `tests/test_explainer_trace.py` | `explainer.py`, `trace.py` | 解释不稳定、trace 缺字段、敏感字段泄漏。 |
| `tests/test_llm.py` | `llm.py` | LLM 脱敏、fallback、安全输出校验、问答范围和 provider 请求错误。 |
| `tests/test_llm_deepseek_smoke.py` | `llm.py`, DeepSeek/OpenAI-compatible API | 真实 provider 配置和返回格式，仅显式启用时运行。 |
| `tests/test_service.py` | `service.py` | HTTP 应用服务 DTO 转换、内存状态、推荐编排、营养师评审记录和 LLM fallback metadata。 |
| `tests/test_http_server.py` | `server.py`, `service.py` | FastAPI endpoints、payload 校验、统一错误响应、推荐响应结构和缺菜单/LLM provider error。 |
| `tests/test_http_llm_smoke.py` | `server.py`, `llm.py`, DeepSeek/OpenAI-compatible API | 真实 HTTP 推荐 + LLM 增强链路，仅显式启用时运行。 |
| `tests/test_engine.py` | `engine.py`, `fixtures.py` | 推荐主流程编排错误；在线知识检索增强、静默降级。 |
| `tests/test_ports.py` | `ports.py` | 外部扩展契约不稳定、时间/枚举非法值、知识库端口协议。 |
| `tests/test_public_api.py` | `__init__.py` | 顶层公共 API 意外破坏。 |
| `tests/test_knowledge_bridge.py` | `knowledge_bridge.py`, `ports.py` | 端口适配器类型转换错误、版本加载、检索委托。 |
| `tests/test_knowledge_integration.py` | `knowledge_bridge.py`, `knowledge/*`, `engine.py`, `nutrition.py`, `matcher.py` | Phase 1/2/3 知识库端到端流程：文档导入→向量索引→规则发布→加载→检索→在线增强推荐→缺口补尝→多样性评分。 |

### 知识库包测试文件

| 测试文件 | 覆盖模块 | 主要风险 |
| --- | --- | --- |
| `knowledge/tests/test_schema.py` | `schema.py` | 数据模型校验、非法字段值、类型约束。 |
| `knowledge/tests/test_store.py` | `store.py` | 规则 CRUD、JSON 持久化、版本化发布与加载。 |
| `knowledge/tests/test_documents.py` | `documents.py` | 文档导入、段落分块、元数据管理、文件读取。 |
| `knowledge/tests/test_vectordb.py` | `vectordb.py` | ChromaDB 索引、语义搜索、相关性分数、删除操作。 |
| `knowledge/tests/test_loader.py` | `loader.py` | 目录批量导入、文件过滤、可选索引。 |
| `knowledge/tests/test_extractor.py` | `extractor.py` | LLM 两阶段规则提取、交叉验证、MockLLMProvider 适配。 |
| `knowledge/tests/test_curator.py` | `curator.py` | 规则审核、发布、人工归因。 |

### 前端原型测试文件

| 测试文件 | 覆盖模块 | 主要风险 |
| --- | --- | --- |
| `apps/mini-program-prototype/src/state.test.ts` | `state.ts` | 多患者状态隔离、当前患者切换、摄入和推荐串台、营养师审核结果回写。 |
| `apps/mini-program-prototype/src/features/patient/PatientWorkspace.test.tsx` | `PatientWorkspace.tsx` | 患者身份选择器、健康资料摘要、关键风险确认状态、空摄入状态、患者侧推荐/拒绝/待审核展示。 |
| `apps/mini-program-prototype/src/App.test.tsx` | `App.tsx` | 角色切换、营养师审核结果回到患者端、当前患者后端推荐请求。 |
| `apps/mini-program-prototype/src/api/medidietApi.test.ts` | `api/medidietApi.ts` | 患者资料 seed、摄入记录增量补写、跨患者摄入隔离、推荐请求 payload、结构化错误。 |
| `apps/mini-program-prototype/src/api/adapters.test.ts` | `api/adapters.ts` | 前后端 DTO 转换、概念编码、推荐响应映射。 |
| `apps/mini-program-prototype/src/features/review/DietitianWorkspace.test.tsx` | `DietitianWorkspace.tsx` | 审核队列、Trace 展示、审核动作。 |
| `apps/mini-program-prototype/src/features/catering/CateringWorkspace.test.tsx` | `CateringWorkspace.tsx` | 菜单可售状态、营养信息展示、履约状态。 |
| `apps/mini-program-prototype/src/fixtures.test.ts` | `fixtures.ts` | 演示数据完整性、患者/菜单/推荐 fixture 结构。 |
| `apps/mini-program-prototype/src/contracts.test.ts` | `contracts.ts` | 前端枚举、餐次名称、推荐结果状态映射。 |
| `apps/mini-program-prototype/src/components/RoleSwitcher.test.tsx` | `RoleSwitcher.tsx` | 三角色切换入口和可访问状态。 |

## 4. 功能覆盖矩阵

| 功能点 | 自动化覆盖 | 关键测试 |
| --- | --- | --- |
| 包可导入 | 已覆盖 | `DomainSmokeTest.test_package_imports` |
| 概念注册表 | 已覆盖 | `test_registry_returns_registered_concept_codes`, `test_registry_rejects_unknown_or_malformed_codes` |
| 患者疾病/过敏/禁忌使用 `ConceptCode` | 已覆盖 | `test_patient_profile_uses_concept_codes_for_medical_constraints` |
| 错误 `ConceptCode.kind` 被拒绝 | 已覆盖 | `test_patient_profile_rejects_wrong_code_kinds`, `test_condition_rule_rejects_wrong_concept_kinds` |
| 患者年龄/身高/体重边界 | 已覆盖 | `test_patient_profile_rejects_invalid_numeric_boundaries` |
| 营养值接受浮点数 | 已覆盖 | `test_nutrients_accept_float_values_and_add` |
| 营养值拒绝负值、非有限值、过大值 | 已覆盖 | `test_nutrients_reject_negative_non_finite_and_absurd_values` |
| 菜单过敏原匹配 | 已覆盖 | `test_menu_item_allergen_matching_uses_code_sets` |
| 规则包版本和来源 | 已覆盖 | `test_rule_pack_has_version_sources_and_registry` |
| 高血压低钠/单餐钠限制 | 已覆盖 | `test_hypertension_rule_uses_table_driven_limits` |
| 糖尿病每日糖上限和滚动窗口糖上限 | 已覆盖 | `test_diabetes_rule_supports_daily_and_rolling_sugar_limits` |
| 非法 `NutrientLimit` 边界和窗口 | 已覆盖 | `test_nutrient_limit_rejects_invalid_boundaries_and_windows` |
| 安全事件使用整数枚举 code | 已覆盖 | `test_safety_events_use_integer_enum_codes_not_strings` |
| 过敏命中 hard block | 已覆盖 | `test_allergy_match_is_hard_block_and_warning_log` |
| 患者风险字段未确认转人工 | 已覆盖 | `test_unconfirmed_profile_requires_review_and_warning_log` |
| 低置信度摄入转人工 | 已覆盖 | `test_low_confidence_intake_requires_review_and_warning_log` |
| 菜单营养上限 hard block | 已覆盖 | `test_menu_per_meal_nutrient_limit_is_hard_block_and_warning_log` |
| 安全日志不产生低等级海量日志 | 已覆盖 | `test_safe_loop_does_not_emit_below_warning_logs` |
| 默认 logger 不污染 stderr | 已覆盖 | `test_default_logger_does_not_write_warning_to_stderr` |
| 今日摄入聚合 | 已覆盖 | `test_aggregates_daily_totals_with_float_values` |
| 低置信度摄入仍计入营养统计 | 已覆盖 | `test_low_confidence_records_are_reported_but_still_counted` |
| 下一餐目标使用概念标签 | 已覆盖 | `test_next_meal_target_uses_concept_tags_not_strings` |
| 每日糖剩余量 | 已覆盖 | `test_daily_sugar_limit_uses_remaining_allowance` |
| 滚动窗口糖剩余量 | 已覆盖 | `test_rolling_sugar_limit_counts_only_records_inside_window` |
| 单餐限制不扣减当日摄入 | 已覆盖 | `test_per_meal_limit_is_carried_without_daily_consumption` |
| 餐食方案低钠建议 | 已覆盖 | `test_generates_low_sodium_plan_from_per_meal_limit` |
| 餐食方案控糖/控主食建议 | 已覆盖 | `test_generates_controlled_carbs_plan_from_daily_or_rolling_sugar_limits` |
| 餐食建议使用整数枚举 | 已覆盖 | `test_plan_uses_concept_codes_and_integer_instruction_enums` |
| `MealLabel` 拒绝字符串 | 已覆盖 | `test_rejects_string_meal_label` in planner and engine |
| 菜单 avoid tag 排除 | 已覆盖 | `test_excludes_avoid_tags_with_integer_rejection_code` |
| 菜单单餐营养超限排除 | 已覆盖 | `test_excludes_items_exceeding_per_meal_nutrient_limit` |
| 不可用菜单排除 | 已覆盖 | `test_excludes_unavailable_items` |
| 菜单排序考虑营养标签、口味、价格、距离、可靠性 | 已覆盖 | `test_ranks_safe_items_by_tags_preference_price_distance_and_reliability` |
| 推荐成功路径 | 已覆盖 | `test_recommends_safe_ranked_item_and_records_trace` |
| 所有候选被排除时拒绝推荐 | 已覆盖 | `test_refuses_when_matcher_excludes_all_candidates` |
| 安全事件触发人工审核 | 已覆盖 | `test_routes_safety_events_to_human_review` |
| demo fixture 能输出 trace JSON | 已覆盖 | `test_fixture_demo_returns_trace_json` |
| 患者解释稳定且为安全模板 | 已覆盖 | `test_patient_explanation_is_deterministic_safe_chinese_text` |
| 医生解释使用结构化整数 code | 已覆盖 | `test_clinician_explanation_uses_structured_integer_codes` |
| trace camelCase 序列化 | 已覆盖 | `test_trace_serializes_camel_case_context_with_integer_codes` |
| trace 不接受敏感字段 | 已覆盖 | `test_trace_does_not_accept_sensitive_patient_fields` |
| 请求 envelope 使用 timezone-aware 时间 | 已覆盖 | `test_request_envelope_carries_version_source_and_aware_time` |
| envelope 拒绝字符串时间和 naive datetime | 已覆盖 | `test_request_envelope_rejects_string_or_naive_time` |
| 摄入估算请求使用图片 URI 和 `MealLabel` | 已覆盖 | `test_intake_request_carries_image_reference_and_meal_label` |
| 领域事件稳定名称和整数 payload | 已覆盖 | `test_domain_event_names_are_stable_and_payload_can_carry_integer_codes` |
| 顶层公共 API | 已覆盖 | `test_engine_exports_are_available` |
| 知识库数据模型校验 | 已覆盖 | `test_schema.py` 全覆盖（6 个 dataclass + 边界值） |
| 规则存储 CRUD + 版本化 | 已覆盖 | `test_store.py` 全覆盖（CRUD、持久化、版本发布/加载） |
| 文档导入与分块 | 已覆盖 | `test_documents.py` 全覆盖（文本导入、文件导入、段落分块） |
| ChromaDB 向量索引与搜索 | 已覆盖 | `test_vectordb.py` 全覆盖（索引、语义搜索、top_k、删除） |
| 批量文档加载 | 已覆盖 | `test_loader.py` 全覆盖（目录导入、文件过滤、索引） |
| KnowledgeRuleProvider 端口适配 | 已覆盖 | `test_load_rule_pack_from_store`, `test_list_versions`, `test_load_latest_when_no_version_specified` |
| KnowledgeRetriever 端口适配 | 已覆盖 | `test_search_delegates_to_vectordb`, `test_retrieve_context`, `test_explain_rule_returns_source_info` |
| 端口 Protocol 类型检查 | 已覆盖 | `isinstance(provider, RuleProviderPort)`, `isinstance(retriever, KnowledgePort)` |
| 知识库端到端集成（Phase 1） | 已覆盖 | `test_full_workflow`（导入→索引→规则发布→加载→检索→解释） |
| LLM 规则提取与交叉验证（Phase 2） | 已覆盖 | `test_full_extraction_pipeline`（导入→索引→提取→审核→发布→加载→验证） |
| 在线引擎 + 缺口补尝 + 多样性 + 知识片段（Phase 3） | 已覆盖 | `test_online_engine_with_gap_compensation` |
| 在线知识检索增强解释 | 已覆盖 | `test_engine_with_knowledge_includes_snippets` |
| 知识检索失败静默降级 | 已覆盖 | `test_engine_with_failing_knowledge_degrades_gracefully` |
| 无知识库时无 snippets | 已覆盖 | `test_engine_without_knowledge_has_no_snippets` |
| 营养素缺口补尝（低蛋白→lean_protein） | 已覆盖 | `test_compensation_tags_low_protein_adds_lean_protein` |
| 营养素缺口补尝（低纤维→high_fiber） | 已覆盖 | `test_compensation_tags_low_fiber_adds_high_fiber` |
| 缺口补尝跨记录合并 | 已覆盖 | `test_compensation_tags_combines_across_records` |
| 缺口补尝空记录/足够时返回空 | 已覆盖 | `test_compensation_tags_empty_records_returns_empty`, `test_compensation_tags_adequate_meal_returns_empty` |
| 食材多样性评分（重复食材扣分） | 已覆盖 | `test_repeated_ingredient_penalty_reduces_score` |
| 多样性评分多食材累加 | 已覆盖 | `test_multiple_repeated_ingredients_accumulate_penalty` |
| 多样性评分默认空不影响 | 已覆盖 | `test_recent_ingredients_default_empty_has_no_effect` |
| LLM fallback 保留 knowledge snippets | 已覆盖 | `test_fallback_preserves_knowledge_snippets_from_deterministic_clinician_payload` |
| KnowledgeSnippet / KnowledgeContext | 已覆盖 | `test_valid_snippet`, `test_valid_context` |
| RuleProviderPort / KnowledgePort 协议 | 已覆盖 | `test_protocol_is_usable_for_type_checking` |
| 前端多患者初始状态和当前患者切换 | 已覆盖 | `state.test.ts` 中 `initializes multiple patients...`, `switches the active patient...` |
| 前端摄入和推荐按患者隔离 | 已覆盖 | `state.test.ts` 中 `adds manually corrected intake records only to the active patient`, `creates simulated recommendation states only for the active patient` |
| 前端审核等待不泄漏其它患者 trace | 已覆盖 | `state.test.ts` 中 CKD review mode regression |
| 患者端身份选择器与健康资料摘要 | 已覆盖 | `PatientWorkspace.test.tsx` 中 active patient selector、CKD patient details、unknown concept fallback |
| 患者端空摄入状态 | 已覆盖 | `PatientWorkspace.test.tsx` 中 `shows an empty state...` |
| 前端推荐请求使用当前患者 | 已覆盖 | `App.test.tsx` 中 switched-patient backend request |
| HTTP adapter 摄入记录增量补写 | 已覆盖 | `medidietApi.test.ts` 中 missing intake records test |
| HTTP adapter 跨患者 seed 隔离 | 已覆盖 | `medidietApi.test.ts` 中 selected patient intake records test |

## 5. 关键业务路径测试

### 5.1 推荐成功路径

覆盖目标：

- 安全门禁通过。
- 计算下一餐营养目标。
- 生成餐食计划。
- 匹配并排序候选菜单。
- 返回 `Outcome.RECOMMENDED`。
- trace 记录规则版本、分数、患者解释和医生解释。

关键测试：

- `tests/test_engine.py::test_recommends_safe_ranked_item_and_records_trace`

### 5.2 拒绝推荐路径

覆盖目标：

- 安全门禁通过，但菜单候选全部被 matcher 排除。
- 返回 `Outcome.REFUSED`。
- 不返回推荐菜单项。
- trace 中保存 `MatchRejectionCode` 整数 code。

关键测试：

- `tests/test_engine.py::test_refuses_when_matcher_excludes_all_candidates`

### 5.3 人工审核路径

覆盖目标：

- 过敏、未确认风险字段、低置信度或营养硬上限触发安全事件。
- 返回 `Outcome.HUMAN_REVIEW_REQUIRED`。
- 不返回推荐菜单项。
- trace 中保存 `SafetyCode` 整数 code。

关键测试：

- `tests/test_engine.py::test_routes_safety_events_to_human_review`
- `tests/test_safety.py`

## 6. 边界值覆盖

### 6.1 已覆盖边界

- 年龄小于 0、大于 130、非整数。
- 身高小于等于 0、过大。
- 体重小于等于 0、过大。
- 营养值负数、非有限值、过大值。
- 置信度小于 0、大于 1。
- `NutrientLimit.max_value` 非正数、非有限值、过大值。
- `ROLLING_WINDOW` 缺少或使用非法 `window_hours`。
- 非滚动窗口错误传入 `window_hours`。
- 字符串 `MealLabel`。
- naive datetime。
- 字符串 datetime。
- 错误 `ConceptCode.kind`。

### 6.2 仍建议补充的边界

这些不影响当前 MVP 验收，但后续生产化建议补充：

- 空 `patient_id`、空 `item_id`、空 `merchant_id` 的策略。
- 多疾病规则冲突时的优先级。
- 大量菜单候选项下的性能和日志量。
- `Preference.disliked_ingredients` 的硬排除或降权策略。
- 多个 accepted 菜单项推荐策略。
- `Outcome.DOWNGRADED` 的实际业务路径。
- 不同 timezone 下跨日摄入统计。
- 规则包多版本选择、回滚和兼容性。

## 7. 日志测试覆盖

当前日志相关测试验证：

- 安全事件会写 warning 日志。
- warning 日志包含整数 code。
- 文件日志包含时间戳、进程号、线程号。
- 安全循环中不会写入低于 warning 的日志。
- 默认 logger 不写 stderr。

未覆盖但生产建议补充：

- 日志轮转。
- 日志脱敏。
- 日志存储失败时的服务级处理。
- 多进程服务中的日志一致性。

## 8. Trace 和解释测试覆盖

当前测试验证：

- 患者解释由模板生成，不凭空生成医学建议。
- 医生解释包含结构化 safety events、exclusions、scores、matched tags。
- trace JSON 使用 camelCase。
- safety code 和 rejection code 输出为整数。
- trace 不接受任意敏感字段。

人工测试建议：

- 检查患者解释是否对普通用户足够清晰。
- 检查医生解释是否足以定位规则命中原因。
- 检查拒绝推荐和人工审核提示是否避免过度承诺。

## 9. 集成测试

当前仓库包含以下集成测试：

| 测试 | 覆盖范围 | 说明 |
| --- | --- | --- |
| `tests/test_knowledge_integration.py::TestPhase1EndToEnd` | `knowledge` 包 → `knowledge_bridge` → `medidiet` | Phase 1 端到端：文档导入、向量索引、规则创建发布、RulePack 加载、语义检索、解释生成。 |
| `tests/test_knowledge_integration.py::TestPhase2EndToEnd` | `knowledge/*` → `extractor` → `curator` → `knowledge_bridge` | Phase 2 端到端：文档导入→向量索引→LLM 规则提取→交叉验证→审核→发布→RulePack 加载。 |
| `tests/test_knowledge_integration.py::TestPhase3EndToEnd` | `knowledge_bridge` → `engine` → `nutrition` → `matcher` | Phase 3 端到端：在线引擎 + KnowledgePort + 缺口补尝 + 食材多样性 + 知识片段验证。 |

后续接入外部系统时建议新增：

| 集成对象 | 建议测试 |
| --- | --- |
| 图片识别服务 | 图片 URI 到 `IntakeRecord` 的转换、低置信度转人工、人工修正后不再触发低置信度。 |
| 外卖/食堂 API | 商品字段缺失、营养值异常、不可用商品、过敏原字段、分页和超时。 |
| HIS/EMR | 患者疾病编码映射、过敏映射、授权失败、病历字段缺失。 |
| 事件系统 | `DomainEvent` 序列化、幂等、失败重试、人工审核队列。 |
| 服务入口 | 鉴权、请求 id、payload 校验、错误响应、trace 持久化；当前已覆盖本地 HTTP payload 校验和统一错误响应。 |

Phase 3 端到端测试详见 `docs/phase-3-knowledge-engine-e2e-testing.md`。

## 10. 回归测试建议

每次修改推荐逻辑前后至少运行：

```bash
PYTHONPATH=src:knowledge/src pytest tests/ knowledge/tests/ --rootdir=. -q
PYTHONPATH=src python -m medidiet.cli
git diff --check
```

若修改规则包、枚举、trace 或公共 API，还应重点运行：

```bash
PYTHONPATH=src:knowledge/src pytest tests/test_rules.py tests/test_engine.py tests/test_explainer_trace.py tests/test_public_api.py -v --rootdir=.
```

若修改知识库或桥接适配器，还应重点运行：

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/ tests/test_knowledge_bridge.py tests/test_knowledge_integration.py tests/test_ports.py -v --rootdir=.
```

## 11. 测试人员验收清单

测试人员评估当前版本时，可按以下清单验收：

- 能从全新工作区运行全量测试。
- CLI 能输出 trace JSON。
- 高血压 + 高钠菜单触发安全阻断或菜单排除。
- 过敏原命中时必须人工审核。
- 低置信度摄入或菜单必须人工审核。
- 糖尿病规则同时包含每日糖上限和滚动窗口糖上限。
- 推荐结果不依赖字符串疾病名或字符串用餐标签。
- trace 中 code 为整数。
- 日志中 safety event 为 warning，且包含 pid/tid/timestamp。
- 默认运行测试和 CLI 时不产生额外 warning 到 stderr。

## 12. LLM 测试策略

LLM 单元测试默认离线运行，使用 `MockLLMProvider` 覆盖解释增强、问答、fallback、安全输出校验和 provider 请求构造。

真实 DeepSeek/OpenAI-compatible smoke test 位于 `tests/test_llm_deepseek_smoke.py`，真实 HTTP 推荐 + LLM smoke test 位于 `tests/test_http_llm_smoke.py`。两者默认跳过，只有显式设置 `MEDIDIET_LLM_SMOKE_TEST=1` 和完整 LLM 环境变量时才运行。

`tests/test_http_llm_smoke.py` 验证完整 HTTP 推荐路径能通过真实 OpenAI-compatible LLM provider 返回增强解释。它默认跳过，只在 `MEDIDIET_LLM_SMOKE_TEST=1` 且 LLM 环境变量完整时运行。

测试人员评估 LLM 功能时应确认：

- 普通全量测试不会访问外网。
- smoke test 不发送 `patient_id`。
- LLM 失败时回退到确定性模板解释。
- LLM 输出不能改变推荐 outcome 或推荐菜单。
