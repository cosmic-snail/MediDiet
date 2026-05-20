# Phase 3 端到端测试文档：在线知识增强 + 缺口补尝 + 食材多样性

版本：0.1.0
目标读者：QA、测试人员、代码 reviewer。
关联实现：PR #3 (`feature/nutrition-knowledge-base-phase-2`)

## 1. 测试范围

Phase 3 为推荐引擎新增三项能力，本文档描述端到端验证场景：

- **在线知识检索增强**：引擎注入 `KnowledgePort` 后，推荐结果携带知识来源片段。
- **营养素缺口补尝**：上一餐蛋白质/纤维不足 → 下一餐自动注入偏好标签。
- **食材多样性评分**：近期已摄入食材 → 候选菜单扣分，促进多样化。
- **LLM fallback 知识保留**：LLM 增强失败时，确定性解释中的 `knowledgeSnippets` 不丢失。

## 2. 测试环境

```bash
# 依赖
pip install chromadb sentence-transformers

# 运行所有 Phase 3 相关测试
PYTHONPATH=src:knowledge/src pytest tests/test_knowledge_integration.py tests/test_engine.py tests/test_nutrition.py tests/test_matcher.py tests/test_llm.py -v --rootdir=.
```

## 3. E2E 场景

### 3.1 在线知识检索增强

**场景**：患者有 CKD 疾病，引擎注入 `KnowledgePort`（ChromaDB + 知识库文档），推荐后 `clinician_explanation` 包含知识来源片段。

**前置条件**：
- 知识库已导入 CKD 指南文档并向量索引
- 规则已从文档提取/发布
- `KnowledgeRetriever` 以 `KnowledgePort` 注入引擎

**测试步骤**：
1. 导入 CKD 指南文档到 ChromaDB
2. 提取规则、审核、发布版本
3. `KnowledgeRuleProvider` 加载 RulePack
4. `KnowledgeRetriever` 作为 `KnowledgePort` 注入 `RecommendationEngine`
5. 创建 CKD 患者，调用 `recommend()`
6. 验证 `result.clinician_explanation["knowledgeSnippets"]` 存在且非空
7. 验证片段包含 `sourceTitle`, `sourceUrl`, `relevanceScore` 等字段

**关键测试**：
- `test_engine_with_knowledge_includes_snippets`
- `test_online_engine_with_gap_compensation`（含 snippets 验证）

### 3.2 知识检索失败静默降级

**场景**：`KnowledgePort.retrieve_context()` 抛出异常时，推荐正常完成，只是 `knowledgeSnippets` 字段缺失。

**测试步骤**：
1. 构造 `KnowledgePort` 实现，`retrieve_context()` 总是抛异常
2. 注入引擎，调用 `recommend()`
3. 验证返回 `Outcome.RECOMMENDED`
4. 验证 `knowledgeSnippets` 不在 `clinician_explanation` 中
5. 验证 trace 正常生成

**关键测试**：`test_engine_with_failing_knowledge_degrades_gracefully`

### 3.3 营养缺口补尝 — 低蛋白午餐 → 晚餐补 lean_protein

**场景**：患者午餐蛋白质仅 8g（<15g 阈值），推荐晚餐时引擎自动注入 `lean_protein` 标签。

**前置条件**：
- 午餐摄入记录：蛋白质 8g
- 候选菜单中包含带 `lean_protein` 标签的项

**测试步骤**：
1. 创建患者，添加午餐记录（蛋白质 8g）
2. 构建菜单（含 `lean_protein` 标签项）
3. 调用 `recommend()` for `MealLabel.DINNER`
4. 验证 `matchedTags` 包含 `lean_protein`
5. 验证 `Outcome.RECOMMENDED`

**关键测试**：
- `test_compensation_tags_low_protein_adds_lean_protein`
- `test_online_engine_with_gap_compensation`（含 matchedTags 验证）

### 3.4 营养缺口补尝 — 同日过滤

**场景**：昨天的午餐蛋白质不足，不应影响今天的晚餐推荐。

**测试步骤**：
1. 创建昨天的午餐记录（蛋白质 8g）
2. 创建今天的午餐记录（蛋白质 30g，足够）
3. 调用 `recommend()` for `MealLabel.DINNER` with `now=` 今天
4. 验证 `matchedTags` 不包含 `lean_protein`（今天的午餐已足够）
5. 验证昨天的记录被同日过滤排除

**相关代码**：`engine.py:_PREVIOUS_MEAL` 同日过滤逻辑

### 3.5 食材多样性评分

**场景**：近期已摄入鱼（`fish`），候选菜单含鱼的项得分低于其他相同条件的项。

**测试步骤**：
1. 引擎注入 `recent_ingredients=frozenset({fish})`
2. 两个候选菜单项：一项含鱼，一项不含鱼
3. 调用 `recommend()`
4. 验证含鱼项得分 < 不含鱼项得分
5. 验证 trace.scores 反映差异

**关键测试**：
- `test_repeated_ingredient_penalty_reduces_score`
- `test_multiple_repeated_ingredients_accumulate_penalty`

### 3.6 LLM Fallback 保留知识片段

**场景**：LLM 解释增强失败回退时，确定性引擎生成的 `knowledgeSnippets` 被保留到 fallback 文本中。

**测试步骤**：
1. 构造一个 `RecommendationResult`，`clinician_explanation` 中包含 `knowledgeSnippets`
2. 使用 `MockLLMProvider(error=RuntimeError)` 触发 LLM fallback
3. 调用 `LLMExplanationEnhancer(MockLLMProvider(error=...)).enhance(context, result)`
4. 验证返回的 `clinician_explanation` 字符串包含 `knowledgeSnippets` JSON
5. 验证包含原文引用（如 "Limit sodium to 700mg/meal."）

**关键测试**：`test_fallback_preserves_knowledge_snippets_from_deterministic_clinician_payload`

### 3.7 完整管线：知识库 → 提取 → 发布 → 在线推荐 → 缺口补尝 → 多样性

**场景**：从源文档到最终推荐的完整链路，验证 Phase 1/2/3 所有环节串联。

**测试步骤**：
1. 导入 CKD 指南文档到 ChromaDB
2. LLM 提取规则 + 交叉验证
3. 审核规则 + 发布版本
4. `KnowledgeRuleProvider` 加载 RulePack
5. `KnowledgeRetriever` 注入引擎
6. 创建 CKD 患者 + 低蛋白午餐记录
7. 构建候选菜单（含 `low_sodium`、`lean_protein`、`high_fiber` 标签）
8. 注入 `recent_ingredients=frozenset({fish})`
9. 调用 `recommend()` for `MealLabel.DINNER`
10. 验证：
    - `Outcome.RECOMMENDED`
    - `knowledgeSnippets` 在 `clinician_explanation` 中且包含来源引用
    - `matchedTags` 包含 `lean_protein`（缺口补尝）
    - `trace.scores` 中得分 > 0 且反映了多样性扣分

**关键测试**：`test_online_engine_with_gap_compensation`

## 4. 测试数据

### CKD 指南片段（用于 E2E 测试）

```
# CKD Dietary Guidelines

## Sodium
Limit sodium to under 700mg per meal for CKD patients.

## Protein
Restrict protein to 0.6-0.8g/kg/day for CKD stages 3-5.
```

### 患者示例

```python
patient = PatientProfile(
    patient_id="pt-ckd-001",
    age=65,
    height_cm=170,
    weight_kg=75,
    conditions={ConceptCode(CodeKind.CONDITION, "ckd")},
    allergens=set(),
    contraindications=set(),
    preferences=Preference(),
    key_risk_fields_confirmed=True,
    source=DataSource.PATIENT_REPORTED,
)
```

### 低蛋白午餐摄入记录

```python
IntakeRecord(
    food_label="light congee",
    occurred_at=now,
    meal_label=MealLabel.LUNCH,
    portion="one bowl",
    nutrients=Nutrients(protein_g=8, fiber_g=1, sodium_mg=300),
    confidence=Confidence(0.9),
    source=DataSource.SYSTEM_ESTIMATED,
)
```

## 5. 回退与兼容性验证

| 场景 | 预期行为 |
| --- | --- |
| 引擎不传 `knowledge` | 行为与 Phase 2 完全一致 |
| 引擎不传 `recent_ingredients` | 多样性评分不影响，得分不变 |
| 引擎传 `knowledge=None` | 等同于不传，无 snippets |
| 上一餐无记录 | 不触发缺口补尝 |
| 早餐推荐 | 无上一餐，不触发缺口补尝 |
| `meal_label` 为 SNACK | 不在 `_PREVIOUS_MEAL` 中，不触发缺口补尝 |

## 6. 测试清单

- [ ] `test_engine_with_knowledge_includes_snippets` — 有 KnowledgePort 时有 snippets
- [ ] `test_engine_without_knowledge_has_no_snippets` — 无 KnowledgePort 时无 snippets
- [ ] `test_engine_with_failing_knowledge_degrades_gracefully` — KnowledgePort 失败时静默降级
- [ ] `test_compensation_tags_low_protein_adds_lean_protein` — 低蛋白缺口补尝
- [ ] `test_compensation_tags_low_fiber_adds_high_fiber` — 低纤维缺口补尝
- [ ] `test_compensation_tags_combines_across_records` — 跨记录合并
- [ ] `test_compensation_tags_empty_records_returns_empty` — 空记录无边角
- [ ] `test_compensation_tags_adequate_meal_returns_empty` — 足够时不补尝
- [ ] `test_repeated_ingredient_penalty_reduces_score` — 多样性扣分
- [ ] `test_multiple_repeated_ingredients_accumulate_penalty` — 多食材累加扣分
- [ ] `test_recent_ingredients_default_empty_has_no_effect` — 默认不影响
- [ ] `test_fallback_preserves_knowledge_snippets_from_deterministic_clinician_payload` — Fallback 保留片段
- [ ] `test_online_engine_with_gap_compensation` — 完整管线 E2E
