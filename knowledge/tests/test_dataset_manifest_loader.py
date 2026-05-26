from __future__ import annotations

from pathlib import Path

from knowledge.dataset_manifest import load_dataset_documents


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_manifest_loader_preserves_source_metadata():
    docs = load_dataset_documents(REPO_ROOT / "knowledge" / "datasets" / "rule_extraction_v1", source_root=REPO_ROOT / "knowledge" / "source_documents")
    assert docs
    doc = next(item for item in docs if item.metadata["doc_id"] == "en_guideline_who_sodium_2012")
    assert doc.source_type == "guideline"
    assert doc.metadata["dataset_id"] == "rule_extraction_v1"
    assert doc.metadata["source_url"].startswith("https://")
    assert doc.metadata["publisher"]
    assert doc.metadata["year"]
    assert "hypertension" in doc.metadata["disease_focus"]
    assert "sodium_mg" in doc.metadata["nutrition_focus"]
    assert doc.metadata["source_card_path"].endswith(".md")
    assert doc.metadata["source_card_hash"].startswith("sha256:")
    assert doc.metadata["extractable_content_hash"].startswith("sha256:")
