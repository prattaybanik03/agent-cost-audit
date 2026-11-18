from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aca.log import CallLog, CallRecord, read_records


def make_record(**overrides) -> CallRecord:
    fields = {
        "run_id": "run-1",
        "task_id": "lru_cache",
        "policy": "routed",
        "rep": 0,
        "attempt": 0,
        "step": "plan",
        "provider": "mock",
        "model": "claude-opus-5-5",
        "input_tokens": 1200,
        "output_tokens": 300,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "latency_ms": 850.5,
        "cost_usd": 0.0108,
    }
    fields.update(overrides)
    return CallRecord(**fields)


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "raw" / "calls.jsonl"  # parent directory does not exist yet
    log = CallLog(path)
    first = make_record()
    second = make_record(step="write", model="claude-haiku-5-5", cost_usd=0.0002)
    log.append(first)
    log.append(second)

    assert list(read_records(path)) == [first, second]


def test_one_json_object_per_line(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    log = CallLog(path)
    for attempt in range(3):
        log.append(make_record(step="fix", attempt=attempt + 1))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert [json.loads(line)["attempt"] for line in lines] == [1, 2, 3]


def test_log_schema_holds_no_prompt_or_response_text() -> None:
    """The schema is the contract for `aca ingest`. It must stay free of prompt text."""
    assert set(CallRecord.model_fields) == {
        "run_id",
        "task_id",
        "policy",
        "rep",
        "attempt",
        "step",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "cache_write_tokens",
        "cache_read_tokens",
        "latency_ms",
        "cost_usd",
        "stop_reason",
        "timestamp",
    }


def test_timestamp_is_timezone_aware() -> None:
    assert make_record().timestamp.tzinfo is not None


def test_invalid_records_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_record(step="deploy")
    with pytest.raises(ValidationError):
        make_record(input_tokens=-1)
    with pytest.raises(ValidationError):
        make_record(cost_usd=-0.01)
