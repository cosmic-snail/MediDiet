# DocRule-Agent Experiment Summary

- run id: dry-run
- dataset id: rule_extraction_v1
- model: fake
- prompt version: dry-run-v1
- timestamp: 2026-05-26T12:21:52.634066+00:00
- registry snapshot: research-snapshot-0324cf8926ac18e2

## Dataset Profile

- chunk rows: 6

## Lifecycle Benchmark Portfolio

- benchmarks: 12

## Comparator Arms

- C0: Clean synthetic chunk
- C1: Raw source card + current two-stage extractor
- C2: Extractable content + current two-stage extractor
- C3: Source notes plus extractable content + current two-stage extractor
- C4: One-shot JSON extractor
- C5: Two-stage extractor without cross-validation rejection
- C6: Two-stage extractor + judge/verifier observation
- C7: Repeated self-consistency aggregator
- C8: Manifest-free directory scan

## Observation Coverage

["O5", "O6", "O8"]

## Failure Taxonomy Counts

Dry-run observations preserve failure labels for later real-provider analysis.
