#!/usr/bin/env python3
"""Build a small external guideline dataset for rule-extraction smoke tests.

The script intentionally fetches selected rows through the HuggingFace dataset
viewer API instead of downloading the full ~878 MB JSONL source file.
"""

from __future__ import annotations

import json
import re
import textwrap
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATASET_API = "https://datasets-server.huggingface.co/rows"
HF_DATASET_URL = "https://huggingface.co/datasets/epfl-llm/guidelines"
REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "knowledge" / "source_documents" / "external_epfl_guidelines"
DATASET_DIR = REPO_ROOT / "knowledge" / "datasets" / "rule_extraction_epfl_guidelines_smoke"


@dataclass(frozen=True)
class SelectedGuideline:
    row_idx: int
    doc_id: str
    title: str
    source_type: str
    publisher: str
    disease_focus: list[str]
    nutrition_focus: list[str]
    evaluation_labels: list[str]
    notes: str


SELECTED_ROWS = [
    SelectedGuideline(
        row_idx=195,
        doc_id="epfl_cdc_physical_activity_diet_weight",
        title="CDC Physical Activity and Sound Dietary Practices for Weight Control",
        source_type="guideline",
        publisher="Centers for Disease Control and Prevention",
        disease_focus=["obesity", "chronic_disease_prevention"],
        nutrition_focus=["dietary_pattern", "physical_activity", "weight_management"],
        evaluation_labels=["external_smoke", "contextual"],
        notes="CDC row includes population targets combining sound dietary practices and regular physical activity.",
    ),
    SelectedGuideline(
        row_idx=102,
        doc_id="epfl_cdc_who_flour_fortification",
        title="WHO/FAO/UNICEF/GAIN Flour Fortification Position Statement",
        source_type="guideline",
        publisher="CDC-hosted WHO/FAO/UNICEF/GAIN statement",
        disease_focus=["micronutrient_deficiency", "public_health"],
        nutrition_focus=["food_fortification", "micronutrients", "dietary_pattern"],
        evaluation_labels=["external_smoke", "concept_gap"],
        notes="Public-health nutrition guidance; useful for observing whether the current schema handles fortification concepts.",
    ),
    SelectedGuideline(
        row_idx=1025,
        doc_id="epfl_cma_obesity_clinical_practice",
        title="CMA Obesity Clinical Practice Guideline",
        source_type="guideline",
        publisher="Canadian Medical Association Journal",
        disease_focus=["obesity", "cardiometabolic_risk"],
        nutrition_focus=["weight_management", "dietary_pattern", "food_choice"],
        evaluation_labels=["external_smoke", "contextual"],
        notes="Obesity guideline row with dietary behavior, food choice, and weight-management signals.",
    ),
    SelectedGuideline(
        row_idx=1063,
        doc_id="epfl_cma_type2_diabetes_primary_care",
        title="CMA Type 2 Diabetes Primary Care Guideline Summary",
        source_type="guideline",
        publisher="Canadian Medical Association Journal",
        disease_focus=["diabetes"],
        nutrition_focus=["dietary_pattern", "medical_nutrition_therapy", "carbohydrate_quality"],
        evaluation_labels=["external_smoke", "contextual"],
        notes="Diabetes guideline summary with dietary options and shared decision-making context.",
    ),
    SelectedGuideline(
        row_idx=2010,
        doc_id="epfl_nice_ckd_dialysis_fluid_management",
        title="NICE Multiple Frequency Bioimpedance Devices for CKD Dialysis Fluid Management",
        source_type="guideline",
        publisher="NICE",
        disease_focus=["chronic_kidney_disease"],
        nutrition_focus=["fluid_management", "target_weight", "blood_pressure"],
        evaluation_labels=["external_smoke", "concept_gap"],
        notes="CKD dialysis row is not a diet-only source; it tests whether renal fluid/weight management is treated as a nutrition-adjacent rule.",
    ),
    SelectedGuideline(
        row_idx=2011,
        doc_id="epfl_nice_obesity_local_communities",
        title="NICE Obesity: Working with Local Communities",
        source_type="guideline",
        publisher="NICE",
        disease_focus=["obesity", "chronic_disease_prevention"],
        nutrition_focus=["dietary_pattern", "physical_activity", "community_intervention"],
        evaluation_labels=["external_smoke", "patient_education"],
        notes="NICE public-health obesity guideline with diet and physical-activity intervention context.",
    ),
    SelectedGuideline(
        row_idx=4005,
        doc_id="epfl_pubmed_obesity_kidney_transplant",
        title="Management of Obesity in Kidney Transplant Candidates and Recipients",
        source_type="guideline",
        publisher="Nephrology Dialysis Transplantation",
        disease_focus=["obesity", "chronic_kidney_disease"],
        nutrition_focus=["weight_management", "protein", "potassium", "phosphorus"],
        evaluation_labels=["external_smoke", "concept_gap"],
        notes="Kidney-transplant obesity guideline stresses diet limits that complicate weight loss.",
    ),
    SelectedGuideline(
        row_idx=4038,
        doc_id="epfl_pubmed_ada_type1_diabetes_nutrition",
        title="ADA Type 1 Diabetes in Children and Adolescents",
        source_type="guideline",
        publisher="American Diabetes Association",
        disease_focus=["diabetes"],
        nutrition_focus=["medical_nutrition_therapy", "carbohydrate_counting", "exercise"],
        evaluation_labels=["external_smoke", "should_extract"],
        notes="ADA row has explicit nutrition therapy and carbohydrate-monitoring recommendations.",
    ),
]

FOCUS_TERMS = [
    "nutrition therapy",
    "medical nutrition therapy",
    "nutrition",
    "dietary",
    "diet",
    "food",
    "healthy eating",
    "carbohydrate",
    "protein",
    "potassium",
    "phosphorus",
    "sodium",
    "salt",
    "fluid",
    "target weight",
    "physical activity",
    "weight loss",
    "weight management",
    "obesity",
    "diabetes",
    "kidney",
]


def fetch_row(row_idx: int) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "dataset": "epfl-llm/guidelines",
            "config": "default",
            "split": "train",
            "offset": str(row_idx),
            "length": "1",
        }
    )
    with urllib.request.urlopen(f"{DATASET_API}?{params}", timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload.get("rows") or []
    if not rows:
        raise RuntimeError(f"No row returned for row_idx={row_idx}")
    returned_idx = rows[0].get("row_idx")
    if returned_idx != row_idx:
        raise RuntimeError(f"Expected row_idx={row_idx}, got {returned_idx}")
    return rows[0]["row"]


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def excerpt_windows(text: str, terms: list[str], *, window: int = 520, max_windows: int = 4) -> list[str]:
    windows: list[tuple[int, int]] = []
    lower = text.lower()
    for term in terms:
        pos = lower.find(term.lower())
        if pos < 0:
            continue
        start = max(0, pos - window // 2)
        end = min(len(text), pos + len(term) + window)
        if any(abs(start - previous_start) < 300 for previous_start, _ in windows):
            continue
        windows.append((start, end))
        if len(windows) >= max_windows:
            break
    if not windows:
        windows.append((0, min(len(text), window * 2)))
    return [normalize_space(text[start:end]) for start, end in windows if normalize_space(text[start:end])]


def yaml_list(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(value, ensure_ascii=False) for value in values) + "]"


def render_source_card(selected: SelectedGuideline, row: dict[str, Any]) -> str:
    source = row.get("source") or "unknown"
    row_title = row.get("title") or selected.title
    source_url = row_url(row, selected.row_idx)
    text = row.get("clean_text") or row.get("raw_text") or ""
    overview = normalize_space(row.get("overview") or "")
    windows = excerpt_windows(text, FOCUS_TERMS)
    bullets = "\n".join(f"- Excerpt window {index}: {window}" for index, window in enumerate(windows, start=1))
    if overview:
        bullets = f"- Dataset overview: {overview}\n{bullets}"
    return f"""---
doc_id: {selected.doc_id}
title: {json.dumps(selected.title, ensure_ascii=False)}
language: en
source_type: {selected.source_type}
source_url: {json.dumps(source_url, ensure_ascii=False)}
publisher: {json.dumps(selected.publisher, ensure_ascii=False)}
year: "unknown"
disease_focus: {yaml_list(selected.disease_focus)}
nutrition_focus: {yaml_list(selected.nutrition_focus)}
evaluation_labels: {yaml_list(selected.evaluation_labels)}
annotation_method: external_dataset_sample
source_dataset: epfl-llm/guidelines
source_dataset_row_idx: "{selected.row_idx}"
source_dataset_row_id: {json.dumps(row.get("id") or "", ensure_ascii=False)}
source_dataset_source: {json.dumps(source, ensure_ascii=False)}
review_status: unreviewed
failure_is_valid_observation: false
copyright_mode: short_excerpt_windows
notes: {json.dumps(selected.notes, ensure_ascii=False)}
---

# {selected.title}

## Source Notes

This source card was generated from the public HuggingFace dataset `epfl-llm/guidelines`, row index {selected.row_idx}.
Original row title: {row_title}
Original row source: {source}

The card keeps short focus windows rather than the full guideline text so the external smoke dataset remains small and auditable.

## Extractable Source Content

{bullets}

## Copyright Handling

This card stores short excerpt windows selected for research smoke testing and links back to the dataset/source row instead of vendoring the full guideline.
"""


def row_url(row: dict[str, Any], row_idx: int) -> str:
    url = str(row.get("url") or "").strip()
    if url and url.lower() != "none":
        return url
    return f"{HF_DATASET_URL}?row={row_idx}"


def manifest_row(selected: SelectedGuideline, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": selected.doc_id,
        "path": f"knowledge/source_documents/external_epfl_guidelines/{selected.doc_id}.md",
        "title": selected.title,
        "language": "en",
        "source_type": selected.source_type,
        "source_url": row_url(row, selected.row_idx),
        "publisher": selected.publisher,
        "year": "unknown",
        "disease_focus": selected.disease_focus,
        "nutrition_focus": selected.nutrition_focus,
        "evaluation_labels": selected.evaluation_labels,
        "annotation_method": "external_dataset_sample",
        "review_status": "unreviewed",
        "failure_is_valid_observation": False,
        "copyright_mode": "short_excerpt_windows",
        "source_dataset": "epfl-llm/guidelines",
        "source_dataset_row_idx": selected.row_idx,
        "source_dataset_row_id": row.get("id") or "",
        "source_dataset_source": row.get("source") or "",
        "notes": selected.notes,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    for selected in SELECTED_ROWS:
        row = fetch_row(selected.row_idx)
        (SOURCE_DIR / f"{selected.doc_id}.md").write_text(
            render_source_card(selected, row), encoding="utf-8"
        )
        manifest_rows.append(manifest_row(selected, row))
        selection_rows.append(
            {
                "doc_id": selected.doc_id,
                "row_idx": selected.row_idx,
                "row_id": row.get("id") or "",
                "source": row.get("source") or "",
                "source_url": row_url(row, selected.row_idx),
                "clean_text_chars": len(row.get("clean_text") or ""),
                "selection_reason": selected.notes,
            }
        )

    write_jsonl(DATASET_DIR / "manifest.jsonl", manifest_rows)
    write_jsonl(DATASET_DIR / "selection_manifest.jsonl", selection_rows)
    for empty_name in [
        "expected_rules.jsonl",
        "gold_evaluation_set.jsonl",
        "challenge_set.jsonl",
        "extraction_observations.jsonl",
    ]:
        (DATASET_DIR / empty_name).write_text("", encoding="utf-8")

    (DATASET_DIR / "README.zh.md").write_text(
        textwrap.dedent(
            f"""\
            # rule_extraction_epfl_guidelines_smoke

            这个数据集是从 HuggingFace `epfl-llm/guidelines` 的公开 `open_guidelines.jsonl`
            子集中抽样得到的外部烟测集。它的目标不是替代 `rule_extraction_v1` 的金标评测，
            而是用来源、版式、主题都不同的真实英文指南文本检查规则抽取实验管线是否稳健。

            ## 数据来源

            - 上游数据集：{HF_DATASET_URL}
            - 读取方式：HuggingFace dataset viewer API，固定 row index 抽样。
            - 本仓库只保存短 excerpt windows，不保存完整上游 JSONL。

            ## 选择标准

            - 与 MediDiet 当前研究范围相关：肥胖、糖尿病、CKD、营养治疗、饮食模式、
              体重/液体管理或公共卫生营养。
            - 优先选择 CMA、NICE、ADA/PubMed、CDC 等来源中具备 guideline/position statement
              语境的行。
            - 排除明显不属于当前研究范围的肿瘤治疗、职业化学暴露、疫苗、传染病控制等主题。

            ## 文件说明

            - `manifest.jsonl`：实验平台入口，声明 source card、主题标签和来源元数据。
            - `selection_manifest.jsonl`：记录每个 source card 对应的上游 row index、row id 和选择理由。
            - `expected_rules.jsonl`、`gold_evaluation_set.jsonl`、`challenge_set.jsonl`：当前为空。
              这表示该数据集先用于外部 smoke/观察，不用于准确率或 F1 结论。
            - `extraction_observations.jsonl`：预留给 `--append-observations` 的真实 LLM 观察记录。

            ## 适用范围

            适合回答：外部指南文本进入当前框架后，dry-run、chunking、LLM 抽取、
            稳定性摘要和报告生成是否正常。

            不适合回答：模型抽取准确率是否达到某个阈值。因为本数据集尚未冻结人工 gold。
            """
        ),
        encoding="utf-8",
    )

    print(f"Wrote {len(manifest_rows)} source cards to {SOURCE_DIR}")
    print(f"Wrote dataset manifest to {DATASET_DIR / 'manifest.jsonl'}")


if __name__ == "__main__":
    main()
