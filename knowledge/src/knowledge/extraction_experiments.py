from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    name: str
    dataset_slice: str
    comparator_arms: tuple[str, ...]
    default_repeats: int
    primary_metrics: tuple[str, ...]
    required_observation_points: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkExperimentSpec:
    experiment_id: str
    name: str
    lifecycle_layer: str
    benchmark_ids: tuple[str, ...]
    comparator_arms: tuple[str, ...]
    primary_metrics: tuple[str, ...]
    bridge_outputs: tuple[str, ...]


COMPARATOR_ARMS: dict[str, str] = {
    "C0": "Clean synthetic chunk",
    "C1": "Raw source card + current two-stage extractor",
    "C2": "Extractable content + current two-stage extractor",
    "C3": "Source notes plus extractable content + current two-stage extractor",
    "C4": "One-shot JSON extractor",
    "C5": "Two-stage extractor without cross-validation rejection",
    "C6": "Two-stage extractor + judge/verifier observation",
    "C7": "Repeated self-consistency aggregator",
    "C8": "Manifest-free directory scan",
}

OBSERVATION_POINTS: dict[str, str] = {
    "O1": "Manifest ingestion",
    "O2": "Source hashing",
    "O3": "Content selection",
    "O4": "Chunking",
    "O5": "Prompt assembly",
    "O6": "Provider call",
    "O7": "Raw response",
    "O8": "Structured parse",
    "O9": "Rule normalization",
    "O10": "Field evaluation",
    "O11": "Stability",
    "O12": "Registry governance",
    "O13": "Downstream effect",
}

BENCHMARK_EXPERIMENT_MATRIX: tuple[BenchmarkExperimentSpec, ...] = (
    BenchmarkExperimentSpec("B1", "Guideline parsing", "L0_raw_guideline_corpus", ("epfl_guidelines",), ("C1", "C2", "C8"), ("parse_success_rate", "section_coverage", "candidate_rule_density"), ("GuidelineDocument", "GuidelineSection", "RecommendationCandidate")),
    BenchmarkExperimentSpec("B2", "Rule-backed QA", "L1_guideline_qa_and_L5_rag_comparison", ("cpgqa", "ragcare_qa"), ("C2", "C4", "C6", "C7"), ("qa_accuracy", "citation_quality", "answer_stability"), ("GuidelineQuestion", "AnswerEvidence", "RuleBackedAnswer", "CitationTrace")),
    BenchmarkExperimentSpec("B3", "Executable structure", "L2_executable_guideline_structure", ("meddm", "text2mdt"), ("C2", "C4", "C5", "C6"), ("node_edge_f1", "triplet_f1", "execution_path_accuracy"), ("DecisionNode", "ActionNode", "DecisionEdge", "RuleCandidateDraft")),
    BenchmarkExperimentSpec("B4", "Conflict governance", "L3_conflict_governance", ("sglt2i_conflicts",), ("C2", "C6"), ("conflict_precision", "conflict_recall", "conflict_type_accuracy"), ("ConflictPair", "ConflictType", "ArbitrationTrace")),
    BenchmarkExperimentSpec("B5", "Guideline adherence", "L4_guideline_adherence_safety", ("amega_llm", "medguide"), ("C2", "C4", "C6", "C7"), ("guideline_adherence_score", "safety_error_rate", "citation_completeness"), ("GuidelineAdherenceCase", "SafetyError", "CitationTrace")),
    BenchmarkExperimentSpec("B6", "Version update", "L6_version_evidence_update", ("high_precision_ir_updates", "q2crbench3"), ("C2", "C6"), ("update_detection_recall", "update_detection_precision", "rule_diff_accuracy"), ("VersionedRecommendation", "EvidenceLink", "RuleDiffGold")),
    BenchmarkExperimentSpec("B7", "Auxiliary IE", "L8_auxiliary_ie", ("clinical_ie_aux",), ("C4", "C6"), ("entity_f1", "relation_f1", "event_f1"), ("ConditionCandidate", "RelationCandidate", "EvidenceUnit")),
)

EXPERIMENT_MATRIX: tuple[ExperimentSpec, ...] = (
    ExperimentSpec("E1", "Chunking ablation", "14 frozen gold records", ("C1", "C2", "C3"), 3, ("numeric_limit_recall", "chunk_contamination_rate", "parse_success_rate"), ("O1", "O2", "O3", "O4", "O5", "O6", "O7", "O8", "O10")),
    ExperimentSpec("E2", "Architecture ablation", "14 frozen gold records", ("C2", "C4", "C5", "C6"), 3, ("field_level_f1", "unsupported_concept_rate", "verifier_disagreement_rate"), ("O3", "O5", "O6", "O7", "O8", "O9", "O10")),
    ExperimentSpec("E3", "Stability study", "5 high-value gold/challenge records", ("C1", "C2", "C7"), 10, ("field_stability", "pairwise_similarity", "empty_output_rate", "retry_rate"), ("O5", "O6", "O7", "O8", "O9", "O10", "O11")),
    ExperimentSpec("E4", "Clean-vs-real chunk gap", "matched clean chunks and generated chunks", ("C0", "C1", "C2"), 5, ("performance_drop", "numeric_limit_recall_delta", "rule_count_delta"), ("O3", "O4", "O5", "O8", "O10", "O11")),
    ExperimentSpec("E5", "Source-update simulation", "3 edited source-card variants", ("C2",), 1, ("stale_detection_accuracy", "rule_diff_correctness"), ("O1", "O2", "O9", "O12")),
    ExperimentSpec("E6", "Conflict governance", "conflict challenge records", ("C2", "C6"), 3, ("conflict_grouping_accuracy", "authority_traceability"), ("O1", "O2", "O8", "O9", "O10", "O12")),
    ExperimentSpec("E7", "Downstream citation effect", "stable extracted candidates", ("C2", "C7"), 1, ("recommendation_delta", "citation_completeness"), ("O9", "O10", "O12", "O13")),
)


def get_benchmark_experiment(experiment_id: str) -> BenchmarkExperimentSpec:
    for experiment in BENCHMARK_EXPERIMENT_MATRIX:
        if experiment.experiment_id == experiment_id:
            return experiment
    raise KeyError(f"Unknown benchmark experiment: {experiment_id}")


def get_experiment(experiment_id: str) -> ExperimentSpec:
    for experiment in EXPERIMENT_MATRIX:
        if experiment.experiment_id == experiment_id:
            return experiment
    raise KeyError(f"Unknown extraction experiment: {experiment_id}")
