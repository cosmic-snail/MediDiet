# Lifecycle Benchmark Portfolio For DocRule-Agent

## Rationale

No public dataset covers the full DocRule-Agent lifecycle. The evaluation composes lifecycle-specific benchmarks and then transfers to a self-built nutrition, chronic-disease, and dialysis rule gold set.

## Lifecycle Layers

- L0 Raw guideline corpus: epfl-llm / Guidelines.
- L1 Guideline QA: cpgQA.
- L2 Executable structure: MedDM and Text2MDT.
- L3 Conflict governance: SGLT2i multidisciplinary guideline conflict dataset.
- L4 Guideline adherence and safety: AMEGA-LLM and MedGUIDE.
- L5 RAG comparison: RAGCare-QA.
- L6 Version and evidence update: High-Precision IR and Q2CRBench-3.
- L7 Target transfer: self-built KDOQI / KDIGO / ADA / dialysis nutrition rule gold.
- L8 Auxiliary IE: clinical-ie, CBLUE, and MedBench.

## Bridge To DocRule-Agent

Each benchmark maps to a lifecycle-specific intermediate representation. Public benchmarks are not forced directly into `ExtractedConditionRule`.

## Transfer Claim

Public datasets establish external validity for individual lifecycle skills. The self-built target gold set is the core evidence for nutrition, chronic disease, and dialysis rule registration.
