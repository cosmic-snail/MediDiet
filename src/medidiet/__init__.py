"""MediDiet recommendation engine core."""

from medidiet.engine import RecommendationEngine, RecommendationResult
from medidiet.llm import (
    LLMAnswer,
    LLMConfig,
    LLMContextSanitizer,
    LLMEnhancedExplanation,
    LLMExplanationEnhancer,
    LLMFallbackReason,
    LLMQuestionAnswerer,
    MockLLMProvider,
    OpenAICompatibleLLMProvider,
)
from medidiet.rules import RulePack, load_baseline_rule_pack
from medidiet.server import create_app
from medidiet.service import RecommendationService

__version__ = "0.1.1"

__all__ = [
    "LLMAnswer",
    "LLMConfig",
    "LLMContextSanitizer",
    "LLMEnhancedExplanation",
    "LLMExplanationEnhancer",
    "LLMFallbackReason",
    "LLMQuestionAnswerer",
    "MockLLMProvider",
    "OpenAICompatibleLLMProvider",
    "RecommendationEngine",
    "RecommendationResult",
    "RecommendationService",
    "RulePack",
    "create_app",
    "load_baseline_rule_pack",
]
