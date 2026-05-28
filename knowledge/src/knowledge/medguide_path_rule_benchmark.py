from __future__ import annotations

import argparse
import http.client
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from knowledge.path_rule_evaluation import evaluate_medguide_rows


MEDGUIDE_DATASET = "MedGUIDE/MedGUIDE-MCQA-8K"
DATASET_ROWS_API = "https://datasets-server.huggingface.co/rows"


def fetch_medguide_rows(offset: int = 0, limit: int = 20, retry_attempts: int = 3) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "dataset": MEDGUIDE_DATASET,
            "config": "default",
            "split": "train",
            "offset": str(offset),
            "length": str(limit),
        }
    )
    url = f"{DATASET_ROWS_API}?{params}"
    last_error: Exception | None = None
    for attempt in range(retry_attempts):
        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return list(payload.get("rows", []))
        except (http.client.IncompleteRead, urllib.error.URLError) as exc:
            last_error = exc
            if attempt + 1 == retry_attempts:
                break
            time.sleep(0.5 * (attempt + 1))
    if last_error is not None:
        raise last_error
    payload = {"rows": []}
    return list(payload.get("rows", []))


def load_facts_jsonl(path: Path) -> dict[str, list[str]]:
    facts_by_sample_id: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sample_id = row["sample_id"]
        facts = row.get("facts") or row.get("matched_path") or []
        facts_by_sample_id[sample_id] = [str(item) for item in facts]
    return facts_by_sample_id


def write_medguide_path_rule_report(
    rows: list[dict[str, Any]],
    output_path: Path,
    facts_by_sample_id: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    report = evaluate_medguide_rows(rows, facts_by_sample_id=facts_by_sample_id)
    report = {
        "dataset_id": MEDGUIDE_DATASET,
        "run_type": "medguide_path_rule_benchmark",
        "mode": "external_facts" if facts_by_sample_id is not None else "oracle_path_facts",
        "autonomous_llm_answering": False,
        "note": (
            "external_facts mode evaluates deterministic rule matching from supplied patient facts; "
            "oracle_path_facts mode is a pipeline smoke test and must not be reported as model performance."
        ),
        **report,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--facts-jsonl", default="")
    parser.add_argument("--output", default="reports/medguide-path-rule-benchmark-report.json")
    args = parser.parse_args(argv)

    facts = load_facts_jsonl(Path(args.facts_jsonl)) if args.facts_jsonl else None
    rows = fetch_medguide_rows(offset=args.offset, limit=args.limit)
    report = write_medguide_path_rule_report(
        rows=rows,
        output_path=Path(args.output),
        facts_by_sample_id=facts,
    )
    print(json.dumps({key: report[key] for key in ("row_count", "answer_accuracy", "mode")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
