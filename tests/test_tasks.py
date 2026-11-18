from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

import pytest

from aca.agent import Task
from aca.sandbox import SubprocessSandbox
from aca.tasks import load_index, load_tasks, reference_code

TASKS_ROOT = Path(__file__).resolve().parents[1] / "tasks"
TASKS = load_tasks(TASKS_ROOT)
SANDBOX = SubprocessSandbox(timeout_s=60)

by_id = pytest.mark.parametrize("task", TASKS, ids=[task.task_id for task in TASKS])


def test_workload_shape() -> None:
    assert len(TASKS) == 10
    assert len({task.task_id for task in TASKS}) == 10
    assert Counter(task.difficulty for task in TASKS) == {"easy": 3, "medium": 4, "hard": 3}
    assert [entry.id for entry in load_index(TASKS_ROOT)] == [task.task_id for task in TASKS]


def test_a_task_carries_no_reference_solution() -> None:
    """The run path only ever sees Task objects, so the reference cannot reach a prompt."""
    assert {f.name for f in dataclasses.fields(Task)} == {
        "task_id",
        "prompt",
        "test_code",
        "difficulty",
    }


@by_id
def test_reference_solution_passes_the_hidden_tests(task: Task) -> None:
    result = SANDBOX.run(task.test_code, reference_code(task.task_id, TASKS_ROOT))
    assert result.passed, result.output


@by_id
def test_empty_solution_fails_the_hidden_tests(task: Task) -> None:
    assert not SANDBOX.run(task.test_code, "").passed


@by_id
def test_prompt_does_not_leak_the_tests_or_the_reference(task: Task) -> None:
    reference = reference_code(task.task_id, TASKS_ROOT)
    assert "solution.py" in task.prompt
    assert "def test_" not in task.prompt
    # No substantial line of the reference solution or the tests appears in the prompt.
    for source in (reference, task.test_code):
        for line in source.splitlines():
            stripped = line.strip()
            if len(stripped) >= 40:
                assert stripped not in task.prompt, stripped
