import json

from medidiet.llm import LLMResponse, LLMTask
from knowledge.concept_discovery import discover_concept_candidates


class CandidateProvider:
    def __init__(self) -> None:
        self.tasks = []

    def complete(self, request):
        self.tasks.append(request.task)
        return LLMResponse(
            content=json.dumps(
                {
                    "candidates": [
                        {
                            "kind": "condition",
                            "value": "cardiovascular_risk",
                            "display_name": "Cardiovascular Risk",
                            "aliases": ["heart health"],
                            "definition": "Dietary prevention or risk reduction for cardiovascular disease.",
                            "evidence_quote": "improve cardiovascular health",
                            "confidence": 0.86,
                        }
                    ]
                }
            ),
            provider_name="test",
            model="test-model",
        )


def test_discover_concept_candidates_outputs_registry_schema():
    provider = CandidateProvider()

    candidates = discover_concept_candidates(
        provider=provider,
        doc_id="doc1",
        source_text="Dietary guidance to improve cardiovascular health.",
        known_condition_values={"hypertension"},
        source_content_strategy="extractable_content",
        source_hash="sha256:source",
    )

    assert provider.tasks == [LLMTask.RULE_EXTRACTION]
    assert candidates[0]["value"] == "cardiovascular_risk"
    assert candidates[0]["source_type"] == "llm"
    assert candidates[0]["status"] == "candidate"
    assert candidates[0]["evidence"] == ["improve cardiovascular health"]
    assert candidates[0]["source_doc_ids"] == ["doc1"]
    assert candidates[0]["source_content_strategy"] == "extractable_content"
    assert candidates[0]["source_hash"] == "sha256:source"
