"""Where things live."""
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_DIR / "tasks"
RESULTS_DIR = REPO_DIR / "results"
DEFAULT_RUNS_DIR = Path.home() / "agent-scorecard-runs"
