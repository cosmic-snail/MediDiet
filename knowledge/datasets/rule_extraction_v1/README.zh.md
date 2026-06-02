# rule_extraction_v1

这是一个用于营养与疾病规则抽取研究的数据集。系统构建链路保持 no-human-in-loop：`manifest.jsonl` 和 `expected_rules.jsonl` 中的标签是机器生成弱标签，不代表临床金标准。

该数据集同时支持 DocRule-Agent 研究流程的可重复 dry-run 与真实 LLM opt-in 实验。

## 文件

- `manifest.jsonl`：60 个真实来源 source card 的元数据和弱标签。
- `expected_rules.jsonl`：机器生成的预期抽取假设。
- `extraction_observations.jsonl`：无人闭环抽取运行后的 append-only 观察结果。
- `gold_evaluation_set.jsonl`：冻结的离线评测真值子集，只用于计算指标，不用于更新 prompt、标签或规则。
- `gold_audit.jsonl`：冻结 gold 的证据分层与审计建议，用于区分 clean headline score 与 exploratory/schema-gap/contextual rows，不修改 `gold_evaluation_set.jsonl`。
- `challenge_set.jsonl`：上下文复杂或当前 schema 不支持的样本，用于失败分析，不强制纳入 F1。

## 研究协议

研究协议见 [docs/research/doc-rule-agent-research-protocol.md](../../../docs/research/doc-rule-agent-research-protocol.md)。

本次提交的系统级总结见 [docs/research/doc-rule-agent-commit-summary.md](../../../docs/research/doc-rule-agent-commit-summary.md)；真实 LLM 运行解读见 [docs/research/doc-rule-agent-real-llm-run-summary.md](../../../docs/research/doc-rule-agent-real-llm-run-summary.md)。

实验词汇固定为 comparator arms C0-C8 和 observation points O1-O13。任何报告必须保留 `experiment_id`、`arm_id`、`dataset_id`、`doc_id` 和 source hash。

## 评测边界

本数据集用于研究系统行为、可追溯性、稳定性和失败类型。任何规则候选都不是已审核临床建议。

LLM API 层面的运行失败不进入研究观察范围，包括超时、HTTP/provider 错误、transport 异常和异常空响应。这类问题只作为 `operational_failures` 记录运行卫生状态，不参与字段评分、稳定性分析或架构对比。

普通单元测试不得默认写入 `extraction_observations.jsonl`；真实 LLM 运行只有在显式 `--append-observations` 时才可追加。

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
- `reports/rule-extraction-v1-real-llm-field-evaluation-report.json`
- `reports/rule-extraction-v1-real-llm-summary.md`

## 研究管线 dry-run / real-run

dry-run 全矩阵用于确认管线、报告和 registry 不坏：

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --dry-run \
  --output-dir reports
```

真实 LLM opt-in 示例：

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --real-llm \
  --experiments E1 \
  --arms C1,C2,C3 \
  --max-docs 2 \
  --output-dir reports
```

`--max-docs` 是真实 LLM 的保护性上限，默认只跑 2 个文档；传 `--max-docs 0` 表示跑完整 manifest。
