from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from medidiet.domain import ConceptCode, CodeKind
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from knowledge.schema import ExtractedConditionRule, VerificationResult, VerificationIssue


class RuleStore:
    def __init__(self, data_dir: str = "data"):
        self._rules_dir = Path(data_dir) / "rules"
        self._rules_dir.mkdir(parents=True, exist_ok=True)
        self._candidates_file = self._rules_dir / "candidates.json"
        self._versions: dict[str, Path] = {}
        self._cache: dict[str, ExtractedConditionRule] = {}
        self._load()

    def create(self, rule: ExtractedConditionRule) -> None:
        if rule.candidate_id in self._cache:
            raise ValueError(f"rule already exists: {rule.candidate_id}")
        self._cache[rule.candidate_id] = rule
        self._save()

    def get(self, candidate_id: str) -> ExtractedConditionRule | None:
        return self._cache.get(candidate_id)

    def update(self, rule: ExtractedConditionRule) -> None:
        if rule.candidate_id not in self._cache:
            raise ValueError(f"rule not found: {rule.candidate_id}")
        self._cache[rule.candidate_id] = rule
        self._save()

    def delete(self, candidate_id: str) -> None:
        if candidate_id not in self._cache:
            raise ValueError(f"rule not found: {candidate_id}")
        del self._cache[candidate_id]
        self._save()

    def list_all(self) -> list[ExtractedConditionRule]:
        return list(self._cache.values())

    def list_by_status(self, status: str) -> list[ExtractedConditionRule]:
        return [rule for rule in self._cache.values() if rule.status == status]

    def list_by_condition(self, condition: ConceptCode) -> list[ExtractedConditionRule]:
        return [
            rule
            for rule in self._cache.values()
            if rule.condition == condition
        ]

    def publish_version(self, version: str, notes: str) -> str:
        approved = self.list_by_status("approved")
        rules_data = [_serialize_rule(rule) for rule in approved]
        payload = {
            "version": version,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
            "rules": rules_data,
        }
        version_path = self._rules_dir / f"{version}.json"
        with open(version_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self._versions[version] = version_path
        return str(version_path)

    def list_versions(self) -> list[str]:
        versions = []
        for entry in sorted(self._rules_dir.glob("v*.json")):
            name = entry.stem
            if name not in self._versions:
                self._versions[name] = entry
            versions.append(name)
        return sorted(versions)

    def load_version(self, version: str) -> list[ExtractedConditionRule]:
        version_path = self._rules_dir / f"{version}.json"
        if not version_path.exists():
            raise ValueError(f"version not found: {version}")
        with open(version_path, encoding="utf-8") as f:
            data = json.load(f)
        return [_deserialize_rule(rule_data) for rule_data in data["rules"]]

    def _load(self) -> None:
        if self._candidates_file.exists():
            with open(self._candidates_file, encoding="utf-8") as f:
                data = json.load(f)
            for rule_data in data.get("candidates", []):
                rule = _deserialize_rule(rule_data)
                self._cache[rule.candidate_id] = rule

    def _save(self) -> None:
        candidates = [_serialize_rule(rule) for rule in self._cache.values()]
        with open(self._candidates_file, "w", encoding="utf-8") as f:
            json.dump({"candidates": candidates}, f, ensure_ascii=False, indent=2)


def _serialize_rule(rule: ExtractedConditionRule) -> dict:
    data = {
        "candidate_id": rule.candidate_id,
        "source_doc_ids": rule.source_doc_ids,
        "source_chunk_ids": rule.source_chunk_ids,
        "condition": {"kind": rule.condition.kind.value, "value": rule.condition.value},
        "hard_exclusions": [
            {"kind": c.kind.value, "value": c.value} for c in rule.hard_exclusions
        ],
        "preferred_tags": [
            {"kind": c.kind.value, "value": c.value} for c in rule.preferred_tags
        ],
        "nutrition_limits": [
            {
                "metric": limit.metric.value,
                "scope": limit.scope.value,
                "max_value": limit.max_value,
                "window_hours": limit.window_hours,
            }
            for limit in rule.nutrition_limits
        ],
        "confidence": rule.confidence,
        "extraction_method": rule.extraction_method,
        "reviewed_by": rule.reviewed_by,
        "status": rule.status,
        "created_at": rule.created_at.isoformat(),
    }
    if rule.verification_result is not None:
        vr = rule.verification_result
        data["verification_result"] = {
            "verdict": vr.verdict,
            "confidence": vr.confidence,
            "consistency_score": vr.consistency_score,
            "logic_score": vr.logic_score,
            "completeness_score": vr.completeness_score,
            "issues": [
                {
                    "severity": iss.severity,
                    "dimension": iss.dimension,
                    "description": iss.description,
                    "related_field": iss.related_field,
                    "suggested_fix": iss.suggested_fix,
                }
                for iss in vr.issues
            ],
            "missing_items": vr.missing_items,
            "evidence_quotes": vr.evidence_quotes,
        }
    return data


def _deserialize_rule(data: dict) -> ExtractedConditionRule:
    condition = ConceptCode(
        CodeKind(data["condition"]["kind"]), data["condition"]["value"]
    )
    hard_exclusions = {
        ConceptCode(CodeKind(c["kind"]), c["value"]) for c in data["hard_exclusions"]
    }
    preferred_tags = {
        ConceptCode(CodeKind(c["kind"]), c["value"]) for c in data["preferred_tags"]
    }
    nutrition_limits = set()
    for limit_data in data["nutrition_limits"]:
        window_hours = limit_data.get("window_hours")
        nutrition_limits.add(
            NutrientLimit(
                metric=NutrientMetric(limit_data["metric"]),
                scope=LimitScope(limit_data["scope"]),
                max_value=limit_data["max_value"],
                window_hours=window_hours,
            )
        )

    verification_result = None
    if "verification_result" in data and data["verification_result"] is not None:
        vr_data = data["verification_result"]
        issues = []
        for iss_data in vr_data.get("issues", []):
            issues.append(
                VerificationIssue(
                    severity=iss_data["severity"],
                    dimension=iss_data["dimension"],
                    description=iss_data["description"],
                    related_field=iss_data.get("related_field"),
                    suggested_fix=iss_data.get("suggested_fix"),
                )
            )
        verification_result = VerificationResult(
            verdict=vr_data["verdict"],
            confidence=vr_data["confidence"],
            consistency_score=vr_data["consistency_score"],
            logic_score=vr_data["logic_score"],
            completeness_score=vr_data["completeness_score"],
            issues=issues,
            missing_items=vr_data.get("missing_items"),
            evidence_quotes=vr_data.get("evidence_quotes", {}),
        )

    return ExtractedConditionRule(
        candidate_id=data["candidate_id"],
        source_doc_ids=data["source_doc_ids"],
        source_chunk_ids=data["source_chunk_ids"],
        condition=condition,
        hard_exclusions=hard_exclusions,
        preferred_tags=preferred_tags,
        nutrition_limits=nutrition_limits,
        confidence=data["confidence"],
        extraction_method=data["extraction_method"],
        reviewed_by=data.get("reviewed_by"),
        status=data["status"],
        created_at=datetime.fromisoformat(data["created_at"]),
        verification_result=verification_result,
    )
