"""Runs the benchmark: every task, under every policy, for every repetition.

Output goes to results/raw/<run_id>/, which is gitignored:

- calls.jsonl      one line per model call (counts, timings, costs; no prompt text)
- task_runs.jsonl  one line per task x policy x repetition
- run_meta.json    the settings the run used, so it can be reproduced
- artifacts/       generated code and test output per attempt, for diagnosing failures

Task runs are spread across worker threads. Work is ordered repetition by repetition, so every
policy makes progress at the same pace and a run stopped early still covers every policy.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from aca import prompts
from aca.agent import Agent, Task, TaskRun, TestResult, TokenEstimator
from aca.budget import Budget, BudgetExceeded
from aca.log import CallLog
from aca.policies import Policy, RunConfig
from aca.pricing import PriceTable
from aca.providers.base import Provider
from aca.sandbox import Sandbox, SandboxError, as_test_runner

_COUNTS = re.compile(r"(\d+) (passed|failed|error|errors)\b")


def pytest_counts(output: str) -> tuple[int, int]:
    """(passed, failed) from pytest's summary line. Errors count as failures."""
    passed = failed = 0
    for number, word in _COUNTS.findall(output):
        if word == "passed":
            passed = int(number)
        else:
            failed += int(number)
    return passed, failed


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def git_commit() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return None
    return proc.stdout.strip() or None


@dataclass
class RunSummary:
    run_id: str
    out_dir: Path
    spent_usd: float
    completed: int
    planned: int
    stopped_reason: str | None = None
    passed_by_policy: dict[str, tuple[int, int]] = field(default_factory=dict)


class _Recorder:
    """Writes task-run records and per-attempt artifacts. Safe to share between threads."""

    def __init__(self, out_dir: Path) -> None:
        self.task_runs = out_dir / "task_runs.jsonl"
        self.artifacts = out_dir / "artifacts"
        self._lock = threading.Lock()
        self.last_result: dict[tuple[str, str, int], TestResult] = {}

    def on_test(
        self, run: TaskRun, step: str, attempt: int, short: str, code: str, result: TestResult
    ) -> None:
        folder = self.artifacts / run.task_id / run.policy / f"rep{run.rep}"
        folder.mkdir(parents=True, exist_ok=True)
        stem = f"{attempt}_{step}_{short}"
        (folder / f"{stem}.py").write_text(code, encoding="utf-8")
        (folder / f"{stem}.txt").write_text(result.output, encoding="utf-8")
        with self._lock:
            self.last_result[(run.task_id, run.policy, run.rep)] = result

    def write(self, run: TaskRun, status: str, error: str | None = None) -> None:
        record = asdict(run)
        record["status"] = status
        record["error"] = error
        result = self.last_result.get((run.task_id, run.policy, run.rep))
        tests_passed, tests_failed = pytest_counts(result.output) if result else (0, 0)
        record["tests_passed"] = tests_passed
        record["tests_failed"] = tests_failed
        with self._lock, open(self.task_runs, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")


def run_benchmark(
    *,
    provider: Provider,
    config: RunConfig,
    prices: PriceTable,
    tasks: list[Task],
    policies: list[Policy],
    repetitions: int,
    sandbox: Sandbox,
    estimate_tokens: TokenEstimator,
    out_root: Path,
    workers: int,
    budget_cap_usd: float | None = None,
    run_id: str | None = None,
    echo=print,
) -> RunSummary:
    config.check_priced(prices)
    run_id = run_id or new_run_id()
    out_dir = out_root / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    cap = budget_cap_usd if budget_cap_usd is not None else config.budget_cap_usd
    budget = Budget(cap)
    log = CallLog(out_dir / "calls.jsonl")
    recorder = _Recorder(out_dir)
    test_runner = as_test_runner(sandbox)

    agents = {
        policy.name: Agent(
            provider=provider,
            config=config,
            prices=prices,
            budget=budget,
            log=log,
            system=prompts.system_prompt(policy.name),
            run_tests=test_runner,
            estimate_tokens=estimate_tokens,
            on_test=recorder.on_test,
        )
        for policy in policies
    }
    work = [
        (rep, task, policy) for rep in range(repetitions) for task in tasks for policy in policies
    ]

    started_at = datetime.now(UTC)
    meta = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "provider": provider.name,
        "token_counts": "estimated (mock)" if provider.name == "mock" else "from API usage fields",
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "sandbox": sandbox.name,
        "sandbox_isolates_network": sandbox.isolates_network,
        "budget_cap_usd": cap,
        "repetitions": repetitions,
        "workers": workers,
        "max_tokens": config.max_tokens,
        "max_fix_attempts": config.max_fix_attempts,
        "effort": config.effort,
        "models": config.models,
        "baseline": config.baseline,
        "policies": [policy.model_dump() for policy in policies],
        "tasks": [{"id": task.task_id, "difficulty": task.difficulty} for task in tasks],
        "prices": prices.model_dump(mode="json"),
        "system_prompt_sha256": prompts.body_sha256(),
        "cache_ttl": "5m (default ephemeral)",
        "refusal_fallback": False,
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    stop = threading.Event()
    stop_reason: list[str] = []
    lock = threading.Lock()
    progress = {"done": 0}

    def one(rep: int, task: Task, policy: Policy) -> None:
        if stop.is_set():
            return
        try:
            run = agents[policy.name].run_task(task, policy, run_id=run_id, rep=rep)
        except BudgetExceeded as exc:
            with lock:
                if not stop.is_set():
                    stop_reason.append(f"budget: {exc}")
                stop.set()
            recorder.write(TaskRun(run_id, task.task_id, policy.name, rep), "aborted", "budget")
            return
        except SandboxError as exc:
            with lock:
                stop_reason.append(f"sandbox: {exc}")
                stop.set()
            recorder.write(TaskRun(run_id, task.task_id, policy.name, rep), "error", str(exc))
            return
        except Exception as exc:  # an API error the SDK could not retry away
            with lock:
                stop_reason.append(f"{type(exc).__name__}: {exc}")
                stop.set()
            message = f"{type(exc).__name__}: {exc}"
            recorder.write(TaskRun(run_id, task.task_id, policy.name, rep), "error", message)
            return
        recorder.write(run, "complete")
        with lock:
            progress["done"] += 1
            done = progress["done"]
        echo(
            f"[{done}/{len(work)}] rep {rep} {task.task_id:<18} {policy.name:<14} "
            f"{'PASS' if run.passed else 'fail'}  calls={run.calls} "
            f"esc={run.escalations}  ${run.cost_usd:.4f}  {run.wall_time_s:.1f}s  "
            f"spent ${budget.spent_usd:.3f}"
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(one, rep, task, policy) for rep, task, policy in work]:
            future.result()

    meta["finished_at"] = datetime.now(UTC).isoformat()
    meta["spent_usd"] = budget.spent_usd
    meta["completed_task_runs"] = progress["done"]
    meta["planned_task_runs"] = len(work)
    meta["stopped_reason"] = stop_reason[0] if stop_reason else None
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    passed: dict[str, list[int]] = {policy.name: [0, 0] for policy in policies}
    with open(recorder.task_runs, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["status"] == "complete":
                passed[record["policy"]][1] += 1
                passed[record["policy"]][0] += record["passed"]

    return RunSummary(
        run_id=run_id,
        out_dir=out_dir,
        spent_usd=budget.spent_usd,
        completed=progress["done"],
        planned=len(work),
        stopped_reason=meta["stopped_reason"],
        passed_by_policy={name: (p, n) for name, (p, n) in passed.items()},
    )
