---
doc_id: zh_paper_diabetes_medical_nutrition_review
title: "[Computer Assisted Nutrition Therapy for Patients with Type 2 Diabetes]"
language: zh
source_type: paper
source_url: "https://pubmed.ncbi.nlm.nih.gov/12881874/"
publisher: "Zhejiang Da Xue Xue Bao Yi Xue Ban"
year: "2003"
disease_focus: ["diabetes"]
nutrition_focus: ["carbs_g", "dietary_pattern", "energy_kcal", "medical_nutrition_therapy"]
evaluation_labels: ["should_extract", "contextual"]
annotation_method: llm_generated
label_model: "deepseek-v4-flash"
label_prompt_version: "metadata-labeling-v1"
review_status: unreviewed
label_confidence: 0.81
failure_is_valid_observation: true
copyright_mode: short_excerpt_or_summary
notes: "PubMed record marked Article in Chinese; Chinese-language clinical trial on nutrition therapy support for type 2 diabetes."
---

# [Computer Assisted Nutrition Therapy for Patients with Type 2 Diabetes]

## Source Notes

Article in Chinese; 中文论文来源. This source card tests extraction from a Chinese-language type 2 diabetes nutrition-therapy study.

## Extractable Source Content

- 论文研究计算机辅助营养治疗在 2 型糖尿病患者中的应用。
- 可抽取信号包括医学营养治疗、碳水化合物管理、总能量控制和随访调整。
- 若源文献没有给出固定克数目标，抽取器应避免生成不存在的 carbs_g 或 energy_kcal 阈值。

## Copyright Handling

This card uses faithful Chinese summary only and links to the PubMed record instead of reproducing article text.
