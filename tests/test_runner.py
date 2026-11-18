from __future__ import annotations

import json
from pathlib import Path

from aca.agent import Task, TestResult
from aca.log import read_records
from aca.providers.mock import MockProvider, estimate_tokens
from aca.runner import pytest_counts, run_benchmark

TASKS = [
    Task(task_id="t_easy", prompt="Easy task.", test_code="", difficulty="easy"),
    Task(task_id="t_hard", prompt="Hard task.", test_code="", difficulty="hard"),
]


class ScriptedSandbox:
    """Passes a task on the first try if its ID contains 'easy', otherwise always fails."""

    name = "scripted"
    isolates_network = False

    def run(self, test_code: str, solution_code: str) -> TestResult:
        raise AssertionError("replaced per task below")


def make_runner(pass_ids: set[str]):
    def run(task: Task, code: str) -> TestResult:
        passed = task.task_id in pass_ids
        output = "3 passed in 0.1s" if passed else "1 failed, 2 passed in 0.1s"
        return TestResult(passed=passed, output=output)

    return run


def run(tmp_path: Path, config, prices, monkeypatch, *, cap=None, workers=3, reps=2):
    import aca.runner as runner_module

    monkeypatch.setattr(runner_module, "as_test_runner", lambda sandbox: make_runner({"t_easy"}))
    lines: list[str] = []
    summary = run_benchmark(
        provider=MockProvider(),
        config=config,
        prices=prices,
        tasks=TASKS,
        policies=[config.policy("opus"), config.policy("routed_cached")],
        repetitions=reps,
        sandbox=ScriptedSandbox(),
        estimate_tokens=estimate_tokens,
        out_root=tmp_path,
        workers=workers,
        budget_cap_usd=cap,
        run_id="test-run",
        echo=lines.append,
    )
    return summary, lines


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_full_run_writes_every_output(tmp_path, config, prices, monkeypatch) -> None:
    summary, lines = run(tmp_path, config, prices, monkeypatch)
    out = tmp_path / "test-run"

    assert summary.completed == summary.planned == 2 * 2 * 2
    assert summary.stopped_reason is None
    assert summary.passed_by_policy == {"opus": (2, 4), "routed_cached": (2, 4)}
    assert len(lines) == 8

    task_runs = read_jsonl(out / "task_runs.jsonl")
    assert len(task_runs) == 8
    assert {r["status"] for r in task_runs} == {"complete"}
    hard = [r for r in task_runs if r["task_id"] == "t_hard"]
    assert all(r["tests_passed"] == 2 and r["tests_failed"] == 1 for r in hard)

    calls = list(read_records(out / "calls.jsonl"))
    assert abs(sum(c.cost_usd for c in calls) - summary.spent_usd) < 1e-9
    assert sum(r["calls"] for r in task_runs) == len(calls)

    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "mock" and meta["token_counts"].startswith("estimated")
    assert meta["completed_task_runs"] == 8 and meta["refusal_fallback"] is False
    assert meta["prices"]["source_url"].startswith("https://")


def test_artifacts_hold_code_and_test_output(tmp_path, config, prices, monkeypatch) -> None:
    run(tmp_path, config, prices, monkeypatch, reps=1)
    folder = tmp_path / "test-run" / "artifacts" / "t_hard" / "routed_cached" / "rep0"
    names = sorted(path.name for path in folder.iterdir())
    assert names == [
        "0_write_haiku.py",
        "0_write_haiku.txt",
        "1_fix_haiku.py",
        "1_fix_haiku.txt",
        "2_fix_opus.py",
        "2_fix_opus.txt",
    ]


def test_call_log_holds_no_prompt_text(tmp_path, config, prices, monkeypatch) -> None:
    run(tmp_path, config, prices, monkeypatch, reps=1)
    text = (tmp_path / "test-run" / "calls.jsonl").read_text(encoding="utf-8")
    assert "Hard task." not in text and "Pipeline label" not in text


def test_budget_cap_stops_the_run_cleanly(tmp_path, config, prices, monkeypatch) -> None:
    # A call reserves its full output allowance plus the prompt at the dearest rate. A cap just
    # above one Opus reservation admits calls until about $0.06 has actually been spent.
    one_call = prices.worst_case_usd("claude-opus-5-5", 2500, config.max_tokens)
    cap = one_call + 0.06
    summary, _ = run(tmp_path, config, prices, monkeypatch, cap=cap, workers=1)
    out = tmp_path / "test-run"

    assert summary.stopped_reason and summary.stopped_reason.startswith("budget")
    assert 0 < summary.completed < summary.planned
    assert summary.spent_usd <= cap
    task_runs = read_jsonl(out / "task_runs.jsonl")
    assert any(r["status"] == "aborted" for r in task_runs)
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["stopped_reason"].startswith("budget")


def test_pytest_counts() -> None:
    assert pytest_counts("12 passed in 0.5s") == (12, 0)
    assert pytest_counts("3 failed, 9 passed in 1.0s") == (9, 3)
    assert pytest_counts("1 failed, 2 passed, 1 error in 0.3s") == (2, 2)
    assert pytest_counts("2 errors in 0.1s") == (0, 2)
    assert pytest_counts("Tests did not finish within 30 seconds.") == (0, 0)
