"""A pretend agent for the tests: it copies the reference solution for the task named in the prompt."""
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
prompt = sys.argv[1]
for task in (REPO / "tasks").iterdir():
    if task.is_dir() and task.name in prompt:
        for f in (task / "solution").iterdir():
            shutil.copy2(f, Path.cwd() / task.name / f.name)
        print(f"solved {task.name}")
        break
