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
