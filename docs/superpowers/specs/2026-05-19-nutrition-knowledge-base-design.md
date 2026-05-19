# Nutrition Knowledge Base Design

Version: 0.1.0
Target: Add a nutrition knowledge base that extracts rules for next-meal recommendations via structured data + vector document library + LLM extraction pipeline.

## 1. Objectives

- Build a **standalone knowledge base package** (`knowledge/`) with structured rule storage, document management, vector search, and LLM rule extraction with cross-validation.
- Integrate with MediDiet engine via **defined ports** (`RuleProviderPort`, `KnowledgePort`) — the engine never directly depends on the knowledge package.
- Support **three rule ingestion paths**: manual curation, LLM extraction, LLM extraction + human review.
- Support **dual-mode operation**: offline (deterministic rules only, default) and online (optional vector retrieval for explanation enrichment).
- Deliver in **three phases**: infrastructure → extraction pipeline → engine integration.

## 2. Directory Structure

```
MediDiet/
├── knowledge/                          # New: independent knowledge base package
│   ├── pyproject.toml                  # Dependencies: chromadb, httpx
│   ├── src/
│   │   └── knowledge/
│   │       ├── __init__.py
│   │       ├── schema.py               # Data structures
│   │       ├── store.py                # Structured rule CRUD + versioning
│   │       ├── documents.py            # Document import, chunking, metadata
│   │       ├── vectordb.py             # ChromaDB vector store + semantic search
│   │       ├── extractor.py            # LLM rule extraction pipeline (2-stage with cross-validation)
│   │       ├── curator.py              # Manual curation API
│   │       ├── retriever.py            # Online retrieval for dual-mode
│   │       └── loader.py               # Batch import from docs/knowledge/
│   └── tests/
│       ├── test_store.py
│       ├── test_documents.py
│       ├── test_vectordb.py
│       ├── test_extractor.py
│       └── test_retriever.py
│
├── src/medidiet/
│   ├── ports.py                        # Extended: KnowledgePort, RuleProviderPort
│   ├── rules.py                        # Extended: support loading from RuleProviderPort
│   ├── engine.py                       # Extended: optional KnowledgePort injection
│   ├── knowledge_bridge.py             # New: port adapter connecting the knowledge package
│   └── ...                             # Remaining files unchanged
│
├── docs/
│   └── knowledge/                      # New: unstructured knowledge documents
│       ├── guidelines/                 # Clinical dietary guideline PDFs/MD
│       ├── papers/                     # Research papers
│       └── food_db/                    # Food composition tables
│
└── data/                               # Runtime data (gitignored)
    ├── chroma/                         # Vector persistence
    ├── rules/                          # Structured rule JSON versions
    └── knowledge.db                    # SQLite metadata
```

## 3. Data Model

### 3.1 Documents & Chunks

```python
@dataclass
class KnowledgeDocument:
    doc_id: str
    title: str
    source: str                          # URL / file path / institution
    source_type: str                     # "guideline" | "paper" | "food_db" | "manual"
    content_raw: str
    chunks: list[DocumentChunk]
    metadata: dict[str, str]             # year, institution, language, etc.
    ingested_at: datetime

@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    embedding: list[float] | None        # Managed by ChromaDB
    metadata: dict[str, str]             # page number, section title, etc.
```

### 3.2 Rule Candidates (intermediate state between extraction and approval)

```python
@dataclass
class ExtractedConditionRule:
    candidate_id: str
    source_doc_ids: list[str]
    source_chunk_ids: list[str]          # Traceable to specific text fragments
    condition: ConceptCode
    hard_exclusions: set[ConceptCode]
    preferred_tags: set[ConceptCode]
    nutrition_limits: set[NutrientLimit]
    confidence: float                    # LLM extraction confidence
    extraction_method: str               # "llm" | "manual" | "llm+review"
    reviewed_by: str | None
    status: str                          # "draft" | "pending_review" | "approved" | "rejected"
    created_at: datetime
    verification_result: VerificationResult | None  # From cross-validation
```

### 3.3 Cross-Validation Results

```python
@dataclass
class VerificationResult:
    verdict: str                         # "pass" | "revision_needed" | "rejected"
    confidence: float
    consistency_score: float             # Source traceability 0-1
    logic_score: float                   # Logical coherence 0-1
    completeness_score: float            # Coverage completeness 0-1
    issues: list[VerificationIssue]
    missing_items: list[str] | None
    revised_rule: ExtractedConditionRule | None
    evidence_quotes: dict[str, str]      # Original text per rule field

@dataclass
class VerificationIssue:
    severity: str                        # "critical" | "warning" | "info"
    dimension: str                       # "consistency" | "logic" | "completeness"
    description: str
    related_field: str | None
    suggested_fix: str | None
```

### 3.4 Concept Discovery

```python
@dataclass
class SuggestedConcept:
    suggest_id: str
    candidate_rule_id: str
    suggested_code: ConceptCode
    definition: str
    source_chunk_ids: list[str]
    display_name: str
```

## 4. Port Interfaces

### 4.1 RuleProviderPort

```python
class RuleProviderPort(Protocol):
    def load_rule_pack(self, version: str | None = None) -> RulePack: ...
    def list_versions(self) -> list[str]: ...
    def publish_version(self, version: str, notes: str) -> RulePack: ...
```

### 4.2 KnowledgePort

```python
class KnowledgePort(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[KnowledgeSnippet]: ...
    def explain_rule(self, condition: ConceptCode) -> str: ...
    def retrieve_context(self, patient: PatientProfile,
                         meal_label: MealLabel) -> KnowledgeContext: ...

@dataclass
class KnowledgeSnippet:
    text: str
    source_title: str
    source_url: str
    chunk_id: str
    relevance_score: float

@dataclass
class KnowledgeContext:
    snippets: list[KnowledgeSnippet]
    related_conditions: list[ConceptCode]
    retrieved_at: datetime
```

### 4.3 Adapter

`src/medidiet/knowledge_bridge.py` implements both ports using the `knowledge` package. The engine and service depend only on the ports, never importing `knowledge` directly.

## 5. Engine Integration & Dual Mode

### 5.1 Engine Construction

```python
# A) Traditional: direct RulePack (existing tests unchanged)
engine = RecommendationEngine(rule_pack=load_baseline_rule_pack())

# B) Port-based: load from knowledge base
engine = RecommendationEngine(rule_provider=KnowledgeRuleProvider())

# C) Port-based + online retrieval (research/complex cases)
engine = RecommendationEngine(
    rule_provider=KnowledgeRuleProvider(),
    knowledge=KnowledgeRetriever(),
)
```

### 5.2 Dual Mode

| Mode | Trigger | Behavior |
| --- | --- | --- |
| Offline (default) | `knowledge` param is None | Pure rule engine, identical to current behavior |
| Online enhanced | `KnowledgePort` implementation injected | After recommendation, calls `retrieve_context()` for knowledge snippets; enriches `clinician_explanation` |

**Constraints:**
- Online retrieval does NOT participate in rule decisions — safety gate, matcher, scoring remain deterministic
- Online retrieval only enriches explanations — adds `knowledge_snippets` field in `clinician_explanation`
- Online retrieval timeout/failure silently degrades, never blocks the recommendation

### 5.3 Recommendation Flow

```
SafetyGate → DailyNutritionCalculator → MealPlanGenerator → MenuMatcher
  → ExplanationBuilder → [if knowledge port injected] retrieve_context()
    → enrich clinician_explanation → return RecommendationResult
```

## 6. LLM Rule Extraction Pipeline

### 6.1 Two-Stage Flow

```
Import Document (chunk + vectorize)
  → Semantic Search (retrieve relevant fragments by disease/nutrient keywords)
  → Stage 1: LLM Extract (extract candidate rules from fragments)
  → Stage 2: LLM Cross-Validate (different persona, structured verification)
  → Verdict handling:
      - pass/high_conf → save as draft with verification result
      - revision_needed → revise with feedback, re-verify (max 2 retries)
      - rejected → mark rejected with reason, exit pipeline
  → [optional] Human Review → approved
  → publish_version()
```

### 6.2 Cross-Validation Dimensions

| Dimension | What It Checks |
| --- | --- |
| Source Consistency | Can each rule field be traced to supporting evidence in the provided document fragments? |
| Logical Coherence | Do hard_exclusions contradict preferred_tags? Are nutrition_limit values in reasonable ranges? Do rules conflict with existing rules? |
| Completeness | Are there missing contraindications, preferred tags, or nutrition limits in the source fragments? |

The verifier outputs a structured `VerificationResult` with per-dimension scores (0-1), specific issues, evidence quotes, and optionally a revised rule.

**Key constraints:**
- Extraction and verification MUST use different system prompt personas
- Verification results are persisted with the rule candidate and travel through the full audit chain
- Both stages share the same document fragment context — no additional retrieval during verification

### 6.3 Manual Curation Path

```python
curator.create_rule(condition, hard_exclusions, preferred_tags, limits, sources)
curator.review_rule(candidate_id, decision="approved")
curator.reject_rule(candidate_id, reason="...")
curator.publish(version="v2.1", notes="Added CKD and gout rules")
```

Manual curation and LLM extraction share the same store → publish pipeline.

## 7. Vector Database & Document Management

### 7.1 ChromaDB Integration (knowledge/vectordb.py)

```python
class KnowledgeVectorDB:
    def __init__(self, persist_dir: str = "data/chroma"): ...
    def index_document(self, doc: KnowledgeDocument) -> None: ...
    def search(self, query: str, top_k: int = 5,
               filter_source: str | None = None) -> list[KnowledgeSnippet]: ...
    def search_by_condition(self, condition: ConceptCode,
                            top_k: int = 10) -> list[KnowledgeSnippet]: ...
    def delete_document(self, doc_id: str) -> None: ...
```

### 7.2 Document Import Pipeline

```
Raw document (PDF/MD/TXT)
  → Parse to plain text (PDF via simple extraction, MD preserves heading hierarchy)
  → Chunk by heading/paragraph (~1000 chars, ~200 chars overlap)
  → Optional: LLM pre-labeling (disease/nutrient tags for filtering)
  → Index into ChromaDB + store metadata
```

Chunking preserves structural info (section headings, list hierarchy) so retrieved results carry context.

### 7.3 Storage Strategy

| Data | Location | Versioned |
| --- | --- | --- |
| Vector embeddings | `data/chroma/` | No (gitignored) |
| Structured rules | `data/rules/v*.json` | Yes (git tracked) |
| Document metadata | `data/knowledge.db` (SQLite) | No (gitignored) |
| Source documents | `docs/knowledge/` | Yes (git tracked) |

## 8. Phased Delivery

### Phase 1: Knowledge Base Infrastructure

- `knowledge` package skeleton: `pyproject.toml`, directory structure, `schema.py`
- `store.py`: structured rule CRUD + JSON file versioning
- `documents.py`: document import, chunking, metadata
- `vectordb.py`: ChromaDB integration, indexing, semantic search
- `loader.py`: batch import from `docs/knowledge/`
- `medidiet/ports.py`: `RuleProviderPort` + `KnowledgePort` interfaces
- `medidiet/knowledge_bridge.py`: port adapter implementation
- Tests for store, documents, vectordb

**Validation:** Import 2-3 documents, semantic search returns relevant fragments, structured rules are CRUD-able.

### Phase 2: LLM Extraction Pipeline

- `extractor.py`: Stage 1 LLM extraction + Stage 2 cross-validation
- `curator.py`: manual curation API
- `medidiet/rules.py` extension: support loading from `RuleProviderPort`
- End-to-end pilot: 2 new diseases (e.g., CKD, gout) through full pipeline
- Tests for extraction pipeline, cross-validation, curator

**Validation:** Extract CKD dietary rules from guideline documents, pass cross-validation, generate `RulePack`, engine recommends using new rules.

### Phase 3: Engine Online Enhancement + Extended Dimensions

- `engine.py` dual-mode: accept `KnowledgePort`, online retrieval enriches explanations
- `retriever.py`: online retrieval context assembly
- `nutrition.py` extension: nutrient gap compensation dimension (previous meal gap → next meal preference)
- `matcher.py` extension: ingredient diversity scoring factor
- Server integration: HTTP API exposes knowledge traceability info
- Tests for dual-mode, new dimensions, full integration

**Validation:** Default mode engine behavior unchanged. Online mode includes `knowledge_snippets` in `clinician_explanation`. Nutrient gap compensation and ingredient diversity participate in scoring.

### Dependency Graph

```
Phase 1 ──→ Phase 2 ──→ Phase 3
              │
              └── curator (manual curation) can be developed in parallel with LLM extraction
```

## 9. Design Constraints

- Every active `ConditionRule` must be traceable back to its source document fragment(s)
- LLM extraction never creates new `ConceptCode` directly — new concepts output as `SuggestedConcept` and enter human review
- **Dependency direction**: The `knowledge` package may import base domain types (`ConceptCode`, `CodeKind`, `NutrientLimit`, `NutrientMetric`, `LimitScope`) from `medidiet.domain` and `medidiet.rules`. The engine (`medidiet`) depends on knowledge only through port Protocols — it never imports from `knowledge` directly. `knowledge_bridge.py` is the sole integration point that imports both packages.
- Cross-validation uses different system prompt personas for extraction vs. verification
- Online retrieval failure must never block recommendation — silent degradation
- Existing `RecommendationEngine` constructor signature remains valid for backward compatibility
- Existing tests pass unchanged when knowledge ports are not injected
- LLM pre-labeling of document chunks (mentioned in document import pipeline) is optional and deferred to Phase 2
