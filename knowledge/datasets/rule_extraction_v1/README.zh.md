# rule_extraction_v1

该数据集用于 DocRule-Agent 研究流程的可重复 dry-run 与真实 LLM opt-in 实验。

## Research Protocol

研究协议见 [docs/research/doc-rule-agent-research-protocol.md](../../../docs/research/doc-rule-agent-research-protocol.md)。

本次提交的系统级总结见 [docs/research/doc-rule-agent-commit-summary.md](../../../docs/research/doc-rule-agent-commit-summary.md)；真实 LLM 运行解读见 [docs/research/doc-rule-agent-real-llm-run-summary.md](../../../docs/research/doc-rule-agent-real-llm-run-summary.md)。

`extraction_observations.jsonl` 是 append-only 观察日志。普通单元测试不得默认写入该文件；真实 LLM 运行只有在显式 `--append-observations` 时才可追加。

实验词汇固定为 comparator arms C0-C8 和 observation points O1-O13。任何报告必须保留 `experiment_id`、`arm_id`、`dataset_id`、`doc_id` 和 source hash。
