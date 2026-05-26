# DocRule-Agent E1 实验运行手册与结果

## 运行日期

2026-05-26

## 目的

本文档记录如何运行当前实验框架，以及如何解读第一次 E1 真实 LLM 运行结果。目标分两步：先确认整条实验管线可用，再比较三种 source card 输入变体对数值型规则抽取的影响。

## 已执行命令

### Dry-Run 全矩阵

Dry-run 用于验证研究管线能在不访问网络、不调用 LLM 的情况下生成全部矩阵报告。

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --benchmark-portfolio doc_rule_agent_lifecycle_v1 \
  --experiment-matrix doc_rule_agent_v1 \
  --benchmark-experiments B1,B2,B3,B4,B5,B6,B7 \
  --experiments E1,E2,E3,E4,E5,E6,E7 \
  --arms C0,C1,C2,C3,C4,C5,C6,C7,C8 \
  --chunk-strategies raw_card,extractable_content,source_notes_plus_extractable \
  --dry-run \
  --write-reports
```

### 真实 LLM E1 运行

这次运行对每个文档、每个输入 arm 各执行一次 E1。

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --benchmark-portfolio doc_rule_agent_lifecycle_v1 \
  --experiment-matrix doc_rule_agent_v1 \
  --benchmark-experiments B1 \
  --experiments E1 \
  --arms C1,C2,C3 \
  --chunk-strategies raw_card,extractable_content,source_notes_plus_extractable \
  --real-llm \
  --append-observations \
  --write-reports
```

## 测试文档

当前数据集包含两个 source card。

| doc_id | 来源 | 关注点 | Gold Rule |
| --- | --- | --- | --- |
| `en_guideline_who_sodium_2012` | WHO sodium guideline source card | hypertension / sodium | `hypertension`, `sodium_mg daily <= 2000` |
| `en_manual_diabetes_sugar_case` | diabetes sugar stability fixture | diabetes / added sugar | `diabetes`, `sugar_g daily <= 25` |

这些 source card 是摘要或短摘录，不是完整版权指南原文。

## E1 Arms

E1 是 chunking/input-selection ablation，也就是“输入文本选择方式”的消融实验。

| Arm | Input Variant | 含义 |
| --- | --- | --- |
| `C1` | `raw_card` | LLM 看到完整 source card，包括 frontmatter、source notes 和 copyright handling 文本。 |
| `C2` | `extractable_content` | LLM 只看到 `## Extractable Source Content` 后面的可抽取正文。 |
| `C3` | `source_notes_plus_extractable` | LLM 看到 source notes 加可抽取正文，但不看到 frontmatter 或 copyright handling 块。 |

## 评测标准

当前 E1 评测关注抽取出的候选规则是否在字段层面匹配 frozen gold rule。

主要字段包括：

- condition：期望的疾病/状态代码，例如 `hypertension` 或 `diabetes`。
- preferred tags：期望饮食标签，例如 `low_sodium` 或 `low_sugar`。
- nutrition limits：营养指标、scope、最大值和时间窗口。
- verification verdict：verifier 对候选规则的判断，是通过、拒绝还是需要修订。

在当前 smoke-scale 数据集里，最关键的信号是 numeric-limit recovery，也就是能否抽回数值阈值：

- Sodium card 应该抽回 `sodium_mg daily <= 2000`。
- Diabetes card 应该抽回 `sugar_g daily <= 25`。

当前实现注意事项：解析出的 daily limit 目前会记录 `window_hours: null`，而 gold row 中写的是 `window_hours: 24`。人工阅读报告时，应先把它视为一个后续需要修复的 normalization 问题；底层的 metric/scope/value 仍然可以直接检查。

## 需要观察什么

### 1. Chunking 质量

报告位置：

```text
reports/rule-extraction-v1-chunking-report.json
```

观察项：

- 每种策略的 total chunks。
- `chunks_with_frontmatter`。
- `chunks_with_copyright_handling`。
- `chunks_starting_mid_word`。
- representative previews。

含义：

- 如果 `extractable_content` 中仍然包含 frontmatter 或 copyright 文本，说明预处理策略泄漏了非来源正文材料。
- 如果 chunk 从单词中间开始，说明 overlap 行为可能扭曲 prompt。

### 2. 真实 LLM 抽取输出

报告位置：

```text
reports/rule-extraction-v1-real-llm-report.json
```

观察项：

- `observation_count`。
- `operational_failure_count`。
- 每条 observation 的 `arm_id`、`input_variant`、`doc_id`。
- `parsed_rules`。
- `nutrition_limits`。
- `verification_verdict`。
- `failures`。

含义：

- `operational_failures` 是 API/transport 层问题，已经排除在研究指标之外。
- `observations` 是有效研究记录。
- 如果规则抽到了正确 condition，但没有 numeric limit，这是部分抽取失败。
- 如果 verifier 结果是 `rejected`，该候选规则不应视为可靠抽取结果。

### 3. Append-Only Observation Log

数据集日志位置：

```text
knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl
```

观察项：

- 每条有效研究 observation 对应一个 JSON object。
- `experiment_id`、`arm_id`、`input_variant`、`doc_id`。
- `observation_points.O5`、`O6`、`O8`。

含义：

- 这个文件是有效研究 observation 的机器历史记录。
- API 调用失败不应该出现在这里。

## 当前真实 LLM E1 结果

本次运行产生：

- research observations: 6
- operational failures: 0

| doc_id | Arm | Input Variant | Parsed Rule Summary | Verifier |
| --- | --- | --- | --- | --- |
| `en_guideline_who_sodium_2012` | `C1` | `raw_card` | `hypertension`, `sodium_mg daily <= 2000` | pass |
| `en_guideline_who_sodium_2012` | `C2` | `extractable_content` | `hypertension`, `sodium_mg daily <= 2000` | pass |
| `en_guideline_who_sodium_2012` | `C3` | `source_notes_plus_extractable` | `hypertension`, `sodium_mg daily <= 2000` | pass |
| `en_manual_diabetes_sugar_case` | `C1` | `raw_card` | `diabetes`, 无 numeric limit | rejected |
| `en_manual_diabetes_sugar_case` | `C2` | `extractable_content` | `diabetes`, 无 numeric limit | rejected |
| `en_manual_diabetes_sugar_case` | `C3` | `source_notes_plus_extractable` | `diabetes`, `sugar_g daily <= 25` | pass |

## 结果解读

Sodium card 对当前 extractor 来说较容易：三种输入变体都恢复了 sodium 数值阈值。

Diabetes card 对输入选择更敏感。在本次运行中，`source_notes_plus_extractable` 成功恢复 sugar 数值阈值并通过验证，而 `raw_card` 与 `extractable_content` 都漏掉了 numeric limit，并被 verifier 拒绝。这还不是统计结论，但它是一个有价值的观察：对于较短的 fixture-like source card，加入 source notes 可能帮助模型建立上下文。

下一步值得对同两个文档重复 E1 多次，再检查 diabetes 的 `C3` 优势是否稳定，还是只是一次随机结果。

## 实用阅读清单

审阅一次运行时，建议按这个顺序检查：

1. `operational_failure_count`：如果非零，这些调用不进入研究评分。
2. `observation_count`：确认剩余多少条有效研究记录。
3. `input_variant`：确认实际使用的 arm 是否符合预期。
4. `parsed_rules[].nutrition_limits`：检查数值阈值是否恢复。
5. `verification_verdict`：区分 accepted、rejected 或 revision-needed 候选规则。
6. `extraction_observations.jsonl`：确认有效 observations 已被追加记录。
