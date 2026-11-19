from __future__ import annotations

from pathlib import Path

import pytest

from aca.agent import Agent, Task, TestResult, extract_code
from aca.budget import Budget, BudgetExceeded
from aca.log import CallLog, read_records
from aca.policies import RunConfig
from aca.pricing import PriceTable, PricingError
from aca.providers.mock import MockProvider, estimate_tokens

OPUS = "claude-opus-5-5"
HAIKU = "claude-haiku-5-5"
SHORT_SYSTEM = "You are a careful Python engineer."
LONG_SYSTEM = "Follow the house coding conventions. " * 200  # clears the mock cache minimum
TASK = Task(task_id="interval_merge", prompt="Merge overlapping intervals.")


def scripted_tests(outcomes: list[bool]):
    """A fake test runner that returns the given pass/fail outcomes in order."""
    remaining = list(outcomes)
    seen_code: list[str] = []

    def run(task: Task, code: str) -> TestResult:
        seen_code.append(code)
        passed = remaining.pop(0)
        return TestResult(passed=passed, output="1 passed" if passed else "AssertionError: boom")

    run.seen_code = seen_code  # type: ignore[attr-defined]
    return run


def make_agent(
    tmp_path: Path,
    config: RunConfig,
    prices: PriceTable,
    outcomes: list[bool],
    *,
    provider: MockProvider | None = None,
    cap_usd: float = 5.0,
    system: str = SHORT_SYSTEM,
):
    provider = provider or MockProvider()
    budget = Budget(cap_usd)
    log_path = tmp_path / "calls.jsonl"
    agent = Agent(
        provider=provider,
        config=config,
        prices=prices,
        budget=budget,
        log=CallLog(log_path),
        system=system,
        run_tests=scripted_tests(outcomes),
        estimate_tokens=estimate_tokens,
    )
    return agent, provider, budget, log_path


def records(log_path: Path):
    return list(read_records(log_path)) if log_path.exists() else []


def test_pass_first_time_makes_two_calls(tmp_path, config, prices) -> None:
    agent, _, _, log_path = make_agent(tmp_path, config, prices, [True])
    run = agent.run_task(TASK, config.policy("routed"), run_id="r1", rep=0)

    assert run.passed and run.calls == 2
    assert run.fix_attempts == 0 and run.escalations == 0
    assert [(r.step, r.attempt, r.model) for r in records(log_path)] == [
        ("plan", 0, OPUS),
        ("write", 0, HAIKU),
    ]


def test_first_fix_stays_on_the_cheap_model(tmp_path, config, prices) -> None:
    agent, _, _, log_path = make_agent(tmp_path, config, prices, [False, True])
    run = agent.run_task(TASK, config.policy("routed"), run_id="r1", rep=0)

    assert run.passed and run.calls == 3
    assert run.fix_attempts == 1 and run.escalations == 0
    assert [(r.step, r.attempt, r.model) for r in records(log_path)][-1] == ("fix", 1, HAIKU)


def test_second_fix_escalates_to_the_strong_model(tmp_path, config, prices) -> None:
    agent, _, _, log_path = make_agent(tmp_path, config, prices, [False, False, True])
    run = agent.run_task(TASK, config.policy("routed"), run_id="r1", rep=0)

    assert run.passed and run.calls == 4
    assert run.fix_attempts == 2 and run.escalations == 1
    assert [(r.step, r.attempt, r.model) for r in records(log_path)] == [
        ("plan", 0, OPUS),
        ("write", 0, HAIKU),
        ("fix", 1, HAIKU),
        ("fix", 2, OPUS),
    ]


def test_gives_up_after_the_last_fix_attempt(tmp_path, config, prices) -> None:
    agent, _, _, _ = make_agent(tmp_path, config, prices, [False, False, False])
    run = agent.run_task(TASK, config.policy("routed"), run_id="r1", rep=0)

    assert not run.passed
    assert run.calls == 2 + config.max_fix_attempts


def test_single_model_policy_never_counts_an_escalation(tmp_path, config, prices) -> None:
    agent, _, _, log_path = make_agent(tmp_path, config, prices, [False, False, False])
    run = agent.run_task(TASK, config.policy("opus"), run_id="r1", rep=0)

    assert run.escalations == 0
    assert {r.model for r in records(log_path)} == {OPUS}


def test_fix_prompt_carries_the_failing_code_and_test_output(tmp_path, config, prices) -> None:
    agent, provider, _, _ = make_agent(tmp_path, config, prices, [False, True])
    agent.run_task(TASK, config.policy("routed"), run_id="r1", rep=0)

    fix_prompt = provider.calls[2]["messages"][0]["content"]
    assert "AssertionError: boom" in fix_prompt
    assert "def solution()" in fix_prompt
    assert TASK.prompt in fix_prompt


def test_cost_agrees_across_run_log_and_budget(tmp_path, config, prices) -> None:
    agent, _, budget, log_path = make_agent(tmp_path, config, prices, [False, False, True])
    run = agent.run_task(TASK, config.policy("routed"), run_id="r1", rep=0)

    logged = sum(r.cost_usd for r in records(log_path))
    assert run.cost_usd > 0
    assert run.cost_usd == pytest.approx(logged)
    assert budget.spent_usd == pytest.approx(logged)
    assert budget.reserved_usd == 0
    assert len(run.call_latencies_ms) == run.calls


def test_budget_cap_stops_before_the_call_is_made(tmp_path, config, prices) -> None:
    agent, provider, budget, log_path = make_agent(tmp_path, config, prices, [True], cap_usd=0.0001)
    with pytest.raises(BudgetExceeded):
        agent.run_task(TASK, config.policy("opus"), run_id="r1", rep=0)

    assert provider.calls == []  # nothing was sent
    assert records(log_path) == []
    assert budget.spent_usd == 0 and budget.reserved_usd == 0


def test_failed_provider_call_releases_its_reservation(tmp_path, config, prices) -> None:
    def explode(model, system, messages):
        raise RuntimeError("provider down")

    agent, _, budget, log_path = make_agent(
        tmp_path, config, prices, [True], provider=MockProvider(explode)
    )
    with pytest.raises(RuntimeError, match="provider down"):
        agent.run_task(TASK, config.policy("opus"), run_id="r1", rep=0)

    assert budget.reserved_usd == 0 and budget.spent_usd == 0
    assert records(log_path) == []


def test_call_served_by_an_unpriced_model_is_counted_at_worst_case(
    tmp_path, config, prices
) -> None:
    class SwappedModel(MockProvider):
        def complete(self, messages, system, cache, *, model, max_tokens):
            response = super().complete(messages, system, cache, model=model, max_tokens=max_tokens)
            return response.model_copy(update={"model": "some-unpriced-model"})

    agent, _, budget, _ = make_agent(tmp_path, config, prices, [True], provider=SwappedModel())
    with pytest.raises(PricingError):
        agent.run_task(TASK, config.policy("opus"), run_id="r1", rep=0)

    assert budget.reserved_usd == 0
    assert budget.spent_usd > 0.3  # the full worst-case reservation for one Opus call


def test_uncached_policy_never_touches_the_cache(tmp_path, config, prices) -> None:
    agent, _, _, log_path = make_agent(tmp_path, config, prices, [True, True], system=LONG_SYSTEM)
    for rep in range(2):
        agent.run_task(TASK, config.policy("routed"), run_id="r1", rep=rep)

    assert all(r.cache_write_tokens == 0 and r.cache_read_tokens == 0 for r in records(log_path))


def test_cache_is_written_once_per_model_then_read(tmp_path, config, prices) -> None:
    agent, _, _, log_path = make_agent(tmp_path, config, prices, [True, True], system=LONG_SYSTEM)
    for rep in range(2):
        agent.run_task(TASK, config.policy("routed_cached"), run_id="r1", rep=rep)

    first_plan, first_write, second_plan, second_write = records(log_path)
    # Each model has its own cache entry, so both first calls pay a write.
    assert first_plan.model == OPUS and first_plan.cache_write_tokens > 0
    assert first_write.model == HAIKU and first_write.cache_write_tokens > 0
    assert second_plan.cache_read_tokens == first_plan.cache_write_tokens
    assert second_write.cache_read_tokens == first_write.cache_write_tokens
    assert second_plan.cost_usd < first_plan.cost_usd


def test_system_prompt_below_the_minimum_is_not_cached(tmp_path, config, prices) -> None:
    agent, _, _, log_path = make_agent(tmp_path, config, prices, [True], system=SHORT_SYSTEM)
    agent.run_task(TASK, config.policy("routed_cached"), run_id="r1", rep=0)

    assert all(r.cache_write_tokens == 0 and r.cache_read_tokens == 0 for r in records(log_path))


def test_extract_code_takes_the_last_fenced_block() -> None:
    reply = "First try:\n```python\nx = 1\n```\nBetter:\n```python\nx = 2\n```\nDone."
    assert extract_code(reply) == "x = 2\n"


def test_extract_code_accepts_an_unlabelled_fence() -> None:
    assert extract_code("```\nprint('hi')\n```") == "print('hi')\n"


def test_extract_code_falls_back_to_the_whole_reply() -> None:
    assert extract_code("def f():\n    return 1") == "def f():\n    return 1\n"
