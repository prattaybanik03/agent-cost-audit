"""The JSONL call log: one line per model call.

The log holds counts, timings and costs. It never holds prompt or response text.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Step = Literal["plan", "write", "fix"]


def utc_now() -> datetime:
    return datetime.now(UTC)


class CallRecord(BaseModel):
    run_id: str
    task_id: str
    policy: str
    rep: int = Field(ge=0)
    """Which repetition of this task and policy the call belongs to."""
    attempt: int = Field(ge=0)
    """0 for plan and write. 1, 2, ... for each fix attempt."""
    step: Step
    provider: str
    model: str
    """The model that served the call."""
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_write_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    cost_usd: float = Field(ge=0)
    stop_reason: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)


class CallLog:
    """Appends call records to a JSONL file. Safe to share between threads."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, record: CallRecord) -> None:
        line = record.model_dump_json()
        with self._lock, open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def read_records(path: str | Path) -> Iterator[CallRecord]:
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield CallRecord.model_validate_json(line)
