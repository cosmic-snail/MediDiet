"""MediDiet recommendation engine core."""

from medidiet.engine import RecommendationEngine, RecommendationResult
from medidiet.rules import RulePack, load_baseline_rule_pack

__version__ = "0.1.0"

__all__ = [
    "RecommendationEngine",
    "RecommendationResult",
    "RulePack",
    "load_baseline_rule_pack",
]
