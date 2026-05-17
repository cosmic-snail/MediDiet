from datetime import datetime, timezone
import unittest

from medidiet.domain import MealLabel
from medidiet.ports import (
    DomainEvent,
    EventName,
    IntakeEstimationRequest,
    RecommendationRequestEnvelope,
)
from medidiet.safety import SafetyCode


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


if __name__ == "__main__":
    unittest.main()
