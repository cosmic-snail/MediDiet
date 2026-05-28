from __future__ import annotations

from knowledge.extraction_experiments import BENCHMARK_EXPERIMENT_MATRIX, COMPARATOR_ARMS, EXPERIMENT_MATRIX, OBSERVATION_POINTS, get_benchmark_experiment, get_experiment


def test_experiment_matrix_covers_core_research_questions():
    experiment_ids = {experiment.experiment_id for experiment in EXPERIMENT_MATRIX}
    assert {"E1", "E2", "E3", "E4", "E5", "E6", "E7"} <= experiment_ids
    assert {"C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"} <= set(COMPARATOR_ARMS)
    assert len(OBSERVATION_POINTS) >= 13


def test_benchmark_experiment_matrix_covers_lifecycle_layers():
    benchmark_ids = {experiment.experiment_id for experiment in BENCHMARK_EXPERIMENT_MATRIX}
    assert {"B1", "B2", "B3", "B4", "B5", "B6", "B7"} <= benchmark_ids
    assert get_benchmark_experiment("B4").lifecycle_layer == "L3_conflict_governance"
    assert "conflict_type_accuracy" in get_benchmark_experiment("B4").primary_metrics


def test_stability_experiment_declares_repeats_and_observations():
    experiment = get_experiment("E3")
    assert experiment.name == "Stability study"
    assert experiment.default_repeats == 10
    assert "O6" in experiment.required_observation_points
    assert "O11" in experiment.required_observation_points
    assert "C7" in experiment.comparator_arms
