# Adding a task

A task has four parts.

```
tasks/6-your-task/
  task.json      number, id, title, skill, summary, prompt
  workspace/     the starting files the agent sees
  solution/      files that should pass (used by selftest, never shown to the agent)
```

And one checker function in `scorecard/checks.py`, added to the `CHECKERS` dict:

```python
def check_your_task(folder: Path) -> list[Check]:
    out = folder / "answer.txt"
    if not out.exists():
        return [Check("answer.txt exists", False, "no answer.txt")]
    return [Check("answer.txt exists", True), Check("answer is right", ...)]
```

## Rules for a good task

1. **The prompt reads like a normal request.** No hints about how it's checked.
2. **Check by code, never by another AI.** Every check must give the same answer every time.
3. **Check more than the agent can see.** Add hidden cases so special-casing the visible
   tests doesn't pass.
4. **Lock what shouldn't change.** If the agent must not edit a file, compare its hash.
5. **Be fair to style.** Accept different formats for the same right answer.
6. **Prove it.** `python -m scorecard selftest` must show the starting files fail and the
   solution passes. Add tests in `tests/` that try to game your checker.
