"""MediDiet recommendation engine core."""

from medidiet.engine import RecommendationEngine, RecommendationResult
from medidiet.concept_registry import ConceptSourceType, ConceptStatus
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
from medidiet.ports import KnowledgeContext, KnowledgePort, KnowledgeSnippet, RuleProviderPort
from medidiet.rules import RulePack, load_baseline_rule_pack
from medidiet.server import create_app
from medidiet.service import RecommendationService

__version__ = "0.1.1"

__all__ = [
    "KnowledgeContext",
    "KnowledgePort",
    "KnowledgeSnippet",
    "ConceptSourceType",
    "ConceptStatus",
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
    "RuleProviderPort",
    "create_app",
    "load_baseline_rule_pack",
]
