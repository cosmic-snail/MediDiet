from __future__ import annotations

import json
from typing import Any

from medidiet.concept_registry import ConceptSourceType, ConceptStatus
from medidiet.domain import CodeKind, ConceptCode
from medidiet.llm import LLMProviderPort, LLMRequest, LLMTask


SYSTEM_PROMPT = """You identify missing clinical nutrition concept codes for a shared product and research registry.
Return JSON with a candidates array. Each candidate must include kind, value, display_name, aliases, definition, evidence_quote, and confidence.
Do not repeat known condition values. Do not approve candidates; every generated record remains status=candidate for human review."""


def discover_concept_candidates(
    *,
    provider: LLMProviderPort,
    doc_id: str,
    source_text: str,
    known_condition_values: set[str],
    source_content_strategy: str,
    source_hash: str,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    response = provider.complete(
        LLMRequest(
            task=LLMTask.RULE_EXTRACTION,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=(
                "Known condition values:\n"
                + ", ".join(sorted(known_condition_values))
                + "\n\nDocument id:\n"
                + doc_id
                + "\n\nSource text:\n"
                + source_text[:4000]
            ),
        )
    )
    payload = json.loads(response.content)
    candidates: list[dict[str, Any]] = []
    seen_values: set[str] = set()
    for candidate_record in payload.get("candidates", []) or []:
        if not isinstance(candidate_record, dict):
            continue
        value = str(candidate_record.get("value") or "").strip()
        if not value or value in known_condition_values or value in seen_values:
            continue
        confidence = float(candidate_record.get("confidence") or 0.0)
        if confidence < min_confidence:
            continue
        try:
            kind = CodeKind(str(candidate_record.get("kind") or ""))
            ConceptCode(kind, value)
        except (TypeError, ValueError):
            continue
        seen_values.add(value)
        evidence_quote = str(candidate_record.get("evidence_quote") or "")
        candidates.append(
            {
                "kind": kind.value,
                "value": value,
                "display_name": str(candidate_record.get("display_name") or value.replace("_", " ").title()),
                "aliases": [str(alias) for alias in candidate_record.get("aliases", []) or []],
                "source_type": ConceptSourceType.LLM.value,
                "status": ConceptStatus.CANDIDATE.value,
                "definition": str(candidate_record.get("definition") or ""),
                "evidence": [evidence_quote] if evidence_quote else [],
                "confidence": confidence,
                "source_doc_ids": [doc_id],
                "source_content_strategy": source_content_strategy,
                "source_hash": source_hash,
            }
        )
    return candidates
