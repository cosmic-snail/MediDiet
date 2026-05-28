# rule_extraction_epfl_guidelines_smoke

这个数据集是从 HuggingFace `epfl-llm/guidelines` 的公开 `open_guidelines.jsonl`
子集中抽样得到的外部烟测集。它的目标不是替代 `rule_extraction_v1` 的金标评测，
而是用来源、版式、主题都不同的真实英文指南文本检查规则抽取实验管线是否稳健。

## 数据来源

- 上游数据集：https://huggingface.co/datasets/epfl-llm/guidelines
- 读取方式：HuggingFace dataset viewer API，固定 row index 抽样。
- 本仓库只保存短 excerpt windows，不保存完整上游 JSONL。

## 选择标准

- 与 MediDiet 当前研究范围相关：肥胖、糖尿病、CKD、营养治疗、饮食模式、
  体重/液体管理或公共卫生营养。
- 优先选择 CMA、NICE、ADA/PubMed、CDC 等来源中具备 guideline/position statement
  语境的行。
- 排除明显不属于当前研究范围的肿瘤治疗、职业化学暴露、疫苗、传染病控制等主题。

## 文件说明

- `manifest.jsonl`：实验平台入口，声明 source card、主题标签和来源元数据。
- `selection_manifest.jsonl`：记录每个 source card 对应的上游 row index、row id 和选择理由。
- `expected_rules.jsonl`、`gold_evaluation_set.jsonl`、`challenge_set.jsonl`：当前为空。
  这表示该数据集先用于外部 smoke/观察，不用于准确率或 F1 结论。
- `extraction_observations.jsonl`：预留给 `--append-observations` 的真实 LLM 观察记录。

## 适用范围

适合回答：外部指南文本进入当前框架后，dry-run、chunking、LLM 抽取、
稳定性摘要和报告生成是否正常。

不适合回答：模型抽取准确率是否达到某个阈值。因为本数据集尚未冻结人工 gold。
