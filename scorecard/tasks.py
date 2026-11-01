"""Load task definitions from the tasks/ folder."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .paths import TASKS_DIR


@dataclass(frozen=True)
class Task:
    number: int
    id: str
    title: str
    skill: str
    summary: str
    prompt: str

    @property
    def workspace(self) -> Path:
        return TASKS_DIR / self.id / "workspace"

    @property
    def solution(self) -> Path:
        return TASKS_DIR / self.id / "solution"


def load_tasks() -> list[Task]:
    tasks = []
    for meta in sorted(TASKS_DIR.glob("*/task.json")):
        data = json.loads(meta.read_text(encoding="utf-8"))
        tasks.append(Task(**data))
    return sorted(tasks, key=lambda t: t.number)


def select(tasks: list[Task], spec: str | None) -> list[Task]:
    if not spec:
        return tasks
    wanted = {int(x) for x in spec.replace(" ", "").split(",") if x}
    chosen = [t for t in tasks if t.number in wanted]
    if not chosen:
        raise SystemExit(f"No tasks match '{spec}'. Use numbers 1 to {len(tasks)}.")
    return chosen


def copy_workspace(task: Task, run_dir: Path) -> Path:
    """Copy one task's starting files into a run folder."""
    dest = run_dir / task.id
    shutil.copytree(task.workspace, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dest


def apply_solution(task: Task, task_dir: Path) -> None:
    """Copy the reference solution over a task folder (used by selftest)."""
    for f in task.solution.iterdir():
        shutil.copy2(f, task_dir / f.name)
