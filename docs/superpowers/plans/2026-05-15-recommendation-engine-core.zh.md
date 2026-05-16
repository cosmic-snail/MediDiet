# 推荐引擎核心实现计划（中文审核版）

> **给 agentic workers：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项执行。步骤使用复选框（`- [ ]`）追踪。
>
> 说明：本文件是中文审核版，完整覆盖目标、架构、文件结构、任务拆分、每步动作和验证方式。为避免中英两套代码块漂移，具体代码块以英文执行版 [2026-05-15-recommendation-engine-core.md](/Users/simon/MediDiet/docs/superpowers/plans/2026-05-15-recommendation-engine-core.md) 为准。

**目标：** 构建一个可测试的 MediDiet 推荐引擎核心，能够对成人慢病餐食推荐做安全门禁，生成下一餐方案，匹配具体菜单项，解释推荐结果，并为后续小程序、拍照识别、外卖平台、HIS/EMR、LLM、规则包、审核台和审计集成暴露扩展契约。

**架构：** 在 `src/medidiet` 下实现一个规则优先的 Python 包。核心保持轻依赖、确定性和可审计：领域模型、规则包、安全门禁、营养状态计算器、餐食方案生成器、菜单匹配器、解释生成器、审计 trace、编排引擎和扩展接口分别放在独立文件中。外部系统通过 typed ports/adapters 接入，只能向引擎提供证据，不能绕过安全门禁。

**技术栈：** Python 3.11+ 标准库，`dataclasses`、`enum`、`typing.Protocol`、`unittest`、`json`，本地 CLI 使用 `python -m medidiet.cli`。

---

## 范围检查

本计划实现已批准设计中的 Phase 1：推荐引擎核心、规则基线、模拟摄入/菜单数据、过滤、评分、解释、审计 trace 和扩展接口契约。

本计划不实现：

- 小程序 UI。
- 真实拍照识别模型。
- 真实外卖下单或支付闭环。
- 真实 HIS/EMR 集成。
- 生产级临床营养阈值。

这些内容会在后续计划中作为外部接口消费者接入。

## 文件结构

- `pyproject.toml`：包元数据和 Python 版本。
- `src/medidiet/__init__.py`：公共包导出。
- `src/medidiet/domain.py`：引擎通用枚举和 dataclass。
- `src/medidiet/rules.py`：版本化规则基线和规则查询。
- `src/medidiet/safety.py`：适用人群、过敏、禁忌、数据置信度和硬规则检查。
- `src/medidiet/nutrition.py`：当日营养汇总和下一餐目标计算。
- `src/medidiet/planner.py`：先生成餐食方案，再匹配具体菜单。
- `src/medidiet/matcher.py`：菜单硬过滤和加权排序。
- `src/medidiet/explainer.py`：根据规则命中和评分生成患者/医生解释。
- `src/medidiet/trace.py`：推荐 trace 创建和 JSON 序列化。
- `src/medidiet/engine.py`：推荐编排和结果策略。
- `src/medidiet/ports.py`：扩展接口、适配器 DTO 和领域事件名。
- `src/medidiet/fixtures.py`：测试和 CLI 使用的确定性样例数据。
- `src/medidiet/cli.py`：本地 demo runner。
- `tests/test_domain.py`：领域模型测试。
- `tests/test_rules.py`：规则包和来源治理测试。
- `tests/test_safety.py`：安全门禁测试。
- `tests/test_nutrition.py`：当日摄入和下一餐目标测试。
- `tests/test_planner.py`：餐食方案生成测试。
- `tests/test_matcher.py`：硬排除和排序测试。
- `tests/test_explainer_trace.py`：解释和 trace 测试。
- `tests/test_engine.py`：端到端编排测试。
- `tests/test_ports.py`：扩展契约测试。

## 通用命令

- 运行全部测试：`PYTHONPATH=src python -m unittest discover -s tests -v`
- 运行单个测试模块：`PYTHONPATH=src python -m unittest tests.test_engine -v`
- 运行 demo CLI：`PYTHONPATH=src python -m medidiet.cli`

---

## Task 1：项目骨架和冒烟测试

**文件：**
- 创建：`pyproject.toml`
- 创建：`src/medidiet/__init__.py`
- 创建：`tests/test_domain.py`

- [ ] **Step 1：创建失败的冒烟测试**

动作：创建 `tests/test_domain.py`，验证 `import medidiet` 并断言 `medidiet.__version__ == "0.1.0"`。

代码：使用英文执行版 Task 1 Step 1 中的完整代码块。

- [ ] **Step 2：运行测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_domain -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet'`。

- [ ] **Step 3：添加包骨架**

动作：

- 创建 `pyproject.toml`。
- 创建 `src/medidiet/__init__.py`，设置 `__version__ = "0.1.0"`。

代码：使用英文执行版 Task 1 Step 3 中的完整代码块。

- [ ] **Step 4：重新运行冒烟测试，确认通过**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_domain -v
```

预期：通过，包含 `test_package_imports`。

- [ ] **Step 5：提交**

运行：

```bash
git add pyproject.toml src/medidiet/__init__.py tests/test_domain.py
git commit -m "feat: scaffold recommendation engine package"
```

---

## Task 2：领域模型

**文件：**
- 创建：`src/medidiet/domain.py`
- 修改：`tests/test_domain.py`

- [ ] **Step 1：用表驱动概念注册表扩展领域模型测试**

动作：替换 `tests/test_domain.py`，覆盖：

- `ConceptRegistry` 能返回已注册的医学概念 code。
- `ConceptRegistry` 拒绝未知、空值、带空格或大小写不规范的 code。
- `PatientProfile` 使用 `ConceptCode` 表达疾病、过敏、禁忌和口味偏好。
- `PatientProfile` 拒绝错误 kind 的 code，例如把 `allergen:peanut` 放进 `conditions`。
- `PatientProfile` 校验年龄、身高、体重的非法值和边界值。
- `Nutrients` 支持浮点值和累加。
- `Nutrients` 拒绝负数、非有限值和明显荒谬的大值。
- `MenuItem` 使用 code 集合做过敏判断，不依赖字符串大小写匹配。
- `Outcome.RECOMMENDED.value == "recommended"`。

代码：使用英文执行版 Task 2 Step 1 中的完整代码块。

- [ ] **Step 2：运行领域模型测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_domain -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet.domain'`。

- [ ] **Step 3：实现领域模型**

动作：创建 `src/medidiet/domain.py`，定义：

- `CodeKind`
- `ConceptCode`
- `ConceptDefinition`
- `ConceptRegistry`
- `DataSource`
- `RiskLevel`
- `Outcome`
- `Confidence`
- `Nutrients`
- `Preference`
- `PatientProfile`
- `IntakeRecord`
- `MenuItem`

设计约束：

- 医学概念、过敏原、禁忌、营养标签、口味标签和食材标签都使用表驱动 `ConceptCode`。
- `Outcome`、`RiskLevel`、`DataSource` 这类系统状态仍使用 enum。
- 外部字符串只能在边界输入和注册表定义中出现，进入领域模型后必须变成已校验 code。

代码：使用英文执行版 Task 2 Step 3 中的完整代码块。

- [ ] **Step 4：运行领域模型测试，确认通过**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_domain -v
```

预期：8 个测试通过。

- [ ] **Step 5：提交**

运行：

```bash
git add src/medidiet/domain.py tests/test_domain.py
git commit -m "feat: add recommendation domain models"
```

---

## Task 3：版本化规则基线

**文件：**
- 创建：`src/medidiet/rules.py`
- 创建：`tests/test_rules.py`

- [ ] **Step 1：编写失败的规则测试**

动作：创建 `tests/test_rules.py`，覆盖：

- 规则包版本为 `baseline-2026-05-15`。
- 规则包包含多个来源和内置 `ConceptRegistry`。
- 规则查询使用 `ConceptCode`，不接收裸字符串。
- 高血压规则包含 `high_sodium` 硬禁忌、`low_sodium` 偏好标签和单餐钠上限。
- 糖尿病规则包含每日糖上限、滚动时间窗糖上限、`controlled_carbs` 偏好标签和 `sugary_drink` 硬禁忌。
- `ROLLING_WINDOW` 必须有正整数 `window_hours`，`DAILY` / `PER_MEAL` 不允许带 `window_hours`。
- 规则中的条件、禁忌、标签必须使用正确 kind 的 `ConceptCode`。

代码：使用英文执行版 Task 3 Step 1 中的代码块，并以当前 `tests/test_rules.py` 为准。

- [ ] **Step 2：运行规则测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_rules -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet.rules'`。

- [ ] **Step 3：实现规则包**

动作：创建 `src/medidiet/rules.py`，定义：

- `RuleSource`
- `NutrientMetric`
- `LimitScope`
- `NutrientLimit`
- `ConditionRule`
- `RulePack`
- `load_baseline_rule_pack()`

规则覆盖：

- 高血压。
- 糖尿病。
- 高血脂。
- 控重。

规则包使用表驱动结构：`RulePack.concepts` 保存概念注册表，`rules_by_condition` 以 `ConceptCode(CONDITION, ...)` 为 key，`ConditionRule.nutrition_limits` 保存不同 scope 的营养上限。当前阈值为 baseline/demo thresholds，后续需要医生/营养师审核。

代码：使用英文执行版 Task 3 Step 3 中的代码块，并以当前 `src/medidiet/rules.py` 为准。

- [ ] **Step 4：运行规则测试和全量测试**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_rules -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

预期：全部通过。

- [ ] **Step 5：提交**

运行：

```bash
git add src/medidiet/rules.py tests/test_rules.py
git commit -m "feat: add versioned baseline rule pack"
```

---

## Task 4：安全门禁

**文件：**
- 创建：`src/medidiet/safety.py`
- 创建：`tests/test_safety.py`

- [ ] **Step 1：编写失败的安全测试**

动作：创建 `tests/test_safety.py`，覆盖：

- 返回安全事件使用 `SafetyCode(IntEnum)` 整数枚举，不返回裸字符串或浮点 code。
- 过敏命中是硬拦截，并写入 `WARNING` 日志。
- 患者关键资料未确认时需要人工审核，并写入 `WARNING` 日志。
- 低置信度摄入记录需要人工审核，并写入 `WARNING` 日志。
- 单餐营养上限超限是硬拦截，并写入 `WARNING` 日志。
- 安全候选循环不输出 `DEBUG` / `INFO` 等低等级逐条日志，避免海量日志。
- 安全日志包含时间戳、进程号、线程号、整数 code、code name、事件严重性和规则包版本。

代码：以当前 `tests/test_safety.py` 为准。

- [ ] **Step 2：运行安全测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_safety -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet.safety'`。

- [ ] **Step 3：实现安全门禁**

动作：创建 `src/medidiet/safety.py`，实现：

- `SafetyCode(IntEnum)`
- `SafetySeverity(IntEnum)`
- `SafetyEvent`
- `SafetyResult`
- `SafetyGate.evaluate(...)`
- 每个 hard block / uncertainty 的 `WARNING` 文件日志

检查内容：

- 成人范围。
- 关键风险字段确认状态。
- 摄入置信度。
- 菜单营养置信度。
- 过敏硬拦截。
- 慢病禁忌冲突。
- 单餐营养上限。

日志原则遵循 `docs/superpowers/specs/2026-05-15-safety-logging-principles.md`。

代码：以当前 `src/medidiet/safety.py` 为准。

- [ ] **Step 4：运行安全测试和全量测试**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_safety -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

预期：全部通过。

- [ ] **Step 5：提交**

运行：

```bash
git add src/medidiet/safety.py tests/test_safety.py
git commit -m "feat: add recommendation safety gate"
```

---

## Task 5：营养状态和下一餐目标

**文件：**
- 更新：`src/medidiet/domain.py`
- 创建：`src/medidiet/nutrition.py`
- 创建：`tests/test_nutrition.py`

- [ ] **Step 1：编写失败的营养测试**

动作：创建 `tests/test_nutrition.py`，覆盖：

- 按浮点数汇总当天摄入的能量、钠、糖、碳水等营养数据。
- 低置信度摄入记录进入 `low_confidence_labels`，但仍计入总量。
- 下一餐偏好标签使用 `ConceptCode(NUTRITION_TAG, ...)`，不使用字符串集合。
- `DAILY` 糖上限根据当天已摄入量计算剩余额度。
- `ROLLING_WINDOW` 糖上限只统计窗口内摄入。
- `PER_MEAL` 上限直接进入下一餐目标，不扣减当天摄入。
- `IntakeRecord` 使用 timezone-aware `occurred_at` 和 `meal_label`，不再用自由文本 `meal_time`。

代码：以当前 `tests/test_nutrition.py` 为准。

- [ ] **Step 2：运行营养测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_nutrition -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet.nutrition'`。

- [ ] **Step 3：实现营养计算**

动作：创建 `src/medidiet/nutrition.py`，实现：

- `NutritionReason(IntEnum)`
- `DailyNutritionState`
- `RemainingNutrientLimit`
- `NextMealTarget`
- `DailyNutritionCalculator.aggregate(...)`
- `DailyNutritionCalculator.next_meal_target(...)`

同时更新 `src/medidiet/domain.py` 中的 `IntakeRecord`，将 `meal_time` 升级为 `occurred_at` + `meal_label`，支持每日和滚动窗口计算。

营养计算器消费 `RulePack` 中表驱动的 `NutrientLimit`，返回结构化 `RemainingNutrientLimit`，不再返回分散的 `max_*` 字段。

代码：以当前 `src/medidiet/nutrition.py` 为准。

- [ ] **Step 4：运行营养测试和全量测试**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_nutrition -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

预期：全部通过。

- [ ] **Step 5：提交**

运行：

```bash
git add src/medidiet/nutrition.py tests/test_nutrition.py
git commit -m "feat: calculate daily nutrition targets"
```

---

## Task 6：餐食方案生成器

**文件：**
- 更新：`src/medidiet/domain.py`
- 创建：`src/medidiet/planner.py`
- 创建：`tests/test_planner.py`

- [ ] **Step 1：编写失败的方案生成测试**

动作：创建 `tests/test_planner.py`，验证：

- 根据结构化 `NextMealTarget` 生成 `MealPlan`。
- `MealPlan.meal_label` 使用 `MealLabel(IntEnum)`，不使用 `"dinner"` 这类自由文本。
- `required_tags` 和 `avoid_tags` 使用 `ConceptCode` 集合，不使用字符串集合。
- 单餐钠上限加入 `low_sodium`、避开 `high_sodium`，并加入 `MealInstruction.AVOID_EXTRA_SAUCE`。
- 每日或滚动窗口糖上限加入 `controlled_carbs`、避开 `sugary_drink`，并加入 `MealInstruction.CONTROL_ADDED_SUGAR`。
- `MealInstruction` 使用整数枚举。
- `MealPlan` 保留结构化营养上限，供后续菜单匹配器使用。

代码：以当前 `tests/test_planner.py` 为准。

- [ ] **Step 2：运行测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_planner -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet.planner'`。

- [ ] **Step 3：实现方案生成器**

动作：创建 `src/medidiet/planner.py`，实现：

- `MealInstruction(IntEnum)`
- `MealPlan`
- `MealPlanGenerator.generate(...)`

同时更新 `src/medidiet/domain.py`，新增 `MealLabel(IntEnum)`，并要求 `IntakeRecord.meal_label` 使用该枚举。

方案生成器根据 `RemainingNutrientLimit` 推导标签和指令，并通过 `RulePack.concepts` 获取全部 `ConceptCode`。

代码：以当前 `src/medidiet/planner.py` 为准。

- [ ] **Step 4：运行方案生成测试和全量测试**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_planner -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

预期：全部通过。

- [ ] **Step 5：提交**

运行：

```bash
git add src/medidiet/planner.py tests/test_planner.py
git commit -m "feat: generate nutrition meal plans"
```

---

## Task 7：菜单匹配器

**文件：**
- 更新：`src/medidiet/domain.py`
- 创建：`src/medidiet/matcher.py`
- 创建：`tests/test_matcher.py`

- [ ] **Step 1：编写失败的菜单匹配测试**

动作：创建 `tests/test_matcher.py`，覆盖：

- `MenuMatcher.match(...)` 返回结构化 accepted / excluded 结果。
- `avoid_tags` 命中的菜品用 `MatchRejectionCode.AVOID_TAG` 排除。
- 单餐营养上限超限用 `MatchRejectionCode.NUTRIENT_LIMIT_EXCEEDED` 排除。
- 不可售菜品用 `MatchRejectionCode.UNAVAILABLE` 排除。
- 拒绝码使用 `IntEnum` 整数值，不使用字符串或浮点数。
- 安全候选按分数降序返回。
- 评分考虑 required nutrition tags、患者口味偏好、价格、距离和商家可靠性。

代码：以当前 `tests/test_matcher.py` 为准。

- [ ] **Step 2：运行测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_matcher -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet.matcher'`。

- [ ] **Step 3：实现菜单匹配器**

动作：创建 `src/medidiet/matcher.py`，实现：

- `MatchRejectionCode(IntEnum)`
- `MatchRejection`
- `MenuItemScore`
- `MatchResult`
- `MenuMatcher.match(...)`

同时更新 `src/medidiet/domain.py`，让 `MenuItem` 支持：

- `nutrition_tags: set[ConceptCode]`
- `contraindication_tags: set[ConceptCode]`

菜单匹配器使用 `MenuItem.nutrition_tags` 做 required-tag 评分，用 `MenuItem.contraindication_tags` 做 avoid-tag 硬过滤，用 `MealPlan.limits` 做单餐营养数值过滤。

代码：以当前 `src/medidiet/matcher.py` 为准。

- [ ] **Step 4：运行菜单匹配测试和全量测试**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_matcher -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

预期：全部通过。

- [ ] **Step 5：提交**

运行：

```bash
git add src/medidiet/matcher.py tests/test_matcher.py
git commit -m "feat: match and rank safe menu items"
```

---

## Task 8：解释和审计 Trace

**文件：**
- 创建：`src/medidiet/explainer.py`
- 创建：`src/medidiet/trace.py`
- 创建：`tests/test_explainer_trace.py`

- [ ] **Step 1：编写失败的解释和 trace 测试**

动作：创建 `tests/test_explainer_trace.py`，覆盖：

- 患者解释由 `ConceptCode` 标签和 `MealInstruction` 确定性生成中文说明。
- 患者解释不包含药物调整、诊断结论或治疗建议。
- 医生/营养师解释返回结构化 dict，包含整数安全事件 code、排除 code、规则版本、评分和命中标签。
- 医生/营养师解释包含 `llmBoundary`，明确解释只能基于规则命中、营养事实和候选评分。
- `RecommendationTrace.to_json()` 可序列化稳定 camelCase 字段：`traceId`、`patientId`、`ruleVersion`、`outcome`、`riskLevel`、`createdAt`、`safetyEvents`、`exclusions`。
- trace 中安全事件和排除原因保存整数 code，不保存字符串原因。
- trace 不接受患者姓名、手机号、照片 URI 等敏感字段。

代码：以当前 `tests/test_explainer_trace.py` 为准。

- [ ] **Step 2：运行测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_explainer_trace -v
```

预期：失败，出现 `medidiet.explainer` 或 `medidiet.trace` 的 `ModuleNotFoundError`。

- [ ] **Step 3：实现解释构建器和 trace**

动作：

- 创建 `src/medidiet/explainer.py`。
- 创建 `src/medidiet/trace.py`。

实现：

- `ExplanationBuilder.patient_explanation(...)`
- `ExplanationBuilder.clinician_explanation(...)`
- `SafetyEvent`、`MatchRejection`、`ConceptCode` 的结构化转换 helper。
- `RecommendationTrace.to_dict()`
- `RecommendationTrace.to_json()`

患者侧解释保持确定性模板，不依赖 LLM；trace 序列化不包含敏感患者身份字段。

代码：以当前 `src/medidiet/explainer.py` 和 `src/medidiet/trace.py` 为准。

- [ ] **Step 4：运行解释/trace 测试和全量测试**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_explainer_trace -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

预期：全部通过。

- [ ] **Step 5：提交**

运行：

```bash
git add src/medidiet/explainer.py src/medidiet/trace.py tests/test_explainer_trace.py
git commit -m "feat: explain and trace recommendations"
```

---

## Task 9：推荐引擎编排

**文件：**
- 创建：`src/medidiet/engine.py`
- 创建：`tests/test_engine.py`

- [ ] **Step 1：编写失败的引擎测试**

动作：创建 `tests/test_engine.py`，覆盖：

- 成功推荐路径：串联安全门禁、营养目标、餐食方案、菜单匹配、解释和 trace。
- 返回 `Outcome.RECOMMENDED`，推荐排序最高的候选，并在 trace 中记录 scores。
- 拒绝路径：所有候选被 matcher 排除时返回 `Outcome.REFUSED`，无推荐项，并在 trace 中保存 `MatchRejectionCode` 整数 code。
- 人工审核路径：安全门禁产生事件时返回 `Outcome.HUMAN_REVIEW_REQUIRED`，无推荐项，并在 trace 中保存 `SafetyCode` 整数 code。
- `RecommendationEngine.recommend(...)` 要求 `MealLabel`，不接受自由文本用餐标签。
- 测试 fixture 使用 `ConceptCode` 疾病、过敏、营养标签、口味标签和结构化 `IntakeRecord.occurred_at`。

代码：以当前 `tests/test_engine.py` 为准。

- [ ] **Step 2：运行引擎测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_engine -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet.engine'`。

- [ ] **Step 3：实现引擎编排**

动作：创建 `src/medidiet/engine.py`，实现：

- `RecommendationResult`
- `RecommendationEngine.__init__(...)`
- `RecommendationEngine.recommend(...)`
- `RecommendationEngine._finalize(...)`

逻辑：

- 先跑安全门禁。
- hard block 或 uncertainty 直接转人工。
- 计算下一餐目标。
- 生成餐食方案。
- 匹配菜单。
- 无候选时拒绝。
- 有候选时推荐排序最高项。
- 生成解释和 trace。

trace 和医生解释保留整数安全事件 code / 排除 code，不使用字符串原因；默认 safety logger 不污染 stderr，只有显式配置文件路径时写入文件。

代码：以当前 `src/medidiet/engine.py` 为准。

- [ ] **Step 4：运行引擎测试和全量测试**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_engine -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

预期：全部通过。

- [ ] **Step 5：提交**

运行：

```bash
git add src/medidiet/engine.py tests/test_engine.py
git commit -m "feat: orchestrate recommendation engine"
```

---

## Task 10：扩展接口和领域事件

**文件：**
- 创建：`src/medidiet/ports.py`
- 创建：`tests/test_ports.py`

- [ ] **Step 1：编写失败的扩展接口测试**

动作：创建 `tests/test_ports.py`，覆盖：

- 请求 envelope 携带 schema、来源系统、来源版本、请求 ID 和 timezone-aware `created_at`。
- envelope 序列化输出稳定 camelCase，包括 `createdAt`。
- envelope 拒绝字符串时间戳和 naive datetime。
- 摄入估算请求携带图片 URI 和 `MealLabel`，不携带模型原始输出，也不使用自由文本用餐标签。
- 领域事件名保持稳定字符串枚举，例如 `HumanReviewRequired`。
- 领域事件 payload 可以携带整数安全/业务 code。
- 领域事件拒绝裸字符串 name 和 naive datetime。

代码：以当前 `tests/test_ports.py` 为准。

- [ ] **Step 2：运行测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_ports -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet.ports'`。

- [ ] **Step 3：实现扩展接口和事件**

动作：创建 `src/medidiet/ports.py`，实现：

- `RecommendationRequestEnvelope`
- `IntakeEstimationRequest`
- `EventName`
- `DomainEvent`
- `IntakeEstimatorPort`
- `MenuProviderPort`
- `PatientContextPort`
- `EventPublisherPort`

其中 `RecommendationRequestEnvelope` 和 `DomainEvent` 使用 timezone-aware `created_at` 并提供 `to_dict()`；`IntakeEstimationRequest` 使用 `MealLabel` 并提供 `to_dict()`。

代码：以当前 `src/medidiet/ports.py` 为准。

- [ ] **Step 4：运行接口测试和全量测试**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_ports -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

预期：全部通过。

- [ ] **Step 5：提交**

运行：

```bash
git add src/medidiet/ports.py tests/test_ports.py
git commit -m "feat: add extension ports and events"
```

---

## Task 11：样例数据和 CLI Demo

**文件：**
- 创建：`src/medidiet/fixtures.py`
- 创建：`src/medidiet/cli.py`
- 修改：`tests/test_engine.py`

- [ ] **Step 1：添加失败的 fixture 驱动测试**

动作：在 `tests/test_engine.py` 的 `RecommendationEngineTest` 中追加测试，验证：

- `demo_request()` 返回 `PatientProfile`、`list[IntakeRecord]`、`list[MenuItem]` 和 `MealLabel`。
- 引擎直接使用返回的 `MealLabel`，不使用自由文本用餐标签。
- trace JSON 以 `{` 开头，并包含 `"traceId"`、`"outcome"` 和实际 outcome 值。
- 测试导入 `medidiet.fixtures`，因此在 fixture 模块创建前会失败。

代码：以当前 `tests/test_engine.py` 为准。

- [ ] **Step 2：运行更新后的引擎测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_engine.RecommendationEngineTest.test_fixture_demo_returns_trace_json -v
```

预期：失败，出现 `ModuleNotFoundError: No module named 'medidiet.fixtures'`。

- [ ] **Step 3：实现确定性 fixtures 和 CLI**

动作：

- 创建 `src/medidiet/fixtures.py`，提供确定性的 `DEMO_NOW` 和 `demo_request()`。
- `demo_request() -> tuple[PatientProfile, list[IntakeRecord], list[MenuItem], MealLabel]`。
- 患者疾病、过敏、口味偏好、菜单食材、营养标签、禁忌标签都使用 `ConceptCode`。
- `IntakeRecord` 使用 timezone-aware `occurred_at` 和 `MealLabel`，不使用字符串 `meal_time`。
- 样例菜单包含一个安全可推荐项，以及一个通过 `available=False` 被过滤的菜单项。
- 创建 `src/medidiet/cli.py`，加载 baseline rule pack，使用 `DEMO_NOW` 和 fixture 返回的 `MealLabel` 运行引擎，并且只打印 trace JSON。

代码：以当前 `src/medidiet/fixtures.py` 和 `src/medidiet/cli.py` 为准。

- [ ] **Step 4：运行 fixture 测试、全量测试和 CLI**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_engine.RecommendationEngineTest.test_fixture_demo_returns_trace_json -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m medidiet.cli
```

预期：

- 测试通过。
- CLI 输出包含 `"traceId"` 和 `"outcome"` 的 JSON。

- [ ] **Step 5：提交**

运行：

```bash
git add docs/superpowers/plans/2026-05-15-recommendation-engine-core.md docs/superpowers/plans/2026-05-15-recommendation-engine-core.zh.md src/medidiet/fixtures.py src/medidiet/cli.py tests/test_engine.py
git commit -m "feat: add demo fixtures and CLI"
```

---

## Task 12：公共导出和最终验证

**文件：**
- 修改：`src/medidiet/__init__.py`
- 创建：`tests/test_public_api.py`
- 如需要实施说明，修改：`docs/superpowers/specs/2026-05-15-hospital-diet-agent-recommendation-engine-design.md`

- [ ] **Step 1：编写失败的公共 API 测试**

动作：创建 `tests/test_public_api.py`，验证可以从 `medidiet` 导入：

- `RecommendationEngine`
- `RecommendationResult`
- `RulePack`
- `load_baseline_rule_pack`
- `medidiet.__all__` 精确列出这四个公共名称。
- `load_baseline_rule_pack()` 返回 `RulePack`。
- 可以用公共 API 返回的 rule pack 构造 `RecommendationEngine`。

代码：以当前 `tests/test_public_api.py` 为准。

- [ ] **Step 2：运行公共 API 测试，确认失败**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_public_api -v
```

预期：失败，出现公共 API 导出缺失导致的 `ImportError`。

- [ ] **Step 3：导出稳定公共 API**

动作：替换 `src/medidiet/__init__.py`，导出：

- `RecommendationEngine`
- `RecommendationResult`
- `RulePack`
- `load_baseline_rule_pack`

代码：使用英文执行版 Task 12 Step 3 中的完整代码块。

- [ ] **Step 4：运行公共 API 和完整验证**

运行：

```bash
PYTHONPATH=src python -m unittest tests.test_public_api -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m medidiet.cli
git status --short
```

预期：

- 公共 API 测试通过。
- 全量测试通过。
- CLI 输出包含 `"traceId"` 和 `"outcome"` 的 JSON。
- 提交前 `git status --short` 只显示本任务预期修改。

- [ ] **Step 5：提交**

运行：

```bash
git add docs/superpowers/plans/2026-05-15-recommendation-engine-core.md docs/superpowers/plans/2026-05-15-recommendation-engine-core.zh.md src/medidiet/__init__.py tests/test_public_api.py
git commit -m "feat: expose recommendation engine public API"
```

- [ ] **Step 6：最终实现验证**

运行：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m medidiet.cli
git log --oneline -5
```

预期：

- 全部测试通过。
- CLI 输出推荐 trace JSON。
- 最近提交包含本计划中的任务提交。

---

## 自检

### 设计覆盖

- 成人慢病和过敏范围：Task 2、Task 3、Task 4、Task 9。
- 安全边界和高风险升级：Task 4、Task 9。
- 临床参考治理和版本化规则包：Task 3。
- 规则优先架构和 LLM 解释边界：Task 8、Task 9。
- 数据模型：Task 2。
- 推荐流程：Task 4 到 Task 9。
- 排序策略：Task 7。
- 人工审核：Task 4、Task 8、Task 9、Task 10。
- 错误处理和安全降级：Task 4、Task 7、Task 9。
- API 和扩展边界：Task 10。
- 测试策略：每个任务都包含失败测试和验证命令。
- Roadmap Phase 1：Task 1 到 Task 12。

### 有意后置的内容

- 真实临床营养阈值需要在核心完成后由医生/营养师审核规则包。
- 小程序 UI、生产 API 服务、真实拍照识别、真实外卖连接器、HIS/EMR、LLM provider 和审核台 UI 需要单独计划。

### 占位符扫描

本计划没有未解决的占位标记，也没有模糊的延后实现步骤。每个任务都包含明确文件路径、动作、验证命令和预期结果。

### 类型一致性

英文执行版和中文审核版都使用同一组类型和函数名：

- `PatientProfile`、`IntakeRecord`、`MenuItem`、`Nutrients`、`Confidence`、`Preference`。
- `RulePack`、`ConditionRule`、`load_baseline_rule_pack`。
- `SafetyGate.evaluate`。
- `DailyNutritionCalculator.next_meal_target`。
- `MealPlanGenerator.generate`。
- `MenuMatcher.match`。
- `ExplanationBuilder`。
- `RecommendationTrace`。
- `RecommendationEngine.recommend`。
- `RecommendationRequestEnvelope`、`DomainEvent`、`EventName`。
