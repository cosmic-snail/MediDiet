---
doc_id: zh_paper_ckd_dietary_management_review
title: "慢性肾脏病患者营养管理综述"
language: zh
source_type: paper
source_url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC7652660/"
publisher: "Kidney Research and Clinical Practice"
year: "2020"
disease_focus: ["chronic_kidney_disease"]
nutrition_focus: ["protein", "sodium_mg", "potassium", "phosphorus", "energy_kcal"]
evaluation_labels: ["concept_gap", "contextual"]
annotation_method: llm_generated
label_model: "deepseek-v4-flash"
label_prompt_version: "metadata-labeling-v1"
review_status: unreviewed
label_confidence: 0.79
failure_is_valid_observation: true
copyright_mode: short_excerpt_or_summary
notes: "PMC review on CKD nutritional management; renal nutrition concepts beyond sodium are expected concept gaps."
---

# 慢性肾脏病患者营养管理综述

## Source Notes

This Chinese source card tests CKD nutrition extraction where the schema should expose several gaps.

## Extractable Source Content

- CKD 营养管理通常需要结合病程、透析状态、营养状况和合并症进行个体化调整。
- sodium_mg 相关建议可能被当前指标覆盖。
- protein、potassium 和 phosphorus 是肾病营养管理中的关键概念，但当前 schema 不应把它们误写成已有的常规宏量营养指标。

## Copyright Handling

This card uses faithful Chinese summary only and links to the open-access source instead of reproducing article text.
