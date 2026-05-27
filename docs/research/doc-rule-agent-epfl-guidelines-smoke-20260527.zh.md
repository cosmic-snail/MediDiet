# EPFL Guidelines 外部烟测记录（2026-05-27）

## 结论

本次新增 `rule_extraction_epfl_guidelines_smoke`，从 HuggingFace 数据集 `epfl-llm/guidelines`
抽样 8 条英文临床指南/公共卫生指南，转换为当前实验框架可读的 source card + manifest。

验证结果：

- dry-run 全矩阵已通过：`E1,E2,E3 × C1,C2,C3`，并生成 chunking、stability、coverage 等报告。
- 真实 LLM 已运行：`E1 × C1,C2,C3 × 8 docs × 1 repeat = 24 observations`。
- 真实 LLM operational failure 为 0；也就是没有 API 超时、错误码、调用异常空返回被纳入研究记录。
- 该数据集目前没有人工 gold，因此不能据此报告准确率/F1，只能用于外部 smoke 与观察。

## 数据集来源

- 上游数据集：`epfl-llm/guidelines`
- 上游文件：`open_guidelines.jsonl`
- 抽样方式：通过 HuggingFace dataset viewer API 按固定 row index 读取，不下载或提交完整 878 MB JSONL。
- 本仓库保存内容：每个文档只保存短 excerpt windows，不保存完整指南文本。

新增文件：

- `knowledge/datasets/rule_extraction_epfl_guidelines_smoke/manifest.jsonl`
- `knowledge/datasets/rule_extraction_epfl_guidelines_smoke/selection_manifest.jsonl`
- `knowledge/datasets/rule_extraction_epfl_guidelines_smoke/README.zh.md`
- `knowledge/source_documents/external_epfl_guidelines/*.md`
- `scripts/build_epfl_guidelines_smoke_dataset.py`

## 测试文档

本次外部 smoke 集包含 8 个 source card：

| doc_id | 主题 | 主要观察点 |
| --- | --- | --- |
| `epfl_cdc_physical_activity_diet_weight` | 饮食实践 + 运动 + 体重控制 | broad/contextual 文本是否误抽 |
| `epfl_cdc_who_flour_fortification` | 面粉强化、微量营养素 | schema 是否暴露 fortification 概念缺口 |
| `epfl_cma_obesity_clinical_practice` | 肥胖临床实践 | 体重管理/饮食行为是否被抽成规则 |
| `epfl_cma_type2_diabetes_primary_care` | 2 型糖尿病基层管理 | 糖尿病饮食建议是否能被识别 |
| `epfl_nice_ckd_dialysis_fluid_management` | CKD 透析液体/目标体重 | 肾病液体管理是否被当作营养邻近规则 |
| `epfl_nice_obesity_local_communities` | 社区肥胖干预 | 公共卫生建议是否过度抽取 |
| `epfl_pubmed_obesity_kidney_transplant` | 肾移植候选人肥胖管理 | 钾/蛋白/磷等 schema gap 是否以 suggested concept 出现 |
| `epfl_pubmed_ada_type1_diabetes_nutrition` | ADA 儿童青少年 1 型糖尿病营养治疗 | 明确 MNT/碳水/高纤维建议是否能抽出 |

## 评测标准

这次分成两层看：

1. 管线标准：数据集能否被 `manifest.jsonl` 加载，source card 是否能切出 `extractable_content`，dry-run 是否能展开实验矩阵并写报告。
2. 观察标准：真实 LLM 输出中，是否出现合理的 `parsed_rules`、`suggested_concepts`、`failures`、stability 指标和 operational failure 过滤。

当前不使用准确率/F1 做结论，因为 `gold_evaluation_set.jsonl` 为空。报告中的 precision/recall/f1 为 0 只表示没有可评测 gold，不表示模型质量为 0。

## 如何运行

重建数据集：

```bash
python scripts/build_epfl_guidelines_smoke_dataset.py
```

运行窄测试：

```bash
PYTHONPATH=src:knowledge/src pytest \
  knowledge/tests/test_epfl_guidelines_smoke_dataset.py \
  knowledge/tests/test_dataset_manifest_loader.py \
  knowledge/tests/test_dataset_chunking_strategies.py \
  -q --rootdir=.
```

运行 dry-run 全矩阵：

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_epfl_guidelines_smoke \
  --dry-run \
  --experiments E1,E2,E3 \
  --arms C1,C2,C3 \
  --chunk-strategies raw_card,extractable_content,source_notes_plus_extractable \
  --write-reports \
  --output-dir reports/epfl-guidelines-smoke-20260527-dry-run
```

运行真实 LLM：

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_epfl_guidelines_smoke \
  --real-llm \
  --experiments E1 \
  --arms C1,C2,C3 \
  --max-docs 0 \
  --write-reports \
  --output-dir reports/epfl-guidelines-smoke-20260527-real-llm
```

## Dry-Run 结果

输出目录：

- `reports/epfl-guidelines-smoke-20260527-dry-run/`

关键结果：

- chunking report rows：56
- total chunks：32
- chunks with frontmatter：8
- chunks with copyright handling：17
- dry-run stability rows：10
- dry-run field evaluation rows：0，因为没有 gold

含义：

- 数据集入口和报告生成路径正常。
- `raw_card` 会包含 frontmatter/source notes/copyright handling；这是 C1 的预期观察风险。
- `extractable_content` 更接近实验主体文本；这是 C2/C3 对照的核心。

## 真实 LLM 结果

输出目录：

- `reports/epfl-guidelines-smoke-20260527-real-llm/`

关键结果：

- provider/model：`openai_compatible` / `deepseek-v4-flash`
- observations：24
- operational failures：0
- evaluated records：0
- by arm：C1=8，C2=8，C3=8
- 覆盖文档：8/8，每个文档 3 条观察
- parsed rules：C1=2，C2=1，C3=1
- suggested concepts：C1=2，C2=0，C3=0
- empty output rate：0.833
- parse failure rate：0.0

被抽出的主要信号：

- `epfl_pubmed_obesity_kidney_transplant` 在 C1 下抽出 `weight_control` 规则，并提出 `high_potassium`、`high_protein` suggested concepts。
- `epfl_pubmed_ada_type1_diabetes_nutrition` 在 C1/C2/C3 下均抽出 `diabetes` 相关规则，包含 `high_fiber`、`vegetable_rich`，C1 还包含 `dessert`、`sugary_drink` 和 `controlled_carbs`。
- 两条 ADA 观察有 verifier JSON 解析失败，但主抽取结果成功解析；这属于 verifier 输出质量问题，不是 LLM API operational failure。

## 需要观察什么

建议主要观察以下内容：

- C1 是否因为看到完整 source card 而引入 metadata/source notes/copyright 段污染。
- C2 是否在只看正文时减少无关抽取。
- C3 是否因为带 source notes 而更容易理解外部数据来源和抽取边界。
- `suggested_concepts` 是否稳定暴露当前 schema 缺口，例如 `high_potassium`、`high_protein`。
- `no_rule_extracted` 是否合理：公共卫生、系统性指南、设备指南常常没有明确可结构化饮食规则。
- verifier JSON 解析失败是否需要单独纳入后续 extractor/verifier prompt 改进。

## 这次结果的含义

这次外部数据集能说明：

- 当前实验平台可以接入非自建、非中文、长篇指南来源。
- operational failure 过滤逻辑没有把 API 层失败混入研究观察。
- 当前 schema 对“标准饮食规则”能抽到少量结构化结果，但对公共卫生营养、强化食品、CKD 电解质/液体管理等主题会暴露概念覆盖不足。

这次外部数据集不能说明：

- 模型准确率、召回率或 F1。
- 哪个 arm 在真实质量上显著更好。
- 外部数据集是否已经适合作为正式 benchmark。

下一步如果要把它升级为正式评测集，应先人工冻结 8 条文档的 gold：

- 哪些文档应当抽出规则；
- 哪些文档应当明确为 negative；
- 哪些字段必须匹配 condition、hard exclusions、preferred tags、nutrition limits；
- 哪些新概念应该进入 registry，哪些只作为 suggested concept 观察。
