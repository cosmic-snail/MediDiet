from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicBenchmarkSpec:
    benchmark_id: str
    name: str
    lifecycle_layer: str
    homepage: str
    access: str
    required_for_ci: bool
    evaluation_role: str
    calibration_tasks: tuple[str, ...]
    ground_truth_type: str
    primary_metrics: tuple[str, ...]
    bridge_outputs: tuple[str, ...]
    transfer_use: str


BENCHMARK_PORTFOLIO: tuple[PublicBenchmarkSpec, ...] = (
    PublicBenchmarkSpec("epfl_guidelines", "epfl-llm / Guidelines", "L0_raw_guideline_corpus", "https://huggingface.co/datasets/epfl-llm/guidelines", "open", True, "open_world_guideline_parsing", ("guideline_document_parsing", "section_typing", "recommendation_candidate_detection"), "document_metadata_and_weak_coverage", ("parse_success_rate", "section_coverage", "candidate_rule_density"), ("GuidelineDocument", "GuidelineSection", "RecommendationCandidate"), "Stress-test ingestion before MediDiet transfer."),
    PublicBenchmarkSpec("cpgqa", "cpgQA", "L1_guideline_qa", "https://github.com/mmahbub/cpgQA", "open", True, "guideline_question_answering", ("guideline_mrc", "rule_backed_answer_generation", "citation_trace_check"), "guideline_qa_pairs_with_contexts", ("qa_accuracy", "answer_support_rate", "citation_completeness"), ("GuidelineQuestion", "AnswerEvidence", "RuleBackedAnswer"), "Compare DocRule-backed QA against direct RAG."),
    PublicBenchmarkSpec("meddm", "MedDM Clinical Guidance Trees", "L2_executable_guideline_structure", "https://arxiv.org/html/2312.02441v1", "open", True, "text_to_executable_decision_structure", ("decision_node_extraction", "action_node_extraction", "decision_edge_extraction"), "clinical_guidance_tree_nodes_and_edges", ("node_precision", "node_recall", "edge_f1"), ("DecisionNode", "ActionNode", "DecisionEdge", "RuleCandidateDraft"), "Sanity-check executable rule structure."),
    PublicBenchmarkSpec("text2mdt", "Text2MDT / Text2MDT-TE", "L2_executable_guideline_structure", "https://arxiv.org/html/2401.02034v1", "open", True, "medical_text_to_decision_tree", ("condition_action_triplet_extraction", "threshold_extraction", "tree_structure_reconstruction"), "medical_decision_tree_and_triplet_annotations", ("triplet_f1", "condition_f1", "threshold_accuracy"), ("DecisionNode", "ActionNode", "DecisionEdge", "RuleCandidateDraft"), "Compare MDT extraction with DocRule candidates."),
    PublicBenchmarkSpec("sglt2i_conflicts", "Chinese SGLT2i multidisciplinary guideline conflict dataset", "L3_conflict_governance", "https://arxiv.org/html/2604.17340v1", "open", True, "multi_guideline_conflict_detection", ("conflict_pair_detection", "conflict_pair_classification", "arbitration_trace_generation"), "expert_conflict_type_gold_standard", ("conflict_precision", "conflict_recall", "conflict_type_accuracy"), ("ConflictPair", "ConflictType", "ArbitrationTrace"), "Validate governance before nutrition conflict transfer."),
    PublicBenchmarkSpec("amega_llm", "AMEGA-LLM", "L4_guideline_adherence_safety", "https://pmc.ncbi.nlm.nih.gov/articles/PMC11638254/", "open", True, "multi_turn_guideline_adherence", ("guideline_adherence_scoring", "safety_error_detection", "explanation_audit"), "guideline_based_rubric", ("guideline_adherence_score", "safety_error_rate", "citation_completeness"), ("GuidelineAdherenceCase", "SafetyError", "CitationTrace"), "Compare DocRule-Agent with pure RAG."),
    PublicBenchmarkSpec("medguide", "MedGUIDE", "L4_guideline_adherence_safety", "https://arxiv.org/abs/2505.11613", "open", False, "guideline_consistent_decision_making", ("decision_adherence_scoring", "safety_error_detection"), "guideline_consistency_cases", ("guideline_consistency", "decision_accuracy", "unsafe_action_rate"), ("GuidelineAdherenceCase", "SafetyError", "CitationTrace"), "External robustness check."),
    PublicBenchmarkSpec("ragcare_qa", "RAGCare-QA", "L5_rag_comparison", "https://huggingface.co/datasets/ChatMED-Project/RAGCare-QA", "open", True, "medical_rag_question_answering", ("rag_answering", "retrieval_noise_robustness", "citation_quality_scoring"), "medical_qa_labels_and_noise_settings", ("qa_accuracy", "retrieval_noise_robustness", "citation_quality"), ("GuidelineQuestion", "AnswerEvidence", "RuleBackedAnswer", "CitationTrace"), "Direct RAG baseline comparison."),
    PublicBenchmarkSpec("high_precision_ir_updates", "High-Precision IR / Next Generation Evidence guideline updates", "L6_version_evidence_update", "https://www.nature.com/articles/s41746-025-01648-5", "method_reference", False, "living_guideline_update", ("evidence_update_detection", "versioned_recommendation_alignment", "rule_diff_gold_construction"), "method_reference", ("update_detection_recall", "update_detection_precision", "rule_diff_accuracy"), ("VersionedRecommendation", "EvidenceLink", "RuleDiffGold"), "Method template for source update gold."),
    PublicBenchmarkSpec("q2crbench3", "Q2CRBench-3 / Quicker", "L6_version_evidence_update", "https://arxiv.org/html/2505.10282v1", "open_or_method_reference", False, "question_to_clinical_recommendation", ("evidence_to_recommendation_reconstruction", "recommendation_decomposition", "evidence_chain_trace"), "recommendation_labels", ("recommendation_accuracy", "evidence_chain_completeness", "decomposition_f1"), ("VersionedRecommendation", "EvidenceLink", "RuleCandidateDraft"), "Test evidence to recommendation decomposition."),
    PublicBenchmarkSpec("target_nutrition_gold", "Self-built KDOQI / KDIGO / ADA / dialysis nutrition rule gold", "L7_target_transfer", "docs/research/target-nutrition-gold-protocol.md", "self_built", False, "target_domain_rule_registration_gold", ("nutrition_rule_extraction", "dialysis_rule_extraction", "target_domain_conflict_detection"), "small_high_quality_rule_level_gold", ("rule_level_precision_recall_f1", "high_risk_rule_miss_rate", "numeric_threshold_accuracy"), ("NutritionRuleGold", "RuleCandidateDraft", "ConflictPair", "CitationTrace"), "Core target-domain evidence."),
    PublicBenchmarkSpec("clinical_ie_aux", "mitclinicalml / clinical-ie, CBLUE, MedBench", "L8_auxiliary_ie", "https://huggingface.co/datasets/mitclinicalml/clinical-ie", "mixed_open", False, "field_level_clinical_ie", ("entity_extraction", "relation_extraction", "event_extraction"), "dataset_specific_ie_labels", ("entity_f1", "relation_f1", "event_f1"), ("ConditionCandidate", "RelationCandidate", "EvidenceUnit"), "Optional lower-level calibration."),
)


def get_benchmark(benchmark_id: str) -> PublicBenchmarkSpec:
    for benchmark in BENCHMARK_PORTFOLIO:
        if benchmark.benchmark_id == benchmark_id:
            return benchmark
    raise KeyError(f"Unknown benchmark: {benchmark_id}")
