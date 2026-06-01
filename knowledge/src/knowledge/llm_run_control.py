from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


def classify_provider_failure(label: str) -> str:
    normalized_label = label.lower()
    if "429" in normalized_label or "rate" in normalized_label:
        return "rate_limited"
    if "timeout" in normalized_label or "timed out" in normalized_label:
        return "timeout"
    if "remotedisconnected" in normalized_label or "remote end closed" in normalized_label:
        return "remote_disconnected"
    if "incompleteread" in normalized_label:
        return "incomplete_read"
    if "ssl" in normalized_label or "eof" in normalized_label:
        return "ssl_eof"
    if any(status_code in normalized_label for status_code in ("500", "502", "503", "504")):
        return "server_error"
    return "provider_error"


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    cooldown_seconds: float = 300.0
    consecutive_failures: int = 0
    opened_at_seconds: float | None = None

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at_seconds = None

    def record_failure(self, *, now_seconds: float) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.opened_at_seconds = now_seconds

    def should_pause(self, *, now_seconds: float) -> bool:
        if self.opened_at_seconds is None:
            return False
        return now_seconds - self.opened_at_seconds < self.cooldown_seconds


class RunCheckpoint:
    def __init__(self, path: Path):
        self.path = path
        self._completed = self._load_completed()

    def _load_completed(self) -> set[tuple[str, str, str]]:
        if not self.path.exists():
            return set()
        completed: set[tuple[str, str, str]] = set()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            checkpoint_row = json.loads(line)
            completed.add(
                (
                    str(checkpoint_row["experiment_id"]),
                    str(checkpoint_row["arm_id"]),
                    str(checkpoint_row["doc_id"]),
                )
            )
        return completed

    def is_completed(self, experiment_id: str, arm_id: str, doc_id: str) -> bool:
        return (experiment_id, arm_id, doc_id) in self._completed

    def record_completed(self, experiment_id: str, arm_id: str, doc_id: str) -> None:
        key = (experiment_id, arm_id, doc_id)
        if key in self._completed:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "experiment_id": experiment_id,
                        "arm_id": arm_id,
                        "doc_id": doc_id,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
        self._completed.add(key)
