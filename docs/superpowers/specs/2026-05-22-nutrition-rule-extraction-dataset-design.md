# Nutrition Rule Extraction Dataset Design

Version: 0.1.0
Date: 2026-05-22
Target: Build a 60-source bilingual nutrition and disease knowledge corpus for testing the MediDiet rule extraction module.

## 1. Objective

Build a realistic dataset of guidelines, academic papers, and web/patient-education articles about nutrition and chronic diseases. The dataset will test whether the `knowledge` package can import documents, chunk them, retrieve relevant fragments, extract candidate nutrition rules, surface concept gaps, and avoid fabricating rules from weak evidence.

This is an evaluation dataset, not a production medical rule pack. It should contain realistic source text and traceable metadata, but every extracted rule remains a candidate until reviewed.

## 2. Scope

The first complete version, `rule_extraction_v1`, contains 60 source cards:

| Source class | Chinese | English | Total |
| --- | ---: | ---: | ---: |
| Guidelines / standards | 12 | 12 | 24 |
| Papers / reviews | 9 | 9 | 18 |
| Web articles / patient education | 9 | 9 | 18 |
| Total | 30 | 30 | 60 |

Disease and topic coverage:

- Hypertension and sodium reduction.
- Diabetes and carbohydrate, sugar, meal planning, and weight control.
- Hyperlipidemia and saturated fat, trans fat, oils, and fried/fatty foods.
- Obesity and energy control.
- Chronic kidney disease and sodium, protein, potassium, and phosphorus.
- Gout / hyperuricemia and purine, alcohol, fructose, hydration, and weight loss.
- General healthy diet guidance that creates cross-disease constraints.

## 3. Repository Layout

The dataset should be stored under the existing `knowledge` package:

```text
knowledge/
├── source_documents/
│   ├── guidelines/
│   │   ├── zh_guideline_hypertension_food_therapy_2023.md
│   │   └── en_guideline_who_sodium_2012.md
│   ├── papers/
│   │   ├── en_paper_diabetes_nutrition_consensus_2019.md
│   │   └── zh_paper_hypertension_diet_review_*.md
│   └── manual/
│       ├── en_manual_cdc_diabetes_meal_planning_2024.md
│       └── zh_manual_nhc_food_therapy_interview_2024.md
└── datasets/
    └── rule_extraction_v1/
        ├── README.zh.md
        ├── manifest.jsonl
        └── gold_rules.jsonl
```

`manual/` is used for web articles, blog-like explainers, and patient education pages because the current `KnowledgeDocument.source_type` enum only allows `guideline`, `paper`, `food_db`, and `manual`.

## 4. Source Card Format

Each local source card is a Markdown document with a metadata header followed by source-focused content. The file must be readable by the current `KnowledgeLoader`, so no custom parser is required for ingestion.

```markdown
---
doc_id: en_guideline_who_sodium_2012
title: "WHO Guideline: Sodium Intake for Adults and Children"
language: en
source_type: guideline
source_url: "https://www.who.int/publications/i/item/9789241504836"
publisher: "World Health Organization"
year: "2012"
disease_focus: ["hypertension", "cardiovascular_risk"]
nutrition_focus: ["sodium_mg"]
evaluation_labels: ["should_extract"]
---

# WHO Guideline: Sodium Intake for Adults and Children

## Source Notes

This source is included to test extraction of explicit sodium limits.

## Extractable Source Content

Summarized or short excerpted source content goes here.
```

Content rules:

- Include exact source URL and publisher/institution in the header.
- Use short source excerpts only where needed for evidence quotes; otherwise use faithful summaries.
- Do not paste full copyrighted articles or full guideline chapters.
- Keep each card focused on 1-3 extractable nutrition claims or one deliberate negative/contextual case.
- Keep section headings plain so the existing paragraph-based chunker creates useful chunks.

## 5. Manifest Format

`manifest.jsonl` contains one JSON object per source card:

```json
{
  "doc_id": "en_guideline_who_sodium_2012",
  "path": "knowledge/source_documents/guidelines/en_guideline_who_sodium_2012.md",
  "title": "WHO Guideline: Sodium Intake for Adults and Children",
  "language": "en",
  "source_type": "guideline",
  "source_url": "https://www.who.int/publications/i/item/9789241504836",
  "publisher": "World Health Organization",
  "year": "2012",
  "disease_focus": ["hypertension", "cardiovascular_risk"],
  "nutrition_focus": ["sodium_mg"],
  "evaluation_labels": ["should_extract"],
  "copyright_mode": "short_excerpt_or_summary",
  "notes": "Explicit population sodium threshold; useful for per-day limit extraction."
}
```

Required fields:

- `doc_id`
- `path`
- `title`
- `language`
- `source_type`
- `source_url`
- `publisher`
- `year`
- `disease_focus`
- `nutrition_focus`
- `evaluation_labels`
- `copyright_mode`

## 6. Gold Rule Format

`gold_rules.jsonl` contains expected extraction behavior. A single document may map to zero, one, or multiple expected outputs.

```json
{
  "gold_id": "gold_en_guideline_who_sodium_2012_001",
  "doc_id": "en_guideline_who_sodium_2012",
  "expected_behavior": "rule",
  "condition": {"kind": "condition", "value": "hypertension"},
  "hard_exclusions": [{"kind": "contraindication", "value": "high_sodium"}],
  "preferred_tags": [{"kind": "nutrition_tag", "value": "low_sodium"}],
  "nutrition_limits": [
    {"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": null}
  ],
  "evidence_hint": "sodium threshold for adults",
  "confidence_floor": 0.75
}
```

Supported `expected_behavior` values:

- `rule`: the current extractor should produce a structured candidate rule.
- `suggested_concept`: the source contains useful concepts outside the current registry or nutrient metric set.
- `negative`: the extractor should not produce a rule.
- `contextual`: the source contains a rule only under a condition, stage, or care setting.
- `conflict`: the source deliberately contrasts different recommendations and should test verifier behavior.

## 7. Evaluation Labels

Every source card gets at least one label:

- `should_extract`: explicit rule compatible with current `NutrientMetric` values: `energy_kcal`, `carbs_g`, `fat_g`, `sodium_mg`, `sugar_g`.
- `concept_gap`: clinically useful concepts outside the current extractor/rule metric surface, such as protein, potassium, phosphorus, purine, alcohol, hydration, CKD, or gout.
- `negative`: background text, disease description, general encouragement, or uncertain evidence.
- `contextual`: recommendations depend on stage, medication, dialysis status, acute flare, pregnancy, age, or individualized dietitian assessment.
- `cross_language`: Chinese and English cards covering similar claims for bilingual robustness.
- `patient_education`: web/manual source with less formal wording.

## 8. Current Extractor Alignment

The dataset must explicitly test the current boundaries of the extraction code:

- Current `KnowledgeDocument.source_type` accepts only `guideline`, `paper`, `food_db`, and `manual`.
- Current `KnowledgeLoader` imports `.md` and `.txt` files.
- Current extraction prompt supports nutrition limits only for `energy_kcal`, `carbs_g`, `fat_g`, `sodium_mg`, and `sugar_g`.
- The baseline concept registry contains `hypertension`, `diabetes`, `hyperlipidemia`, and `weight_control`; CKD and gout can be tested either with a custom registry or as `suggested_concept` outputs.
- Sources with potassium, phosphorus, protein, purine, alcohol, and hydration recommendations are valuable because they reveal concept and metric gaps instead of being forced into wrong rule fields.

## 9. Seed Source Families

Use authoritative and traceable sources first:

Chinese guideline and policy sources:

- 国家卫生健康委《成人高血压食养指南（2023年版）》.
- 国家卫生健康委《成人糖尿病食养指南（2023年版）》.
- 国家卫生健康委《成人高脂血症食养指南（2023年版）》.
- 国家卫生健康委《成人肥胖食养指南（2024年版）》.
- 国家卫生健康委《成人高尿酸血症与痛风食养指南（2024年版）》.
- 国家卫生健康委《高血压等慢性病营养和运动指导原则（2024年版）》.
- 中国居民膳食指南（2022） and related Chinese Nutrition Society materials.

English guideline sources:

- WHO sodium guideline.
- WHO sugars guideline.
- WHO saturated fat and trans fat guideline.
- WHO carbohydrate guideline.
- ADA Standards of Care in Diabetes and diabetes nutrition consensus materials.
- KDIGO CKD guideline and KDOQI nutrition in CKD guideline.
- AHA dietary guidance for cardiovascular health.
- ACR gout guideline.
- NICE diabetes and obesity dietary guidance.

Paper/review sources:

- Diabetes nutrition consensus report.
- DASH-Sodium trial and related analyses.
- Mediterranean diet cardiovascular trial/review literature.
- CKD nutrition reviews and KDOQI executive summaries.
- Gout/hyperuricemia diet, purine, alcohol, and fructose reviews.

Web/manual sources:

- CDC diabetes meal planning.
- NIDDK diabetes, CKD, and weight management pages.
- Mayo Clinic gout diet and gout treatment nutrition pages.
- Cleveland Clinic renal diet pages.
- Chinese NHC interviews, Q&A pages, and public nutrition explainers.

## 10. Quality Gates

The dataset is acceptable when:

- `manifest.jsonl` has exactly 60 records.
- Language distribution is 30 Chinese and 30 English records.
- Source class distribution is 24 guidelines, 18 papers, and 18 manual/web records.
- All manifest paths exist and use `.md`.
- All source cards have `doc_id`, `source_url`, `source_type`, `language`, `publisher`, `year`, and evaluation labels.
- At least 20 records are `should_extract`.
- At least 12 records are `concept_gap`.
- At least 8 records are `negative`, `contextual`, or `conflict`.
- `KnowledgeLoader` can load the guideline, paper, and manual directories.
- A dataset validation test checks manifest integrity and gold rule schema.

## 11. Implementation Plan Preview

After this design is approved, implementation should proceed in three batches:

1. Create `manual/`, `datasets/rule_extraction_v1/`, README, manifest schema expectations, and a validation test.
2. Add the 60 Markdown source cards and `manifest.jsonl`.
3. Add `gold_rules.jsonl`, run loader and validation tests, then run a focused extractor smoke test on representative records.

The implementation should not change extraction logic unless validation reveals that the dataset cannot be loaded with the current interfaces.

## 12. Risks

- Copyright risk: avoid storing full guideline PDFs or full article text; use links, metadata, short excerpts, and summaries.
- Medical accuracy risk: gold rules are evaluation expectations, not approved clinical rules.
- Scope drift: do not add new disease logic during dataset construction unless separately approved.
- Concept mismatch: CKD and gout are expected to expose registry gaps; this is useful and should be labelled rather than hidden.
