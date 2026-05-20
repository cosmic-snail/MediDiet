from datetime import datetime, timezone
import unittest

from medidiet.domain import ConceptCode, CodeKind, MealLabel, PatientProfile, Preference, DataSource
from medidiet.safety import SafetyCode
from medidiet.ports import (
    DomainEvent,
    EventName,
    IntakeEstimationRequest,
    KnowledgeContext,
    KnowledgePort,
    KnowledgeSnippet,
    RecommendationRequestEnvelope,
    RuleProviderPort,
)


NOW = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)


class PortsTest(unittest.TestCase):
    def test_request_envelope_carries_version_source_and_aware_time(self):
        envelope = RecommendationRequestEnvelope(
            schema_version="v1",
            source_system="mini-program",
            source_version="0.1.0",
            request_id="req-1",
            created_at=NOW,
        )

        self.assertEqual(envelope.schema_version, "v1")
        self.assertEqual(envelope.source_system, "mini-program")
        self.assertEqual(envelope.to_dict()["createdAt"], "2026-05-16T12:00:00+00:00")

    def test_request_envelope_rejects_string_or_naive_time(self):
        with self.assertRaises(TypeError):
            RecommendationRequestEnvelope("v1", "mini-program", "0.1.0", "req-1", "2026-05-16T12:00:00+08:00")
        with self.assertRaises(ValueError):
            RecommendationRequestEnvelope("v1", "mini-program", "0.1.0", "req-1", datetime(2026, 5, 16, 12, 0))

    def test_intake_request_carries_image_reference_and_meal_label(self):
        request = IntakeEstimationRequest(
            envelope=RecommendationRequestEnvelope("v1", "mini-program", "0.1.0", "req-2", NOW),
            image_uri="oss://bucket/meal.jpg",
            meal_label=MealLabel.LUNCH,
        )

        self.assertEqual(request.image_uri, "oss://bucket/meal.jpg")
        self.assertEqual(request.meal_label, MealLabel.LUNCH)
        self.assertEqual(request.to_dict()["mealLabel"], MealLabel.LUNCH.value)

    def test_intake_request_rejects_string_meal_label(self):
        with self.assertRaises(TypeError):
            IntakeEstimationRequest(
                envelope=RecommendationRequestEnvelope("v1", "mini-program", "0.1.0", "req-2", NOW),
                image_uri="oss://bucket/meal.jpg",
                meal_label="lunch",
            )

    def test_domain_event_names_are_stable_and_payload_can_carry_integer_codes(self):
        event = DomainEvent(
            name=EventName.HUMAN_REVIEW_REQUIRED,
            trace_id="trace-1",
            payload={"code": SafetyCode.LOW_CONFIDENCE_INTAKE.value},
            created_at=NOW,
        )

        payload = event.to_dict()
        self.assertEqual(event.name.value, "HumanReviewRequired")
        self.assertEqual(payload["name"], "HumanReviewRequired")
        self.assertEqual(payload["payload"]["code"], SafetyCode.LOW_CONFIDENCE_INTAKE.value)
        self.assertEqual(payload["createdAt"], "2026-05-16T12:00:00+00:00")

    def test_domain_event_rejects_string_name_or_naive_time(self):
        with self.assertRaises(TypeError):
            DomainEvent(name="HumanReviewRequired", trace_id="trace-1", payload={}, created_at=NOW)
        with self.assertRaises(ValueError):
            DomainEvent(
                name=EventName.HUMAN_REVIEW_REQUIRED,
                trace_id="trace-1",
                payload={},
                created_at=datetime(2026, 5, 16, 12, 0),
            )


class TestKnowledgeSnippet(unittest.TestCase):
    def test_valid_snippet(self):
        snippet = KnowledgeSnippet(
            text="Limit sodium to 2000mg per day.",
            source_title="CKD Guidelines",
            source_url="https://example.org/ckd.pdf",
            chunk_id="doc-001-chunk-0000",
            relevance_score=0.85,
        )
        assert snippet.text == "Limit sodium to 2000mg per day."
        assert snippet.relevance_score == 0.85


class TestKnowledgeContext(unittest.TestCase):
    def test_valid_context(self):
        snippets = (
            KnowledgeSnippet(
                text="Sodium restriction.",
                source_title="Guide",
                source_url="https://example.org",
                chunk_id="chunk-001",
                relevance_score=0.9,
            ),
        )
        ctx = KnowledgeContext(
            snippets=snippets,
            related_conditions=(ConceptCode(CodeKind.CONDITION, "hypertension"),),
            retrieved_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        )
        assert len(ctx.snippets) == 1
        assert len(ctx.related_conditions) == 1


class TestRuleProviderPortProtocol(unittest.TestCase):
    def test_protocol_is_usable_for_type_checking(self):
        class FakeProvider:
            def load_rule_pack(self, version=None):
                pass

            def list_versions(self):
                return []

            def publish_version(self, version, notes):
                pass

        provider = FakeProvider()
        assert isinstance(provider, RuleProviderPort)


class TestKnowledgePortProtocol(unittest.TestCase):
    def test_protocol_is_usable_for_type_checking(self):
        class FakeKnowledge:
            def search(self, query, top_k=5):
                return []

            def explain_rule(self, condition):
                return ""

            def retrieve_context(self, patient, meal_label):
                return KnowledgeContext(
                    snippets=(),
                    related_conditions=(),
                    retrieved_at=datetime.now(timezone.utc),
                )

        kp = FakeKnowledge()
        assert isinstance(kp, KnowledgePort)


if __name__ == "__main__":
    unittest.main()
