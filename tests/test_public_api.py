import unittest


class PublicApiTest(unittest.TestCase):
    def test_engine_exports_are_available(self):
        import medidiet
        from medidiet import (
            RecommendationEngine,
            RecommendationResult,
            RulePack,
            load_baseline_rule_pack,
        )

        self.assertEqual(
            medidiet.__all__,
            [
                "KnowledgeContext",
                "KnowledgePort",
                "KnowledgeRetriever",
                "KnowledgeRuleProvider",
                "KnowledgeSnippet",
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
            ],
        )
        self.assertEqual(RecommendationEngine.__name__, "RecommendationEngine")
        self.assertEqual(RecommendationResult.__name__, "RecommendationResult")
        rule_pack = load_baseline_rule_pack()
        self.assertIsInstance(rule_pack, RulePack)
        self.assertIsInstance(RecommendationEngine(rule_pack), RecommendationEngine)

    def test_llm_exports_are_available(self):
        from medidiet import (
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

        self.assertEqual(LLMConfig.__name__, "LLMConfig")
        self.assertEqual(LLMFallbackReason.PROVIDER_ERROR.value, 6002)
        self.assertEqual(MockLLMProvider.__name__, "MockLLMProvider")
        self.assertEqual(OpenAICompatibleLLMProvider.__name__, "OpenAICompatibleLLMProvider")
        self.assertEqual(LLMContextSanitizer.__name__, "LLMContextSanitizer")
        self.assertEqual(LLMExplanationEnhancer.__name__, "LLMExplanationEnhancer")
        self.assertEqual(LLMQuestionAnswerer.__name__, "LLMQuestionAnswerer")
        self.assertEqual(LLMEnhancedExplanation.__name__, "LLMEnhancedExplanation")
        self.assertEqual(LLMAnswer.__name__, "LLMAnswer")

    def test_http_service_exports_are_available(self):
        from medidiet import RecommendationService, create_app

        self.assertEqual(RecommendationService.__name__, "RecommendationService")
        self.assertEqual(create_app.__name__, "create_app")

    def test_knowledge_exports_are_available(self):
        from medidiet import (
            KnowledgeContext,
            KnowledgePort,
            KnowledgeRetriever,
            KnowledgeRuleProvider,
            KnowledgeSnippet,
            RuleProviderPort,
        )

        self.assertEqual(KnowledgeContext.__name__, "KnowledgeContext")
        self.assertEqual(KnowledgePort.__name__, "KnowledgePort")
        self.assertEqual(KnowledgeRetriever.__name__, "KnowledgeRetriever")
        self.assertEqual(KnowledgeRuleProvider.__name__, "KnowledgeRuleProvider")
        self.assertEqual(KnowledgeSnippet.__name__, "KnowledgeSnippet")
        self.assertEqual(RuleProviderPort.__name__, "RuleProviderPort")


if __name__ == "__main__":
    unittest.main()
