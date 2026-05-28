# MedGUIDE PathRule 评测说明

## 定位

这条评测不是让大模型直接回答 MedGUIDE 多选题，而是评估：

```text
病例事实 + 路径规则 -> deterministic matcher -> 推荐答案
```

因此它更贴近 MediDiet 当前“抽取规则后做匹配推荐”的系统形态。

## 为什么不直接做 MCQA

MedGUIDE 原始 MCQA 可以评估 LLM 是否会直接答题，但这会混入模型医学常识和训练记忆。我们的系统要避免这个捷径：

```text
不采用：profile + options -> LLM -> answer
采用：profile -> facts；facts + rules -> matcher -> answer
```

当前第一版先接收外部 facts。后续可以把 facts 来源替换成病例事实抽取器。

## 新增模块

- `knowledge.path_rule_evaluation`
  - `PathRule`
  - `PathRulePrediction`
  - `path_rule_from_medguide_row`
  - `match_path_rules`
  - `evaluate_path_rule_prediction`
  - `evaluate_medguide_rows`

- `knowledge.medguide_path_rule_benchmark`
  - HuggingFace MedGUIDE 行读取
  - facts JSONL 读取
  - benchmark JSON 报告写出

## 运行方式

仅做管线 smoke：

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.medguide_path_rule_benchmark \
  --offset 0 \
  --limit 5 \
  --output reports/medguide-path-rule-benchmark-smoke.json
```

注意：默认 `oracle_path_facts` 会用 gold path 作为 facts，只能证明管线通，不能报告为模型性能。

使用外部病例事实：

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.medguide_path_rule_benchmark \
  --offset 0 \
  --limit 20 \
  --facts-jsonl reports/medguide-profile-facts.jsonl \
  --output reports/medguide-path-rule-benchmark-report.json
```

facts JSONL 格式：

```json
{"sample_id":"medguide-0","facts":["First relapse (morphologic or molecular)","PCR negative (by BM)","Transplant candidate"]}
```

## 指标

- `answer_accuracy`：最终推荐答案是否等于 MedGUIDE gold answer。
- `path_node_precision`：系统匹配路径中有多少属于 gold path。
- `path_node_recall`：gold path 中有多少被系统覆盖。
- `path_order_match`：已命中的 gold 节点是否保持正确顺序。
- `missing_path_nodes`：漏掉的 gold path 节点。
- `unsupported_path_nodes`：系统匹配出的非 gold 节点。

## 与原营养推荐兼容

本需求没有修改 `ExtractedConditionRule`、营养规则抽取器或原 `rule_evaluation`。PathRule 是并行新增的评测层，未来可以把营养规则作为 action node 绑定到路径叶子，但当前不改变原有能力。
