# MedGUIDE 数据集调研经验沉淀

## 结论

MedGUIDE 适合用来诊断“病例 profile -> facts -> 路径规则匹配 -> 选项推荐”这一段流程，但不适合作为当前阶段的主评测数据集来验证“权威资料 -> 规则抽取”。

本轮修改已经回退 MedGUIDE 旁路评测代码，只保留这份结论文档，避免把后半段 matcher 的可行性误认为核心规则抽取能力已经被验证。

## 背景

当前营养推荐规则系统的关键风险点是：

```text
权威资料/指南原文 -> 结构化规则
```

后续的事实匹配与推荐逻辑相对宽松，且可以通过工程规则、召回策略和人工 review 逐步优化。因此，评测数据集应该优先覆盖“从权威资料抽取规则”的能力，而不是只覆盖“已有规则下如何匹配 profile”。

## 本次 MedGUIDE 方案实际验证了什么

MedGUIDE MCQA row 中提供了：

- `profile`：病例描述。
- `options`：候选选项。
- `answer` / `answer_text`：正确选项。
- `path`：从 guideline decision path 派生的路径节点。
- `disease`：疾病/任务分组。

因此它天然支持的测试流程是：

```text
MedGUIDE row.path -> PathRule
MedGUIDE profile -> facts
facts + PathRule -> deterministic matcher -> option
```

这能观察：

- profile fact extractor 是否能从病例描述中提取关键事实。
- matcher 是否能根据 facts 选中合适路径。
- 最终选项是否等于 MedGUIDE gold answer。

但这不是我们的首要风险点。

## 为什么不适合作为主评测

MedGUIDE 公开 MCQA 数据集没有稳定提供每个样本对应的原始权威资料片段、页码、完整 guideline text 或可验证 citation。它提供的是已经加工过的 `path`。

所以它很难直接评估：

```text
权威指南原文 -> LLM/抽取器 -> 结构化规则
```

如果把 `path` 直接作为规则输入，只能说明规则表示和匹配管线能跑通，不能证明系统能从权威资料中正确抽取规则。

## 本次发现的边界

MedGUIDE 可以作为辅助数据集，但应该明确标注用途：

- 可以：gold path alignment，验证已知路径下的 matcher 行为。
- 可以：profile fact extraction 的小样本诊断。
- 可以：未来有权威 source tree / source text 后，用 `path` 作为 gold 对照。
- 不适合：单独证明“权威资料抽规则”的能力。
- 不适合：用 MCQA accuracy 直接代表规则抽取质量。

## 后续选择数据集的标准

下一轮数据集应优先满足：

1. 有可输入的权威资料文本或结构化 guideline source。
2. 有 gold rules、gold decision paths、gold recommendations 或人工标注答案。
3. 能建立 source span / citation 与规则之间的对应关系。
4. 允许我们区分错误来源：
   - 规则抽取错误。
   - 条件归一化错误。
   - fact 抽取错误。
   - matcher/ranking 错误。
   - option mapping 错误。
5. 许可允许本地实验、报告和必要的衍生标注。

## 推荐的下一步

优先寻找或构造能覆盖以下流程的数据集：

```text
source document
  -> extracted rules
  -> gold rule comparison
  -> optional profile matching
```

如果公开数据集不足，可以先用小规模人工 gold set：

- 选择 5-10 份权威营养指南/共识片段。
- 人工标注每段应抽出的条件、动作、适用人群、证据来源。
- 用现有 rule extraction pipeline 抽取。
- 评估规则级 precision、recall、字段完整性和 citation 覆盖率。

这个方向比继续扩展 MedGUIDE matcher 更贴近当前系统风险。
