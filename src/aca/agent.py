"""The agent loop: plan, write, test, fix. It is identical for every policy.

Each model call is stateless. The loop passes forward only text (the plan, the code, the test
output), so a step can be handed to a different model without replaying another model's turn.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from aca.budget import Budget
from aca.log import CallLog, CallRecord, Step
from aca.policies import Policy, RunConfig
from aca.pricing import PriceTable
from aca.providers.base import Message, Provider


@dataclass(frozen=True)
class Task:
    """One workload task. Only `prompt` is ever sent to a model."""

    task_id: str
    prompt: str
    test_code: str = ""
    """The hidden pytest file. Used by the sandbox, never shown to the model."""
    difficulty: str = ""


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # not a pytest test class

    passed: bool
    output: str
    timed_out: bool = False


TestRunner = Callable[[Task, str], TestResult]
"""Runs a task's hidden tests against generated code. The sandbox provides the real one."""

TokenEstimator = Callable[[str], int]
"""Estimates prompt tokens before a call. Used only for the budget check."""


@dataclass
class TaskRun:
    """The outcome of one task under one policy, for one repetition."""

    run_id: str
    task_id: str
    policy: str
    rep: int
    passed: bool = False
    calls: int = 0
    fix_attempts: int = 0
    escalations: int = 0
    cost_usd: float = 0.0
    wall_time_s: float = 0.0
    timed_out: bool = False
    call_latencies_ms: list[float] = field(default_factory=list)


_CODE_BLOCK = re.compile(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Return the last fenced code block in a reply, or the whole reply if there is none."""
    blocks = _CODE_BLOCK.findall(text)
    return (blocks[-1] if blocks else text).strip() + "\n"


def _plan_prompt(task: Task) -> str:
    return (
        "Here is a programming task.\n\n"
        f"<task>\n{task.prompt}\n</task>\n\n"
        "Write a short implementation plan: the approach, the data structures, and the edge "
        "cases the code must handle. Do not write the code yet."
    )


def _write_prompt(task: Task, plan: str) -> str:
    return (
        "Here is a programming task and an implementation plan for it.\n\n"
        f"<task>\n{task.prompt}\n</task>\n\n"
        f"<plan>\n{plan}\n</plan>\n\n"
        "Write the complete solution as a single Python module. "
        "Reply with one fenced python code block and nothing else."
    )


def _fix_prompt(task: Task, code: str, test_output: str) -> str:
    return (
        "Here is a programming task, a solution that fails its tests, and the test output.\n\n"
        f"<task>\n{task.prompt}\n</task>\n\n"
        f"<code>\n{code}</code>\n\n"
        f"<test_output>\n{test_output}\n</test_output>\n\n"
        "Fix the solution. Reply with the complete corrected module in one fenced python code "
        "block and nothing else."
    )


class Agent:
    """Runs tasks under a policy, logging and pricing every call against the budget."""

    def __init__(
        self,
        *,
        provider: Provider,
        config: RunConfig,
        prices: PriceTable,
        budget: Budget,
        log: CallLog,
        system: str,
        run_tests: TestRunner,
        estimate_tokens: TokenEstimator,
    ) -> None:
        self.provider = provider
        self.config = config
        self.prices = prices
        self.budget = budget
        self.log = log
        self.system = system
        self.run_tests = run_tests
        self.estimate_tokens = estimate_tokens

    def run_task(self, task: Task, policy: Policy, *, run_id: str, rep: int) -> TaskRun:
        """Run one task under one policy. Raises `BudgetExceeded` if the cap would be passed."""
        run = TaskRun(run_id=run_id, task_id=task.task_id, policy=policy.name, rep=rep)
        started = time.perf_counter()
        try:
            plan = self._call(run, policy, "plan", 0, policy.plan, _plan_prompt(task))
            reply = self._call(run, policy, "write", 0, policy.write, _write_prompt(task, plan))
            code = extract_code(reply)
            result = self.run_tests(task, code)

            for attempt, short in enumerate(policy.fix, start=1):
                if result.passed:
                    break
                run.fix_attempts += 1
                if short != policy.write:
                    run.escalations += 1
                prompt = _fix_prompt(task, code, result.output)
                code = extract_code(self._call(run, policy, "fix", attempt, short, prompt))
                result = self.run_tests(task, code)

            run.passed = result.passed
            run.timed_out = result.timed_out
        finally:
            run.wall_time_s = time.perf_counter() - started
        return run

    def _call(
        self, run: TaskRun, policy: Policy, step: Step, attempt: int, short: str, prompt: str
    ) -> str:
        model = self.config.model_id(short)
        messages: list[Message] = [{"role": "user", "content": prompt}]

        prompt_tokens = self.estimate_tokens(self.system) + self.estimate_tokens(prompt)
        worst_case = self.prices.worst_case_usd(model, prompt_tokens, self.config.max_tokens)
        reservation = self.budget.reserve(worst_case)
        try:
            response = self.provider.complete(
                messages,
                self.system,
                policy.cache,
                model=model,
                max_tokens=self.config.max_tokens,
            )
        except BaseException:
            self.budget.release(reservation)
            raise

        cost = self.prices.cost_usd(response.model, response.usage)
        self.budget.settle(reservation, cost)
        self.log.append(
            CallRecord(
                run_id=run.run_id,
                task_id=run.task_id,
                policy=policy.name,
                rep=run.rep,
                attempt=attempt,
                step=step,
                provider=self.provider.name,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_write_tokens=response.usage.cache_write_tokens,
                cache_read_tokens=response.usage.cache_read_tokens,
                latency_ms=response.latency_ms,
                cost_usd=cost,
                stop_reason=response.stop_reason,
            )
        )
        run.calls += 1
        run.cost_usd += cost
        run.call_latencies_ms.append(response.latency_ms)
        return response.text
