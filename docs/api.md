# MediDiet API 文档

版本：0.1.0
状态：核心推荐引擎 MVP，供后续小程序、服务端、图片识别、外卖/食堂接口扩展使用。

## 1. API 边界

当前仓库提供的是医院餐食推荐的 **Python 核心引擎**，不是完整 Web 服务。它负责：

- 校验患者、摄入记录、菜单候选项和规则包。
- 根据慢病、过敏、禁忌、偏好和今日摄入生成下一餐推荐。
- 输出推荐结果、患者解释、医生/营养师解释和可审计 trace。
- 提供外部系统扩展端口的数据结构和 `Protocol`。

当前仓库不直接提供：

- HTTP API server。
- 小程序前端。
- 真实外卖平台连接器。
- 真实图片识别模型。
- HIS/EMR 生产集成。

这些能力应通过 `src/medidiet/ports.py` 中的端口和领域事件接入。

## 2. 顶层公共 API

从 `medidiet` 包顶层导出的稳定 API：

```python
from medidiet import (
    LLMAnswer,
    LLMConfig,
    LLMContextSanitizer,
    LLMEnhancedExplanation,
    LLMExplanationEnhancer,
    LLMFallbackReason,
    LLMQuestionAnswerer,
    MockLLMProvider,
    OpenAICompatibleLLMProvider,
    RecommendationEngine,
    RecommendationResult,
    RulePack,
    load_baseline_rule_pack,
)
```

对应文件：

- `src/medidiet/__init__.py`
- `src/medidiet/engine.py`
- `src/medidiet/llm.py`
- `src/medidiet/rules.py`

### 2.1 推荐引擎入口

```python
RecommendationEngine(rule_pack: RulePack, now: datetime | None = None)
```

参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `rule_pack` | `RulePack` | 已加载的规则包。MVP 使用 `load_baseline_rule_pack()`。 |
| `now` | `datetime | None` | 可选的当前时间。测试或 demo 可传固定时区时间；生产默认使用当前 UTC 时间。 |

### 2.2 推荐调用

```python
result = engine.recommend(
    patient: PatientProfile,
    intake_records: list[IntakeRecord],
    candidate_menu_items: list[MenuItem],
    meal_label: MealLabel,
)
```

参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `patient` | `PatientProfile` | 患者基本信息、疾病、过敏、禁忌、偏好和确认状态。 |
| `intake_records` | `list[IntakeRecord]` | 今天已摄入记录，通常来自图片识别、人工修正或系统估算。 |
| `candidate_menu_items` | `list[MenuItem]` | 外卖、食堂或人工维护菜单候选项。 |
| `meal_label` | `MealLabel` | 下一餐标签，必须是枚举，不接受字符串。 |

返回：

```python
@dataclass(frozen=True)
class RecommendationResult:
    outcome: Outcome
    recommended_items: tuple[MenuItem, ...]
    patient_explanation: str
    clinician_explanation: dict[str, object]
    trace: RecommendationTrace
```

### 2.3 最小调用示例

```python
from medidiet import RecommendationEngine, load_baseline_rule_pack
from medidiet.fixtures import DEMO_NOW, demo_request

rule_pack = load_baseline_rule_pack()
patient, intake_records, menu_items, meal_label = demo_request()

result = RecommendationEngine(rule_pack, now=DEMO_NOW).recommend(
    patient=patient,
    intake_records=intake_records,
    candidate_menu_items=menu_items,
    meal_label=meal_label,
)

print(result.outcome)
print(result.patient_explanation)
print(result.trace.to_json())
```

## 3. 核心枚举

### 3.1 `CodeKind`

文件：`src/medidiet/domain.py`

| 枚举 | 值 | 用途 |
| --- | --- | --- |
| `CONDITION` | `condition` | 疾病或健康目标，如高血压、糖尿病。 |
| `ALLERGEN` | `allergen` | 过敏原，如花生、虾。 |
| `CONTRAINDICATION` | `contraindication` | 禁忌标签，如高钠、油炸。 |
| `NUTRITION_TAG` | `nutrition_tag` | 营养标签，如低钠、控主食。 |
| `TASTE_TAG` | `taste_tag` | 口味偏好，如清淡。 |
| `INGREDIENT` | `ingredient` | 食材，如鱼、糙米。 |

`ConceptCode` 由 `CodeKind` 和规范化 `value` 组成，`value` 必须是小写 snake_case，可带一个命名空间冒号。

### 3.2 `MealLabel`

`MealLabel` 是 `IntEnum`，用于避免自由文本匹配。

| 枚举 | 整数值 | 说明 |
| --- | ---: | --- |
| `BREAKFAST` | 1 | 早餐 |
| `LUNCH` | 2 | 午餐 |
| `DINNER` | 3 | 晚餐 |
| `SNACK` | 4 | 加餐 |

### 3.3 `Outcome`

| 枚举 | 值 | 说明 |
| --- | --- | --- |
| `RECOMMENDED` | `recommended` | 推荐成功。 |
| `DOWNGRADED` | `downgraded` | 预留，低风险降级推荐。当前引擎未主动返回。 |
| `REFUSED` | `refused` | 所有候选不满足要求，拒绝自动推荐。 |
| `HUMAN_REVIEW_REQUIRED` | `human_review_required` | 安全或数据质量触发人工审核。 |

### 3.4 整数 code 约定

| 类型 | 文件 | 范围 | 说明 |
| --- | --- | ---: | --- |
| `SafetyCode` | `safety.py` | 1001-2003 | 安全阻断和不确定性。 |
| `NutritionReason` | `nutrition.py` | 3001-3003 | 营养限额来源。 |
| `MealInstruction` | `planner.py` | 4001-4004 | 给患者的餐食行为建议。 |
| `MatchRejectionCode` | `matcher.py` | 5001-5003 | 菜单候选项排除原因。 |

业务逻辑应使用枚举和整数 code，不应解析日志字符串或自然语言解释。

## 4. 核心数据模型

### 4.1 `PatientProfile`

```python
PatientProfile(
    patient_id: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    conditions: set[ConceptCode],
    allergens: set[ConceptCode],
    contraindications: set[ConceptCode],
    preferences: Preference,
    key_risk_fields_confirmed: bool,
    source: DataSource,
)
```

校验规则：

- `age` 必须为 `0..130` 的整数。
- `height_cm` 必须大于 0 且不超过 260。
- `weight_kg` 必须大于 0 且不超过 600。
- `conditions` 只能包含 `CodeKind.CONDITION`。
- `allergens` 只能包含 `CodeKind.ALLERGEN`。
- `contraindications` 只能包含 `CodeKind.CONTRAINDICATION`。
- `source` 必须是 `DataSource`。

### 4.2 `Preference`

```python
Preference(
    disliked_ingredients: set[ConceptCode] = set(),
    taste_tags: set[ConceptCode] = set(),
    max_price_cents: int | None = None,
    max_distance_meters: int | None = None,
)
```

说明：

- `taste_tags` 用于排序加分。
- `max_price_cents` 和 `max_distance_meters` 必须为非负整数。
- 当前 matcher 尚未硬排除 `disliked_ingredients`，该字段为后续扩展保留。

### 4.3 `IntakeRecord`

```python
IntakeRecord(
    food_label: str,
    occurred_at: datetime,
    meal_label: MealLabel,
    portion: str,
    nutrients: Nutrients,
    confidence: Confidence,
    source: DataSource,
    manually_corrected: bool = False,
)
```

校验规则：

- `occurred_at` 必须是 timezone-aware `datetime`。
- `meal_label` 必须是 `MealLabel`，不接受字符串。
- `confidence < 0.7` 且未人工修正时，会在安全门禁中触发人工审核不确定性。

### 4.4 `MenuItem`

```python
MenuItem(
    item_id: str,
    merchant_id: str,
    name: str,
    ingredients: set[ConceptCode],
    allergens: set[ConceptCode],
    taste_tags: set[ConceptCode],
    nutrients: Nutrients,
    nutrition_confidence: Confidence,
    source: DataSource,
    price_cents: int,
    distance_meters: int,
    merchant_reliability: float,
    nutrition_tags: set[ConceptCode] = set(),
    contraindication_tags: set[ConceptCode] = set(),
    available: bool = True,
)
```

校验规则：

- `ingredients` 只能包含 `CodeKind.INGREDIENT`。
- `allergens` 只能包含 `CodeKind.ALLERGEN`。
- `taste_tags` 只能包含 `CodeKind.TASTE_TAG`。
- `nutrition_tags` 只能包含 `CodeKind.NUTRITION_TAG`。
- `contraindication_tags` 只能包含 `CodeKind.CONTRAINDICATION`。
- `price_cents` 和 `distance_meters` 必须是非负整数。
- `merchant_reliability` 必须在 `0..1`。

### 4.5 `Nutrients` 与 `Confidence`

`Nutrients` 支持浮点数，用于兼容图片识别、营养估算和外部标签数据。

字段：

- `energy_kcal`
- `carbs_g`
- `protein_g`
- `fat_g`
- `sodium_mg`
- `sugar_g`
- `fiber_g`

每个营养值必须是有限非负数，且不超过 `1_000_000`。
`Confidence.value` 必须在 `0..1`。

## 5. 规则包 API

文件：`src/medidiet/rules.py`

### 5.1 加载规则包

```python
from medidiet import load_baseline_rule_pack

rule_pack = load_baseline_rule_pack()
```

当前 baseline 覆盖：

- `hypertension`
- `diabetes`
- `hyperlipidemia`
- `weight_control`

规则包版本：

```python
rule_pack.version == "baseline-2026-05-15"
```

### 5.2 `RulePack`

```python
RulePack(
    version: str,
    sources: tuple[RuleSource, ...],
    concepts: ConceptRegistry,
    rules_by_condition: dict[ConceptCode, ConditionRule],
)
```

主要方法：

```python
rule = rule_pack.for_condition(condition_code)
```

如果 `condition_code` 不是 `CodeKind.CONDITION` 或未注册规则，会抛出异常。

### 5.3 `ConditionRule`

```python
ConditionRule(
    condition: ConceptCode,
    hard_exclusions: set[ConceptCode],
    preferred_tags: set[ConceptCode],
    nutrition_limits: set[NutrientLimit],
)
```

说明：

- `hard_exclusions` 是疾病相关禁忌标签。
- `preferred_tags` 会进入下一餐目标和菜单排序。
- `nutrition_limits` 支持每餐、每日和滚动时间窗口上限。

### 5.4 `NutrientLimit`

```python
NutrientLimit(
    metric: NutrientMetric,
    scope: LimitScope,
    max_value: float,
    window_hours: int | None = None,
)
```

`LimitScope`：

| 枚举 | 值 | 说明 |
| --- | --- | --- |
| `PER_MEAL` | `per_meal` | 单餐上限。 |
| `DAILY` | `daily` | 当日上限。 |
| `ROLLING_WINDOW` | `rolling_window` | 滚动窗口上限，如 4 小时糖摄入上限。 |

约束：

- `max_value` 必须为有限正数。
- `ROLLING_WINDOW` 必须设置正整数 `window_hours`。
- 非滚动窗口不允许设置 `window_hours`。

## 6. 推荐结果与 Trace

`RecommendationTrace` 位于 `src/medidiet/trace.py`。

```python
trace_json = result.trace.to_json()
trace_dict = result.trace.to_dict()
```

输出字段为 camelCase：

| 字段 | 说明 |
| --- | --- |
| `traceId` | 本次推荐 trace id。 |
| `patientId` | 患者内部 id。 |
| `ruleVersion` | 规则包版本。 |
| `outcome` | 推荐结果。 |
| `riskLevel` | 风险等级。 |
| `createdAt` | ISO 8601 时间。 |
| `safetyEvents` | 安全事件列表，使用整数 code。 |
| `exclusions` | 被排除菜单项及整数排除 code。 |
| `scores` | 被接受菜单项分数。 |
| `patientExplanation` | 患者可读解释。 |
| `clinicianExplanation` | 医生/营养师可读结构化解释。 |

隐私边界：

- trace 当前包含 `patient_id`，不包含姓名、手机号、身份证、原始病历文本、原始图片或地址。
- 后续生产化需要在服务层增加患者 id 哈希化、访问控制和留存策略。

## 7. 扩展端口 API

文件：`src/medidiet/ports.py`

### 7.1 请求信封

```python
RecommendationRequestEnvelope(
    schema_version: str,
    source_system: str,
    source_version: str,
    request_id: str,
    created_at: datetime,
)
```

`created_at` 必须是 timezone-aware `datetime`。

序列化：

```python
envelope.to_dict()
```

输出：

```json
{
  "schemaVersion": "1.0",
  "sourceSystem": "mini_program",
  "sourceVersion": "0.1.0",
  "requestId": "req-001",
  "createdAt": "2026-05-16T12:00:00+08:00"
}
```

### 7.2 图片摄入估算请求

```python
IntakeEstimationRequest(
    envelope: RecommendationRequestEnvelope,
    image_uri: str,
    meal_label: MealLabel,
)
```

说明：

- `image_uri` 可以是对象存储 URI、内部文件引用或后续图片服务 id。
- `meal_label` 必须是 `MealLabel`。
- 该请求不保存模型原始输出，生产中应在图片识别服务自身处理模型审计。

### 7.3 领域事件

```python
DomainEvent(
    name: EventName,
    trace_id: str,
    payload: dict[str, object],
    created_at: datetime,
)
```

事件名：

| 枚举 | 值 |
| --- | --- |
| `RECOMMENDATION_REQUESTED` | `RecommendationRequested` |
| `RECOMMENDATION_COMPLETED` | `RecommendationCompleted` |
| `HUMAN_REVIEW_REQUIRED` | `HumanReviewRequired` |
| `HUMAN_REVIEW_COMPLETED` | `HumanReviewCompleted` |
| `PATIENT_PREFERENCE_UPDATED` | `PatientPreferenceUpdated` |
| `INTAKE_RECORD_CORRECTED` | `IntakeRecordCorrected` |
| `MENU_NUTRITION_ANNOTATED` | `MenuNutritionAnnotated` |
| `RULE_PACK_PUBLISHED` | `RulePackPublished` |
| `RULE_PACK_ROLLED_BACK` | `RulePackRolledBack` |

`payload` 可以携带 `SafetyCode.value`、`MatchRejectionCode.value` 等整数 code。

### 7.4 端口 Protocol

```python
class IntakeEstimatorPort(Protocol):
    def estimate(self, request: IntakeEstimationRequest) -> list[IntakeRecord]:
        ...

class MenuProviderPort(Protocol):
    def candidate_items(
        self,
        envelope: RecommendationRequestEnvelope,
        patient: PatientProfile,
    ) -> list[MenuItem]:
        ...

class PatientContextPort(Protocol):
    def load_patient(
        self,
        envelope: RecommendationRequestEnvelope,
        patient_id: str,
    ) -> PatientProfile:
        ...

class EventPublisherPort(Protocol):
    def publish(self, event: DomainEvent) -> None:
        ...
```

后续接入建议：

- 图片识别服务实现 `IntakeEstimatorPort`。
- 外卖/食堂菜单适配器实现 `MenuProviderPort`。
- HIS/EMR 或小程序患者档案服务实现 `PatientContextPort`。
- 消息队列、审计系统或日志平台实现 `EventPublisherPort`。

## 8. 安全日志 API

`SafetyGate` 可选写入 warning 日志文件：

```python
from medidiet.safety import SafetyGate

gate = SafetyGate(rule_pack, log_file_path="logs/safety.log")
```

日志原则：

- 只有安全阻断或不确定性事件写 `WARNING`。
- 默认 logger 使用 `NullHandler`，不会污染 stderr。
- 文件日志包含时间戳、进程号、线程号、整数 code、code name、患者内部 id、规则版本等字段。
- 业务逻辑不得依赖日志文本。

详细原则见 `docs/superpowers/specs/2026-05-15-safety-logging-principles.md`。

## 9. 版本兼容策略

后续扩展时应遵守：

- 顶层 `medidiet` 导出的 API 需要谨慎变更。
- 新疾病、新过敏、新禁忌优先通过 `ConceptRegistry` 和规则包扩展，不直接写死字符串判断。
- 新阻断原因应新增枚举 code，而不是用自然语言字符串表示。
- 外部 payload 字段使用 camelCase，Python 内部 dataclass 字段使用 snake_case。
- 涉及临床阈值的变更必须进入版本化规则包，并保留来源和审核信息。

## 10. LLM 解释与问答 API

LLM 是推荐后的可选增强层。它不能改变 `outcome`、推荐菜单、安全事件、排除原因或评分。

公共入口：

```python
from medidiet import (
    LLMConfig,
    LLMContextSanitizer,
    LLMExplanationEnhancer,
    LLMQuestionAnswerer,
    MockLLMProvider,
    OpenAICompatibleLLMProvider,
)
```

基本用法：

```python
context = LLMContextSanitizer().sanitize(result, patient, meal_label)
provider = OpenAICompatibleLLMProvider(LLMConfig.from_env())
enhanced = LLMExplanationEnhancer(provider).enhance(context, result)
answer = LLMQuestionAnswerer(provider).answer(context, result, "为什么推荐这个餐？")
```

默认脱敏策略不会发送 `patient_id`、原始图片、地址、手机号、身份证或完整病历。
