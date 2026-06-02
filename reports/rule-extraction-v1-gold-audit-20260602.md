# rule_extraction_v1 Gold Audit - 2026-06-02

## Scope

This audit reviews the 14 frozen rows in `knowledge/datasets/rule_extraction_v1/gold_evaluation_set.jsonl`.

The goal is to separate extractor failures from benchmark-quality issues. A gold row is treated as reliable only when the model input used by the experiment contains enough evidence for the expected structured fields. `C1` is `raw_card`, not a true raw webpage/PDF source; `C2` is `extractable_content`.

## Summary

The current gold set is useful for smoke testing, but it mixes several evidence levels:

- Directly supported source-card facts.
- Original-source facts summarized into the source card.
- Derived benchmark conversions that are not visible in the source card.
- LLM-generated umbrella concept codes that do not match product-style atomic concept registration.
- Contextual/negative examples where the current evaluator labels any non-empty extraction too coarsely.

This means current precision/recall/F1 should not be treated as a pure extractor-quality metric until the gold rows are cleaned or stratified by evidence level.

## Recommended Labels

- `keep`: source card and gold are aligned enough for current evaluation.
- `revise_gold`: gold asks for a field not directly supported by source-card evidence.
- `revise_schema_or_gold`: source supports the signal, but current schema/gold granularity is wrong.
- `review_negative`: current negative/contextual label is too coarse.

## Row-Level Audit

| doc_id | current behavior | audit label | rationale | recommendation |
|---|---|---|---|---|
| `en_guideline_who_sodium_2012` | rule | keep | Source card contains `2000 mg` sodium and `5 g` salt. WHO also directly supports less than 2000 mg/day sodium / less than 5 g/day salt. | Keep numeric gold. |
| `zh_guideline_hypertension_food_therapy_2023` | rule | keep | Source card contains about 5 g salt / 2000 mg sodium. NHC PDF has a seasoning exchange table using 2000 mg sodium / 5 g salt. | Keep numeric gold if this card is intended to test salt-to-sodium extraction. |
| `en_paper_dash_sodium_trial` | rule | keep | Source card supports lower sodium and DASH pattern reducing blood pressure; no numeric limit in gold. | Keep. |
| `en_manual_heart_org_sodium_reduction` | rule | keep | Source card supports sodium reduction for heart health and blood pressure; no numeric limit in gold. | Keep, but consider whether `condition=hypertension` is too narrow versus `cardiovascular_risk`. |
| `zh_manual_health_china_salt_reduction` | rule | keep | Source card supports salt reduction as public-health / blood-pressure signal; no numeric limit in gold. | Keep, but consider broader condition/context handling. |
| `zh_manual_health_china_sugar_reduction` | rule | borderline | Source card supports sugar/sweetened-beverage reduction, but diabetes binding is inferred from chronic-disease context rather than explicit in card text. | Consider changing to contextual rule or requiring `condition=chronic_disease_prevention` if available. |
| `en_guideline_who_sugars_2015` | rule | revise_gold | Source card supports percentage-of-energy free-sugar guidance and obesity/dental-caries risk, but not `sugar_g=50`. WHO source states `<10% total energy`; `50 g` is a derived 2000 kcal conversion. | Remove `sugar_g=50` from gold, or add schema support for percent-of-energy limits. Do not write the 50 g conversion into source card. |
| `en_manual_medlineplus_low_sodium_diet` | rule | revise_gold | Source card supports low-salt diet for blood pressure/heart/kidney contexts, but not a `2000 mg` daily sodium threshold. MedlinePlus page mentions salt/sodium concepts but current card does not expose a daily numeric threshold. | Remove numeric `sodium_mg=2000` from this gold row unless the source card is updated from a directly supported source statement. |
| `en_manual_niddk_ckd_eating_right` | suggested_concept | revise_schema_or_gold | Source supports sodium, protein, potassium, and phosphorus. Gold expects umbrella `potassium_phosphorus_management`, while model/product registry tends to emit atomic concepts such as `low_potassium`, `low_phosphorus`, `controlled_protein`. | Replace umbrella gold with atomic expected concepts or introduce explicit alias groups. |
| `en_manual_mayo_gout_diet` | suggested_concept | revise_schema_or_gold | Source supports purines, alcohol, fructose/sweetened drinks, and healthy diet patterns. Gold expects one umbrella `purine_alcohol_fructose_hydration`; model emits atomic concepts. | Replace umbrella gold with atomic concepts and alias groups. |
| `zh_guideline_gout_food_therapy_2024` | suggested_concept | revise_schema_or_gold | Source card supports purine, alcohol, and hydration concepts. Gold expects umbrella `purine_and_alcohol_limits`, while model emits atomic concepts. | Replace umbrella gold with atomic concepts and alias groups. |
| `en_manual_niddk_weight_management` | negative | keep | Source card explicitly says no universal calorie prescription. | Keep as negative. |
| `zh_manual_chinese_nutrition_society_dietary_guidelines_public` | negative | keep | Source card is general public dietary guidance, not disease-specific. | Keep as negative. |
| `en_paper_mediterranean_diet_cardiovascular_prevention` | negative | review_negative | Source is a dietary-pattern trial, not a single nutrient-limit source. However, it may support contextual `dietary_pattern` or `cardiovascular_risk` extraction, not necessarily pure negative. | Keep out of rule F1 or mark as contextual/dietary_pattern. Also fix evaluator label: non-empty negative extraction is not always `unexpected_numeric_limit`. |

## Main Findings

### 1. Source-card sparsity is not the whole story

Historical C1 vs C2 results showed C1 `raw_card` only modestly improved over C2 `extractable_content` (`F1 0.700` vs `0.600`). That does not prove true raw webpages/PDFs are unhelpful, because C1 is still only the full source card. If the source card omitted numeric thresholds, C1 also omitted them.

### 2. Some numeric gold rows are over-specified

`en_guideline_who_sugars_2015` and `en_manual_medlineplus_low_sodium_diet` currently ask for numeric values that are not directly visible in the source-card input. These should not count as extractor recall failures under the current input strategy.

### 3. Suggested-concept gold granularity does not match product registry needs

The current gold set uses umbrella concept ids for CKD and gout. Product-facing concept registration is likely better served by atomic concepts plus alias/group matching. The current evaluator therefore counts valid atomic concept discovery as misses.

### 4. Negative/contextual rows need sharper labels

`en_paper_mediterranean_diet_cardiovascular_prevention` is not a nutrient-limit rule, but it is not necessarily "no signal". A contextual/dietary-pattern category would be more informative than strict negative.

## Proposed Next Steps

1. Add an `evidence_level` field to each gold row:
   - `source_card_direct`
   - `original_source_direct`
   - `derived_conversion`
   - `schema_gap`
   - `contextual_negative`

2. Recompute headline P/R/F1 only on clean rows: `source_card_direct`, `original_source_direct`, and trusted `contextual_negative` rows with `audit_status=keep`.

3. Move `derived_conversion` rows out of ordinary numeric-limit recall until schema explicitly supports conversion formulas.

4. Replace umbrella suggested-concept gold with atomic expected concepts plus alias groups.

5. Fix evaluator failure labels for negative rows:
   - non-empty numeric limit on negative source -> `unexpected_numeric_limit`
   - non-empty contextual/pattern rule -> `unexpected_contextual_rule`
   - non-empty suggested concepts -> `unexpected_suggested_concept`

6. After gold cleanup, rerun C1/C2 using checkpoint/resume and report both:
   - strict score on clean gold rows
   - exploratory score on schema-gap/contextual rows

## External Source Notes

- WHO sodium guidance directly supports less than 2000 mg/day sodium, equivalent to less than 5 g/day salt.
- WHO sugars guidance directly supports less than 10% total energy from free sugars, not a universal fixed gram value.
- NHC hypertension food-therapy PDF includes a seasoning exchange table using 2000 mg sodium / 5 g salt.
- NIDDK CKD source supports potassium, protein, sodium, and phosphorus as individualized diet concepts.
- Mayo gout diet source supports purine, alcohol, and high-fructose/sweetened-food concepts.
