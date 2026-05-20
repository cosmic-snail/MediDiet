from __future__ import annotations

from datetime import datetime, timezone

from medidiet.domain import ConceptCode, CodeKind, MealLabel, PatientProfile, ConceptRegistry, ConceptDefinition
from medidiet.rules import RulePack, ConditionRule, RuleSource
from medidiet.ports import KnowledgeSnippet, KnowledgeContext

from knowledge.store import RuleStore
from knowledge.vectordb import KnowledgeVectorDB
from knowledge.schema import ExtractedConditionRule


class KnowledgeRuleProvider:
    """Adapter that loads rules from a RuleStore and exposes them as a RulePack.

    Implements the RuleProviderPort protocol so the engine never imports
    the knowledge package directly.
    """

    def __init__(self, store: RuleStore, version: str | None = None):
        self._store = store
        self._version = version

    def load_rule_pack(self, version: str | None = None) -> RulePack:
        target = version or self._version
        if target is None:
            versions = self._store.list_versions()
            if not versions:
                raise ValueError("no published versions available")
            # Store returns versions without 'v' prefix; re-add it for
            # a consistent user-facing API.
            latest = versions[-1]
            target = "v" + latest

        extracted_rules = self._store.load_version(target)

        concepts = self._build_concept_registry(extracted_rules)
        rules_by_condition: dict[ConceptCode, ConditionRule] = {}
        for er in extracted_rules:
            if er.condition in rules_by_condition:
                existing = rules_by_condition[er.condition]
                rules_by_condition[er.condition] = ConditionRule(
                    condition=er.condition,
                    hard_exclusions=existing.hard_exclusions | er.hard_exclusions,
                    preferred_tags=existing.preferred_tags | er.preferred_tags,
                    nutrition_limits=existing.nutrition_limits | er.nutrition_limits,
                )
            else:
                rules_by_condition[er.condition] = ConditionRule(
                    condition=er.condition,
                    hard_exclusions=er.hard_exclusions,
                    preferred_tags=er.preferred_tags,
                    nutrition_limits=er.nutrition_limits,
                )

        return RulePack(
            version=target,
            sources=(
                RuleSource(
                    title="Knowledge Base",
                    url="",
                    version=target,
                    note="Generated from knowledge base",
                ),
            ),
            concepts=concepts,
            rules_by_condition=rules_by_condition,
        )

    def list_versions(self) -> list[str]:
        # Store strips the 'v' prefix; re-add it for a consistent API.
        return ["v" + v for v in self._store.list_versions()]

    def publish_version(self, version: str, notes: str) -> RulePack:
        self._store.publish_version(version, notes)
        return self.load_rule_pack(version)

    def _build_concept_registry(
        self, rules: list[ExtractedConditionRule],
    ) -> ConceptRegistry:
        definitions: list[ConceptDefinition] = []
        seen: set[tuple[CodeKind, str]] = set()

        for rule in rules:
            key = (rule.condition.kind, rule.condition.value)
            if key not in seen:
                seen.add(key)
                definitions.append(
                    ConceptDefinition(
                        code=rule.condition,
                        display_name=rule.condition.value.replace("_", " ").title(),
                    )
                )

            for code in rule.hard_exclusions | rule.preferred_tags:
                key = (code.kind, code.value)
                if key not in seen:
                    seen.add(key)
                    definitions.append(
                        ConceptDefinition(
                            code=code,
                            display_name=code.value.replace("_", " ").title(),
                        )
                    )

        return ConceptRegistry(definitions)


class KnowledgeRetriever:
    """Adapter that delegates semantic search to KnowledgeVectorDB.

    Converts internal knowledge.vectordb.KnowledgeSnippet objects to the
    port-level medidiet.ports.KnowledgeSnippet frozen dataclass.

    Implements the KnowledgePort protocol so the engine never imports
    the knowledge package directly.
    """

    def __init__(self, vectordb: KnowledgeVectorDB):
        self._vectordb = vectordb

    def search(self, query: str, top_k: int = 5) -> list[KnowledgeSnippet]:
        results = self._vectordb.search(query, top_k=top_k)
        return [
            KnowledgeSnippet(
                text=r.text,
                source_title=r.source_title,
                source_url=r.source_url,
                chunk_id=r.chunk_id,
                relevance_score=r.relevance_score,
            )
            for r in results
        ]

    def explain_rule(self, condition: ConceptCode) -> str:
        results = self._vectordb.search(
            condition.value.replace("_", " "), top_k=3
        )
        if not results:
            return f"No source documentation found for {condition.value}."

        lines = [f"Sources for {condition.value}:"]
        for r in results:
            lines.append(
                f"- [{r.source_title}] {r.text[:200]}"
                f"{'...' if len(r.text) > 200 else ''}"
            )
        return "\n".join(lines)

    def retrieve_context(
        self, patient: PatientProfile, meal_label: MealLabel,
    ) -> KnowledgeContext:
        queries = [c.value.replace("_", " ") for c in patient.conditions]
        if not queries:
            return KnowledgeContext(
                snippets=(),
                related_conditions=(),
                retrieved_at=datetime.now(timezone.utc),
            )

        all_snippets: list[KnowledgeSnippet] = []
        for query in queries:
            results = self._vectordb.search(query, top_k=3)
            for r in results:
                all_snippets.append(
                    KnowledgeSnippet(
                        text=r.text,
                        source_title=r.source_title,
                        source_url=r.source_url,
                        chunk_id=r.chunk_id,
                        relevance_score=r.relevance_score,
                    )
                )

        all_snippets.sort(key=lambda s: s.relevance_score, reverse=True)
        unique_snippets = list({s.chunk_id: s for s in all_snippets}.values())
        top = unique_snippets[:5]

        return KnowledgeContext(
            snippets=tuple(top),
            related_conditions=tuple(patient.conditions),
            retrieved_at=datetime.now(timezone.utc),
        )
