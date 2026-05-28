from __future__ import annotations

from knowledge.public_benchmarks import BENCHMARK_PORTFOLIO, get_benchmark


def test_benchmark_portfolio_covers_doc_rule_lifecycle_layers():
    benchmark_ids = {benchmark.benchmark_id for benchmark in BENCHMARK_PORTFOLIO}
    assert {"epfl_guidelines", "cpgqa", "meddm", "text2mdt", "sglt2i_conflicts", "amega_llm", "medguide", "ragcare_qa", "high_precision_ir_updates", "q2crbench3", "target_nutrition_gold"} <= benchmark_ids


def test_sglt2i_dataset_maps_to_conflict_governance_layer():
    sglt2i = get_benchmark("sglt2i_conflicts")
    assert sglt2i.lifecycle_layer == "L3_conflict_governance"
    assert "conflict_pair_classification" in sglt2i.calibration_tasks
    assert "ConflictPair" in sglt2i.bridge_outputs
    assert "ConflictType" in sglt2i.bridge_outputs


def test_target_nutrition_gold_is_self_built_and_not_public_authority_anchor():
    benchmark = get_benchmark("target_nutrition_gold")
    assert benchmark.access == "self_built"
    assert benchmark.required_for_ci is False
    assert benchmark.lifecycle_layer == "L7_target_transfer"
    assert "NutritionRuleGold" in benchmark.bridge_outputs
    assert "rule_level_precision_recall_f1" in benchmark.primary_metrics
