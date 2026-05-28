from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileFact:
    node: str
    evidence: str
    confidence: float


STOPWORDS = {
    "a", "an", "and", "or", "the", "of", "to", "in", "on", "with", "by", "as",
    "per", "if", "after", "before", "for", "from", "was", "were", "is", "are",
    "be", "been", "being", "no", "not", "only", "consider",
}

SYNONYMS = {
    "bm": "bone marrow",
    "mo": "months",
    "hct": "transplant",
    "hematopoietic": "transplant",
    "cell": "transplant",
    "transplantation": "transplant",
    "anthracyclines": "anthracycline",
    "levels": "level",
}


def extract_profile_facts(
    profile: str,
    candidate_nodes: list[str],
    min_confidence: float = 0.45,
) -> list[ProfileFact]:
    profile_tokens = _tokens(profile)
    facts: list[ProfileFact] = []
    for node in candidate_nodes:
        node_tokens = _tokens(node)
        if not node_tokens:
            continue
        overlap = profile_tokens & node_tokens
        confidence = len(overlap) / min(len(node_tokens), 6)
        if len(overlap) >= 2 and confidence >= min_confidence:
            facts.append(
                ProfileFact(
                    node=node,
                    evidence=_evidence_window(profile, overlap),
                    confidence=round(min(confidence, 1.0), 3),
                )
            )
    return facts


def _tokens(text: str) -> set[str]:
    normalized = text.lower()
    normalized = normalized.replace(">=", " greater equal ").replace("<=", " less equal ")
    normalized = normalized.replace("<", " less ").replace(">", " greater ")
    raw_tokens = re.findall(r"[a-z0-9]+", normalized)
    tokens: set[str] = set()
    for token in raw_tokens:
        if token in STOPWORDS or len(token) <= 1:
            continue
        replacement = SYNONYMS.get(token, token)
        tokens.update(part for part in replacement.split() if part not in STOPWORDS)
    return tokens


def _evidence_window(profile: str, overlap: set[str]) -> str:
    lower = profile.lower()
    positions = [
        lower.find(token)
        for token in overlap
        if lower.find(token) >= 0
    ]
    if not positions:
        return profile[:240]
    center = min(positions)
    start = max(0, center - 90)
    end = min(len(profile), center + 180)
    return profile[start:end].strip()
