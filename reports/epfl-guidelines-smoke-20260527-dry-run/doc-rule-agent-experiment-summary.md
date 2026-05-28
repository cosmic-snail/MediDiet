# DocRule-Agent Experiment Summary

- run id: dry-run
- dataset id: rule_extraction_epfl_guidelines_smoke
- model: fake
- prompt version: dry-run-v1
- timestamp: 2026-05-27T09:21:26.573283+00:00
- registry snapshot: research-snapshot-4b92a3e55f81b6ca

## Dataset Profile

- chunk rows: 56

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
