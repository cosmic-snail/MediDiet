# DocRule-Agent Research Protocol

## Research Questions

RQ1 document-to-rule fidelity; RQ2 chunking sensitivity; RQ3 extraction architecture effect; RQ4 LLM stability; RQ5 observation value; RQ6 source update propagation; RQ7 registry governance; RQ8 benchmark-to-target transfer.

## Hypotheses H1-H6

H1 extractable-content-only input improves numeric-limit recall. H2 two-stage extraction improves precision but can reduce recall. H3 self-consistency improves confidence estimation more than raw accuracy. H4 clean chunks overestimate end-to-end performance. H5 source authority and version metadata are needed for conflict governance. H6 rich observation logging explains failures hidden by pass/fail tests.

## Lifecycle Benchmark Portfolio L0-L8

L0 epfl-llm / Guidelines; L1 cpgQA; L2 MedDM and Text2MDT; L3 SGLT2i conflicts; L4 AMEGA-LLM and MedGUIDE; L5 RAGCare-QA; L6 High-Precision IR and Q2CRBench-3; L7 target nutrition gold; L8 clinical-ie, CBLUE, and MedBench.

## Comparator Arms C0-C8

C0 clean synthetic chunk; C1 raw source card current two-stage extractor; C2 extractable content current two-stage extractor; C3 source notes plus extractable content; C4 one-shot JSON extractor; C5 two-stage without rejection; C6 judge/verifier observation; C7 repeated self-consistency aggregator; C8 manifest-free directory scan.

## Observation Points O1-O13

O1 manifest ingestion; O2 source hashing; O3 content selection; O4 chunking; O5 prompt assembly; O6 provider call; O7 raw response; O8 structured parse; O9 rule normalization; O10 field evaluation; O11 stability; O12 registry governance; O13 downstream effect.

## Benchmark Experiment Matrix B1-B7

B1 guideline parsing; B2 rule-backed QA; B3 executable structure; B4 conflict governance; B5 guideline adherence; B6 version update; B7 auxiliary IE.

## Experiment Matrix E1-E7

E1 chunking ablation; E2 architecture ablation; E3 stability study; E4 clean-vs-real chunk gap; E5 source-update simulation; E6 conflict governance; E7 downstream citation effect.

## Target Nutrition Gold Transfer Protocol

Use KDOQI, KDIGO, ADA, and dialysis nutrition source families. Build 100-200 rule-level gold records after the protocol stabilizes, with frozen evaluation, challenge, conflict, and downstream case splits.

## Dataset And Label Boundaries

- Weak expectation: generated automatically and used for exploratory scoring.
- Frozen evaluation record: selected before experiments and never mutated by a run.
- Challenge record: retained for failure taxonomy and schema-gap analysis.
- Observation: append-only output from an extraction run.
- Reviewed clinical rule: outside this research loop and still requires explicit approval.

## Primary And Secondary Metrics

Primary metrics include field-level precision, recall, F1, numeric-limit exact match, numeric tolerance match, parse success, stability, conflict accuracy, and citation completeness. Secondary metrics include latency, retry count, empty-output rate, chunk contamination, and unsupported concept clusters.

## Failure Policy

Provider errors, empty outputs, invalid JSON, missing numeric limits, unsupported concepts, and instability are recorded as observations. Research runs do not hide failures through silent retries.

## Reproducibility Contract

Every report records dataset id, run id, arm id, model, prompt version, source hashes, input hashes, observation ids, and timestamp. Dry-run reports are deterministic and require no network calls.
