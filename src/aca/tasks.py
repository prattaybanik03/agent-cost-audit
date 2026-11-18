"""Loads the workload from tasks/.

Each task is a folder holding prompt.md (sent to the model), test_task.py (the hidden tests)
and reference.py (a known-correct solution). A loaded `Task` carries the prompt and the tests
only. The reference solution is reachable solely through `reference_code`, which the run path
never calls, so it cannot leak into a prompt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from aca.agent import Task

TASKS_ROOT = Path("tasks")
Difficulty = Literal["easy", "medium", "hard"]


class TaskEntry(BaseModel):
    id: str
    difficulty: Difficulty
    title: str


def load_index(root: str | Path = TASKS_ROOT) -> list[TaskEntry]:
    with open(Path(root) / "index.yaml", encoding="utf-8") as handle:
        return [TaskEntry.model_validate(item) for item in yaml.safe_load(handle)["tasks"]]


def load_tasks(root: str | Path = TASKS_ROOT) -> list[Task]:
    root = Path(root)
    return [
        Task(
            task_id=entry.id,
            prompt=(root / entry.id / "prompt.md").read_text(encoding="utf-8"),
            test_code=(root / entry.id / "test_task.py").read_text(encoding="utf-8"),
            difficulty=entry.difficulty,
        )
        for entry in load_index(root)
    ]


def reference_code(task_id: str, root: str | Path = TASKS_ROOT) -> str:
    """The known-correct solution. For verifying the tests only."""
    return (Path(root) / task_id / "reference.py").read_text(encoding="utf-8")
