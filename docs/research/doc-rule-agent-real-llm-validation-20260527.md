# DocRule-Agent 真实 LLM 验证报告（2026-05-27）

## 运行范围

本次验证使用真实 LLM provider，目标是确认 `rule_extraction_dataset_smoke` 的真实 LLM 路径可以完成：

- 读取 `rule_extraction_v1` 数据集。
- 按 `E1` 实验展开 `C1/C2/C3` 三个 arm。
- 调用真实两阶段抽取器。
- 生成 observation、gold evaluation、稳定性摘要和可视化 Markdown 摘要。
- 将 LLM API 层失败单独归入 `operational_failures`。

执行命令：

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --real-llm \
  --experiments E1 \
  --arms C1,C2,C3 \
  --max-docs 2 \
  --output-dir reports/real-llm-validation-20260527
```

本次没有使用 `--append-observations`，因此没有写入长期日志 `knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl`。

## 输入文档

`--max-docs 2` 使本次只取 `manifest.jsonl` 的前两个 source card：

| doc_id | 文档 | source type | 是否有 gold |
| --- | --- | --- | --- |
| `zh_guideline_hypertension_food_therapy_2023` | 成人高血压食养指南（2023年版） | guideline | 是 |
| `zh_guideline_diabetes_food_therapy_2023` | 成人糖尿病食养指南（2023年版） | guideline | 否 |

因此本次有 6 条真实 observation，但只有 3 条进入 golden evaluation：

```text
1 experiment × 3 arms × 2 docs = 6 observations
1 gold doc × 3 arms = 3 evaluated records
```

## 输出文件

本次报告输出在：

- `reports/real-llm-validation-20260527/rule-extraction-v1-real-llm-report.json`
- `reports/real-llm-validation-20260527/rule-extraction-v1-real-llm-field-evaluation-report.json`
- `reports/real-llm-validation-20260527/rule-extraction-v1-real-llm-summary.md`

## 运行结果概览

| 项目 | 结果 |
| --- | --- |
| provider | `openai_compatible` |
| model | `deepseek-v4-flash` |
| observation_count | 6 |
| operational_failure_count | 0 |
| evaluated_record_count | 3 |
| suggested_concept_count | 1 |
| unique_suggested_concept_count | 1 |

本次没有 LLM API 层失败。也就是说，没有超时、transport 错误、provider 错误或异常空响应被排除。

## Golden Evaluation

整体分数：

| 指标 | 数值 |
| --- | ---: |
| precision | 1.000 |
| recall | 0.333 |
| F1 | 0.500 |

按 arm 分组：

| experiment | arm | 输入策略 | evaluated records | precision | recall | F1 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| E1 | C1 | `raw_card` | 1 | 0.000 | 0.000 | 0.000 |
| E1 | C2 | `extractable_content` | 1 | 1.000 | 1.000 | 1.000 |
| E1 | C3 | `source_notes_plus_extractable` | 1 | 0.000 | 0.000 | 0.000 |

解释：

- 只有高血压文档有 frozen gold，因此每个 arm 只有 1 条可评分记录。
- `C2 extractable_content` 抽到了 `hypertension` 和 `sodium_mg daily 2300`，被当前评测器视为 `partial_match`，计入真阳性。
- `C1 raw_card` 和 `C3 source_notes_plus_extractable` 都抽到了高血压相关规则，但缺少 numeric sodium limit，因此被标为 `miss`。
- 当前 gold 中的高血压 sodium 目标是 `sodium_mg daily 2000`。模型在 C2 中抽到的是 `2300`，所以字段细节不是完全一致。

## Observation 明细

| arm | doc_id | source_content_strategy | parsed_rules | suggested_concepts | parse_status | 主要输出 |
| --- | --- | --- | ---: | ---: | --- | --- |
| C1 | `zh_guideline_hypertension_food_therapy_2023` | `raw_card` | 1 | 0 | parsed | `hypertension`，`high_sodium`，`low_sodium`，无数值限制 |
| C1 | `zh_guideline_diabetes_food_therapy_2023` | `raw_card` | 1 | 0 | parsed | `diabetes`，`balanced`，`controlled_carbs`，无数值限制 |
| C2 | `zh_guideline_hypertension_food_therapy_2023` | `extractable_content` | 1 | 1 | parsed | `hypertension`，`low_sodium`，`sodium_mg <= 2300 daily`，建议概念 `alcohol` |
| C2 | `zh_guideline_diabetes_food_therapy_2023` | `extractable_content` | 1 | 0 | parsed | `diabetes`，`balanced`，`controlled_carbs`，无数值限制 |
| C3 | `zh_guideline_hypertension_food_therapy_2023` | `source_notes_plus_extractable` | 1 | 0 | parsed | `hypertension`，`high_sodium`，`low_sodium`，无数值限制 |
| C3 | `zh_guideline_diabetes_food_therapy_2023` | `source_notes_plus_extractable` | 1 | 0 | parsed | `diabetes`，`balanced`，`controlled_carbs`，无数值限制 |

## 观察点

本次真实 LLM report 主要落到了以下 observation points：

### O5 Prompt Assembly / 输入策略

每条 observation 都记录了：

- `arm_id`
- `input_variant`
- `source_content_strategy`
- `input_hash`
- comparator strategy 名称

本次验证覆盖：

- `C1 -> raw_card`
- `C2 -> extractable_content`
- `C3 -> source_notes_plus_extractable`

含义：实验平台能够把同一文档按不同 source card 内容策略送入同一个两阶段抽取器。

### O6 Provider Call / 真实模型调用

每条 observation 都记录：

- provider: `real_llm`
- latency_ms
- retry_count
- empty_output

本次 6 条 observation 均成功返回，`operational_failure_count = 0`，`empty_output = false`。

各 arm 的调用耗时大致为 17s 到 51s。真实模型调用耗时较长，后续扩大样本时应继续使用 `--max-docs` 控制成本。

### O8 Structured Parse / 结构化解析

每条 observation 都记录：

- `parsed_rule_count`
- `suggested_concept_count`

本次所有 observation 都至少解析出 1 条 rule。只有 `C2 + 高血压文档` 额外产生 1 个 suggested concept：`alcohol`。

含义：真实模型输出能被当前 parser 正常转成结构化规则或建议概念。

### O10 Field Evaluation / 字段评测

本次新增真实 LLM 与 `gold_evaluation_set.jsonl` 的字段评测闭环。

对于高血压 gold 记录：

- C1：condition 和部分标签相关，但缺少 numeric sodium limit，判为 miss。
- C2：condition 命中，并抽到 sodium numeric limit，判为 partial_match。
- C3：condition 和部分标签相关，但缺少 numeric sodium limit，判为 miss。

含义：真实 LLM 路径已经能回答“相对 frozen gold 准不准”，但当前样本太小，不能作为统计结论。

### O11 Stability / 稳定性

本次稳定性摘要：

| 指标 | 数值 |
| --- | ---: |
| parse_failure_rate | 0.000 |
| empty_output_rate | 0.000 |
| pairwise_canonical_rule_set_similarity | 0.447 |

注意：本次不是重复运行稳定性实验，而是不同 arm、不同文档混合在一起的 6 条 observation。因此 `pairwise_canonical_rule_set_similarity = 0.447` 只能说明本次输出集合差异较大，不能直接解释为同一输入重复运行不稳定。

## 需要关注的点

1. `C2 extractable_content` 在本次高血压 gold 上表现最好。

   这符合 E1 的核心假设：去掉 frontmatter、source notes、copyright handling 后，抽取器更容易聚焦可抽取正文。

2. C1/C3 能抽到疾病和标签，但没有抽到 sodium numeric limit。

   这说明 source card 噪声或额外上下文可能影响数值阈值抽取，需要后续扩大样本验证。

3. C2 抽到 `sodium_mg <= 2300 daily`，而 gold 是 `2000`。

   当前评测把它计为 partial_match。这个差异值得单独看 source card 与 gold 的构造逻辑，确认是模型误抽、source card 表述问题，还是 gold 阈值过严。

4. `zh_guideline_diabetes_food_therapy_2023` 没有进入 gold evaluation。

   它仍然产生了 observation，但不会影响 precision/recall/F1。后续如果要评价糖尿病文档，需要把它加入 frozen gold 或选择已有 gold 的 diabetes 文档。

5. 本次没有 API 层失败。

   这说明当前 provider 配置可用；但这只是一次小规模验证，不代表大批量运行时没有稳定性问题。

## 结论

本次真实 LLM 验证证明当前实验入口可以完成端到端真实运行：

```text
dataset -> source card -> content strategy -> chunking -> real LLM extraction/validation -> observation -> gold evaluation -> report/summary
```

从本次小样本看，`C2 extractable_content` 是最值得继续扩展验证的输入策略。下一步建议扩大到所有 frozen gold 文档，并保持 `C1/C2/C3` 对照，以观察 numeric limit recall、字段 F1 和 suggested concepts 是否稳定。
