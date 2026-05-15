# Hospital Diet Agent Recommendation Engine Design

Date: 2026-05-15

## Purpose

MediDiet will first build a recommendation engine for a hospital diet agent. The engine recommends the patient's next meal while considering nutrition guidelines, chronic disease constraints, allergies and contraindications, explicit taste preferences, today's estimated intake, and candidate meals from external menus such as food delivery platforms or hospital canteens.

The first version focuses on the recommendation engine rather than a full mini-program, food-photo recognition system, external delivery ordering flow, or hospital information system integration. Those surfaces are treated as upstream or downstream interfaces.

## MVP Scope

### In Scope

- Adult chronic disease patients in outpatient or home settings.
- Conditions covered by the first rule baseline:
  - Hypertension.
  - Diabetes.
  - Hyperlipidemia.
  - Obesity or weight-control goals.
- Allergy and contraindication hard exclusions.
- Recommendation for the next meal, while referencing today's already consumed food.
- Two-layer recommendation output:
  - First produce a nutrition-compliant meal plan.
  - Then match that plan against concrete menu items from delivery platforms, hospital canteens, or curated menus.
- Patient-visible recommendations for normal-risk cases.
- Dietitian or clinician confirmation for high-risk or low-confidence cases.
- Dual explanations:
  - Short, patient-friendly explanation.
  - Detailed dietitian-facing trace with rules, data sources, confidence, scores, and risks.

### Out of Scope for MVP

- Pediatric, pregnancy, kidney disease, gout, cancer, post-operative, swallowing difficulty, malnutrition, or other complex clinical nutrition scenarios.
- Medication adjustment or medical diagnosis.
- Full HIS/EMR integration.
- Real delivery checkout and order placement.
- Fully precise clinical nutrition accounting from food photos.
- Long-term meal plans across weeks or months.

Patients outside the default adult chronic disease scope should be rejected for automatic recommendation or routed to human confirmation. Future hospital configuration can expand or restrict the applicable population.

## Product Safety Boundary

The engine is not an autonomous dietitian. It is a safety-gated recommendation system.

Normal-risk cases may receive automatic patient-facing recommendations. High-risk or uncertain cases must be routed to a dietitian or clinician. High-risk triggers include:

- Allergy or explicit contraindication match.
- Serious conflict with chronic disease rules.
- Patient profile missing key risk information.
- Key patient-entered risk fields not confirmed.
- Food-photo recognition or intake estimation confidence is low.
- Menu item nutrition data is missing, conflicting, or low-confidence.
- No candidate meal satisfies hard constraints.
- Patient belongs to an out-of-scope or complex clinical group.

The engine should support four outcomes:

- Automatic recommendation.
- Low-risk downgraded recommendation with clear caveats.
- Refusal to recommend with a reason and next-step guidance.
- Human confirmation request.

## Clinical Reference Governance

This design does not define final clinical nutrient thresholds. Implementation must convert reviewed, versioned clinical and dietary references into machine-readable rules, then have those rules approved by qualified clinicians or dietitians before patient-facing use.

Initial reference candidates for the first rule pack:

- Chinese Nutrition Society, Chinese Dietary Guidelines 2022.
- National Health Commission, Adult Hypertension Dietary Guidance 2023.
- National Health Commission, Adult Diabetes Dietary Guidance 2023.
- National Health Commission, Adult Hyperlipidemia Dietary Guidance 2023.
- National Health Commission, Adult Obesity Dietary Guidance 2024.
- Chinese Diabetes Society, Chinese Diabetes Prevention and Treatment Guideline 2024, for clinical context and exclusion criteria.
- China Hypertension Guideline Revision Committee and related societies, Chinese Hypertension Prevention and Treatment Guideline 2024, for clinical context and exclusion criteria.
- Chinese Joint Committee for Lipid Management, Chinese Guideline for Lipid Management 2023, for clinical context and exclusion criteria.

The product rule pack should store:

- Source title and URL or publication citation.
- Source version and publication date.
- Rule author and reviewer.
- Effective date.
- Applicable population.
- Contraindication severity.
- Whether the rule is a hard exclusion, soft target, or ranking feature.
- Change history.

Hospital-specific rules, when available, override the built-in baseline only through this versioned rule system.

## Architecture

Use a rules-first architecture with LLM assistance.

### Inputs

- Patient profile:
  - Demographics needed for nutrition targets.
  - Height, weight, BMI or weight-control goal.
  - Chronic disease labels.
  - Allergies and contraindications.
  - Explicit taste preferences and dislikes.
  - Price, distance, and convenience preferences.
  - Data source, confirmation status, and update time.
- Today's intake:
  - Food item labels.
  - Estimated portion size.
  - Estimated energy, carbohydrates, protein, fat, sodium, sugar, and fiber.
  - Recognition source and confidence.
- Candidate menu:
  - Menu item name, category, ingredients, taste tags.
  - Nutrition label or estimated nutrition.
  - Price, distance, availability, merchant reliability.
  - Nutrition data source and confidence.
- Rule baseline:
  - Disease nutrition constraints and targets.
  - Applicable population.
  - Evidence source.
  - Rule version.
  - Future hospital override layer.

### Core Components

- Safety gate:
  - Checks applicable population, allergies, contraindications, disease hard constraints, patient data completeness, intake confidence, and menu data confidence.
- Daily nutrition state calculator:
  - Estimates what the patient has already consumed today.
  - Computes remaining or preferred targets for the next meal.
- Meal plan generator:
  - Produces a nutrition-compliant next-meal pattern before binding to concrete menu items.
  - Example: low-sodium protein dish, controlled staple portion, green vegetables, no sugary drink.
- Menu matcher:
  - Hard-excludes unsafe or incompatible items.
  - Scores remaining items against nutrition fit, safety margin, taste preference, price, distance, and merchant/data reliability.
- Explanation generator:
  - Uses LLMs to convert rule hits and nutrition facts into clear patient and dietitian explanations.
  - Must not create new medical claims not supported by rules or data.
- Recommendation auditor:
  - Stores every recommendation decision, rule hit, score, confidence value, LLM output summary, risk level, and human review state.

### LLM Boundary

The LLM may help with:

- Food-photo recognition supplementation and normalization.
- Menu item interpretation when structured data is incomplete.
- Patient Q&A within safe nutrition education boundaries.
- Explanation generation for patients and dietitians.

The LLM must not:

- Override hard safety rules.
- Invent clinical evidence.
- Provide diagnosis or medication adjustment.
- Recommend food that failed safety checks.
- Produce patient-facing output without final rule-layer safety validation.

## Data Model

### PatientProfile

Represents the patient context used by the engine.

Key fields:

- Age group, sex if needed by nutrition targets.
- Height, weight, BMI, weight goal.
- Chronic conditions: hypertension, diabetes, hyperlipidemia, obesity or weight-control.
- Allergens and hard contraindications.
- Explicit dislikes and taste preferences.
- Price, distance, and convenience preferences.
- Data source: patient self-report, clinician entry, or future HIS/EMR import.
- Confirmation status for key risk fields.
- Updated timestamp.

First version supports patient self-report with confirmation prompts for critical risk fields. Future versions can support clinician entry and HIS/EMR import.

### ConditionRule

Represents guideline baseline rules and future hospital overrides.

Key fields:

- Condition.
- Applicable population.
- Hard exclusions.
- Soft nutrition targets.
- Nutrient thresholds or preferred ranges.
- Evidence source.
- Rule severity.
- Rule version.
- Override source, when hospital-specific rules become available.

First version uses built-in guideline baselines. The model must be ready for later hospital-specific rule overrides, but those overrides are not required for MVP.

### IntakeRecord

Represents today's already consumed food.

Key fields:

- Meal time.
- Food label.
- Estimated portion.
- Energy, carbohydrate, protein, fat, sodium, sugar, and fiber estimates.
- Recognition source.
- Confidence.
- Manual correction state.

The MVP uses nutritional estimation with confidence. Low-confidence records trigger human confirmation or conservative recommendation. Later versions can move toward stricter clinical nutrition accounting.

### MenuItem

Represents one candidate dish, meal, or set meal.

Key fields:

- Menu item ID and merchant ID.
- Name, category, ingredients, and taste tags.
- Nutrition data:
  - Energy.
  - Carbohydrate.
  - Protein.
  - Fat.
  - Sodium.
  - Sugar.
  - Fiber, when available.
- Nutrition source:
  - Platform or merchant nutrition label.
  - System estimate from dish name, image, and ingredient database.
  - Human-maintained nutrition data.
- Data confidence.
- Price, distance, availability.
- Merchant reliability.

Nutrition data priority:

1. Platform or merchant-provided nutrition label.
2. Human-maintained curated nutrition data.
3. System estimate.

Low-confidence or missing nutrition data can reduce ranking confidence or trigger human confirmation.

### RecommendationTrace

Represents the audit record for a recommendation request.

Key fields:

- Request context summary.
- Patient profile version.
- Intake records used.
- Candidate menu set.
- Rule version.
- Rule hits and exclusions.
- Nutrition state and next-meal target.
- Candidate scores.
- LLM input/output summary.
- Risk level.
- Outcome: recommendation, downgraded recommendation, refusal, or human review.
- Human review status and reviewer edits, when applicable.

Every recommendation should be reproducible and explainable from this trace.

## Recommendation Flow

1. Receive recommendation request:
   - Patient profile.
   - Today's intake.
   - Candidate menu items.
   - Meal time.
2. Run safety and eligibility gate:
   - Check in-scope population.
   - Check allergies and contraindications.
   - Check chronic disease hard constraints.
   - Check key patient profile completeness and confirmation.
   - Check intake and menu data confidence.
3. Estimate today's nutrition state:
   - Aggregate energy, carbohydrate, protein, fat, sodium, sugar, and fiber from today's intake records.
   - Preserve confidence and uncertainty.
4. Compute next-meal target:
   - Adjust based on chronic disease rules and today's intake.
   - Example: if sodium intake is already high, prefer a lower-sodium dinner.
5. Generate meal plan:
   - Produce a nutrition-compliant meal pattern before selecting concrete dishes.
6. Match concrete menu items:
   - Exclude unsafe items.
   - Score compliant candidates.
   - Build one or more recommended meal combinations.
7. Apply outcome policy:
   - Recommend automatically if safe and reliable.
   - Downgrade to low-risk recommendation if imperfect but acceptable.
   - Refuse if hard constraints cannot be satisfied.
   - Route to human confirmation if risk or uncertainty is high.
8. Generate explanations:
   - Patient-friendly explanation.
   - Dietitian-facing audit explanation.
9. Final safety validation:
   - Validate generated explanation and recommendation against rules.
10. Store RecommendationTrace.

## Ranking Strategy

Safety is a hard threshold. Allergies, contraindications, and severe disease conflicts are not ranking factors; they exclude candidates.

For remaining candidates, use configurable weighted ranking. Default MVP weights:

- Nutrition fit: 45%.
- Safety margin: 20%.
- Taste preference: 15%.
- Price and distance: 10%.
- Merchant and nutrition-data reliability: 10%.

Future versions can allow hospitals or product operators to configure weights.

## Human Review

Human review is required when:

- A hard safety conflict is detected.
- Information is incomplete or low-confidence.
- Patient group is out of MVP scope.
- Menu nutrition data is insufficient for a safe automatic decision.
- No candidate meal satisfies hard constraints.

Dietitian or clinician actions:

- Confirm recommendation.
- Modify meal plan.
- Select alternative dishes.
- Add or adjust contraindications.
- Correct patient profile.
- Correct intake record.
- Annotate menu nutrition data.
- Reject recommendation and provide next-step guidance.

Human review outcomes should not automatically update production rules. They should first become quality-control samples, rule candidates, menu reliability corrections, or preference signals.

## Explanation Design

### Patient Explanation

Patient-facing explanations should be short, concrete, and non-alarming.

They should answer:

- Why is this meal suitable?
- What should the patient pay attention to today?
- Which common alternatives are not recommended and why?
- Whether the recommendation is automatic, conservative, or pending human review.

Example:

> This meal is lower in sodium, has a moderate staple portion, and provides enough protein. Because your lunch was estimated to be high in sodium, avoid drinking the soup base or adding extra sauce tonight.

### Dietitian Explanation

Dietitian-facing explanations should include:

- Risk level.
- Rules hit.
- Data sources and confidence.
- Nutrition estimates.
- Today's intake summary.
- Candidate filtering reasons.
- Score breakdown.
- LLM output summary.
- Audit trace link or ID.

## Error Handling and Degradation

The engine should degrade safely:

- If a dish violates a hard rule, exclude it.
- If no dish satisfies hard rules, refuse recommendation and explain why.
- If only imperfect but low-risk options exist, show the best low-risk candidate with caveats.
- If patient or menu data is unreliable, route to human confirmation.
- If LLM output fails safety validation, regenerate or fall back to rule-only explanation.
- If external menu APIs fail, return a structured unavailable state rather than hallucinating menu items.

## API Boundary

The recommendation engine should expose a clear API boundary so the mini-program, photo-recognition module, delivery-platform connector, and dietitian review console can evolve independently.

Primary request:

```json
{
  "patientProfile": {},
  "todayIntake": [],
  "candidateMenuItems": [],
  "mealTime": "dinner",
  "ruleVersion": "baseline-2026-05-15"
}
```

Primary response:

```json
{
  "outcome": "recommended | downgraded | refused | human_review_required",
  "mealPlan": {},
  "recommendedItems": [],
  "patientExplanation": "",
  "clinicianExplanation": {},
  "riskLevel": "low | medium | high",
  "traceId": ""
}
```

## Testing Strategy

MVP verification should cover:

- Safety:
  - Allergy hard exclusion.
  - Disease hard constraints.
  - Out-of-scope population routing.
  - No-compliant-meal refusal.
- Nutrition:
  - Today's intake affects next-meal recommendation.
  - Sodium, sugar, carbohydrate, fat, and energy targets behave as expected.
  - Low-risk downgraded recommendations are clearly labeled.
- Data quality:
  - Low-confidence food-photo estimates trigger review.
  - Missing menu nutrition data triggers review or lower confidence.
  - Patient critical risk fields require confirmation.
- Explanation:
  - Patient explanation is understandable and does not overclaim.
  - Dietitian explanation includes rule hits, sources, confidence, and scores.
  - RecommendationTrace can replay the decision.
- LLM safety:
  - LLM cannot override rules.
  - LLM does not invent evidence.
  - LLM does not provide diagnosis or medication advice.
  - Patient-facing output passes final safety validation.
- Ranking:
  - Hard constraints always beat preference.
  - Weight configuration changes ranking only among safe candidates.

## Roadmap

### Phase 1: Recommendation Engine Core

- Recommendation API.
- Rule baseline for adult chronic disease and allergies.
- Patient profile, intake, menu, and trace models.
- Simulated intake and menu data.
- Rule-based filtering, scoring, explanation, and audit traces.

### Phase 2: Data Integrations

- Food-photo recognition interface.
- Delivery or canteen menu connector interface.
- Nutrition estimation with confidence.
- Human review trigger loop.

### Phase 3: Product Experience

- Mini-program patient experience.
- Dietitian review console.
- Explicit preference collection.
- Preference learning from choices, skips, repeat orders, and ratings.
- Hospital-specific rule configuration.

### Phase 4: Hospital Integration and Evaluation

- HIS/EMR integration.
- Long-term diet planning.
- Quality-control dashboards.
- Real-world safety, adherence, and satisfaction evaluation.

## Success Criteria

The MVP succeeds if it can:

- Avoid recommending allergy or contraindicated meals.
- Adjust next-meal recommendation based on today's estimated intake.
- Explain recommendations clearly to patients.
- Provide dietitians with a complete evidence chain.
- Stop or escalate when information is unsafe or uncertain.
- Preserve a reproducible audit trace for every recommendation.

## Reference URLs Reviewed During Design

- Chinese Nutrition Society, Chinese Dietary Guidelines 2022 release: https://dg.cnsoc.org/article/04/glVJd6DRRCqm-hYzWlEVNQ.html
- Chinese Nutrition Society, Chinese Dietary Guidelines 2022 core principles: https://dg.cnsoc.org/article/04/J4-AsD_DR3OLQMnHG0-jZA.html
- National Health Commission, adult chronic disease dietary guidance notice: https://www.nhc.gov.cn/sps/c100088/202301/f01895a06c5349ef999f25da833c166d.shtml
- National Health Commission, Adult Hypertension Dietary Guidance 2023 PDF: https://www.nhc.gov.cn/sps/c100088/202301/f01895a06c5349ef999f25da833c166d/files/1732844468193_68545.pdf
- National Health Commission, Adult Diabetes Dietary Guidance 2023 PDF: https://www.nhc.gov.cn/sps/c100088/202301/f01895a06c5349ef999f25da833c166d/files/1732844468278_20318.pdf
- National Health Commission, Adult Hyperlipidemia Dietary Guidance 2023 PDF: https://www.nhc.gov.cn/cms-search/downFiles/cd496bd490bc4564beeb009c1612eb11.pdf
- National Health Commission, Adult Obesity Dietary Guidance 2024 compilation note PDF: https://www.nhc.gov.cn/sps/c100088/202312/3fbdf286857a4235be5749ca7a7b2ac9/files/1732845040999_78396.pdf
- Chinese Diabetes Society guideline page: https://diab.cma.org.cn/cn/zhinangongshi.aspx
- Chinese Guideline for Lipid Management 2023: https://rs.yiigle.com/CN2021/1449955.htm
- Chinese Hypertension Prevention and Treatment Guideline 2024 article page: https://cjournal.hep.com.cn/1673-7245/CN/1160171857581368285
