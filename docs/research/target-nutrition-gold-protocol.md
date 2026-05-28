# Target Nutrition Rule Gold Protocol

## Scope

Build a small, high-quality rule-level gold set for nutrition, chronic disease, and dialysis where public benchmarks do not provide structured rule gold.

## Source Families

- KDOQI Clinical Practice Guideline for Nutrition in CKD.
- KDIGO CKD guideline nutrition and metabolic management sections.
- ADA Standards of Care nutrition and weight-management sections.
- Dialysis nutrition guidance from renal and nutrition societies.

## Target Size

The first complete research release targets 100-200 rule-level gold records after the extraction and evaluation protocol stabilizes.

## Required Gold Fields

- source document id, URL, guideline version, section title, and evidence quote.
- condition and patient subgroup.
- lab or clinical qualifiers where required.
- recommended intake, restriction, contraindication, or warning.
- nutrient metric, threshold, unit, scope, and time window when numeric.
- evidence level and recommendation strength when stated.
- conflict group id when another source gives a competing recommendation.

## Split Policy

- development split: prompt and schema iteration.
- frozen evaluation split: final metrics only.
- conflict split: conflict detection and arbitration.
- downstream case split: synthetic patient profiles derived from gold rules.

## Boundary

The gold set is a research evaluation artifact. It is not a clinical approval process and does not publish patient-facing rules without separate review.
