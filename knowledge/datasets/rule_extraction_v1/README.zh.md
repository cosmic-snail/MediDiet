# rule_extraction_v1

这是一个用于营养与疾病规则抽取研究的数据集。系统构建链路保持 no-human-in-loop：`manifest.jsonl` 和 `expected_rules.jsonl` 中的标签是机器生成弱标签，不代表临床金标准。

## 文件

- `manifest.jsonl`：60 个真实来源 source card 的元数据和弱标签。
- `expected_rules.jsonl`：机器生成的预期抽取假设。
- `extraction_observations.jsonl`：无人闭环抽取运行后的观察结果。
- `gold_evaluation_set.jsonl`：冻结的离线评测真值子集，只用于计算指标，不用于更新 prompt、标签或规则。
- `challenge_set.jsonl`：上下文复杂或当前 schema 不支持的样本，用于失败分析，不强制纳入 F1。

## 评测边界

本数据集用于研究系统行为、可追溯性、稳定性和失败类型。任何规则候选都不是已审核临床建议。

## 本地校验

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

## 默认回归

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_loader.py knowledge/tests/test_documents.py knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

## 数据集计数

以 `manifest.jsonl` 为准：

- guideline: 24
- paper: 18
- manual: 18
- zh: 30
- en: 30

`knowledge/source_documents/guidelines/` 目录中还包含项目既有的 legacy 卡片，目录文件数可能大于本数据集的 guideline 数。

## 真实 LLM smoke

真实 LLM smoke 需要显式环境变量。该测试只用于观察无人闭环抽取行为，不会修改 `gold_evaluation_set.jsonl`。

```bash
MEDIDIET_LLM_SMOKE_TEST=1 \
MEDIDIET_LLM_RULE_SMOKE_TEST=1 \
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_real_llm_extraction_smoke.py -q --rootdir=.
```

## 真实材料观测 smoke

该测试使用 `rule_extraction_v1` 的真实 source cards，而不是手写 `DocumentChunk`。默认测试会输出切块报告：

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset_smoke_reports.py -q --rootdir=.
```

报告位置：

- `reports/rule-extraction-v1-chunking-report.json`

如需调用真实 LLM 跑 gold 子集，需显式开启：

```bash
MEDIDIET_LLM_DATASET_SMOKE_TEST=1 \
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset_smoke_reports.py -q --rootdir=.
```

真实 LLM 报告位置：

- `reports/rule-extraction-v1-real-llm-report.json`
