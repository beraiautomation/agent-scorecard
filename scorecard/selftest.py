"""Prove the checkers work: starting files must fail, reference solutions must pass."""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import term
from .runner import score
from .tasks import apply_solution, copy_workspace, load_tasks


def run_selftest(verbose: bool = True) -> bool:
    ok_all = True
    with tempfile.TemporaryDirectory() as tmp:
        for task in load_tasks():
            before_dir, after_dir = Path(tmp) / "before", Path(tmp) / "after"
            before_dir.mkdir(exist_ok=True)
            after_dir.mkdir(exist_ok=True)
            copy_workspace(task, before_dir)
            copy_workspace(task, after_dir)
            apply_solution(task, after_dir / task.id)
            untouched = score(task, before_dir)["passed"]
            solved = score(task, after_dir)
            good = (not untouched) and solved["passed"]
            ok_all &= good
            if verbose:
                print(f"{term.mark(good)}  Task {task.number}: starting files fail = {not untouched}, "
                      f"reference solution passes = {solved['passed']}")
                if not solved["passed"]:
                    for c in solved["checks"]:
                        if not c["ok"]:
                            print(term.red(f"     ✗ {c['name']}: {c['detail']}"))
    if verbose:
        print()
        print(term.green("All checkers work.") if ok_all else term.red("Selftest failed."))
    return ok_all
