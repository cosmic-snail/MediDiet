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
                "RecommendationEngine",
                "RecommendationResult",
                "RulePack",
                "load_baseline_rule_pack",
            ],
        )
        self.assertEqual(RecommendationEngine.__name__, "RecommendationEngine")
        self.assertEqual(RecommendationResult.__name__, "RecommendationResult")
        rule_pack = load_baseline_rule_pack()
        self.assertIsInstance(rule_pack, RulePack)
        self.assertIsInstance(RecommendationEngine(rule_pack), RecommendationEngine)


if __name__ == "__main__":
    unittest.main()
