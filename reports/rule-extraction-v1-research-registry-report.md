# Rule Extraction V1 Research Registry Report

- snapshot id: research-snapshot-0324cf8926ac18e2
- snapshot type: research_only
- candidates: 126

## Stable Rules

Dry-run stable rule identities are listed in the machine JSONL snapshot.

## Unstable Rules

{
  "condition_presence": {
    "diabetes": 0.5,
    "hypertension": 0.5
  },
  "empty_output_rate": 0.0,
  "failure_counts": {},
  "hard_exclusion_presence": {},
  "nutrition_limit_presence": {
    "sodium_mg|daily|2000|24": 0.5,
    "sugar_g|daily|25|24": 0.5
  },
  "pairwise_canonical_rule_set_similarity": 0.4444444444444444,
  "parse_failure_rate": 0.0,
  "preferred_tag_presence": {
    "low_sodium": 0.5,
    "low_sugar": 0.5
  },
  "retry_count_distribution": {
    "0": 10
  },
  "run_count": 10
}

## Stale Candidates

{
  "added_doc_ids": [],
  "changed_doc_ids": [],
  "removed_doc_ids": [],
  "stale_rule_identities": [],
  "unchanged_doc_ids": [
    "en_guideline_who_sodium_2012",
    "en_manual_diabetes_sugar_case"
  ]
}

## Conflicts

{
  "conflicts": []
}
