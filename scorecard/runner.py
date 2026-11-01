"""Run the tasks against an agent and score them."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from . import term
from .checks import CHECKERS
from .system import RamSampler, machine_info
from .tasks import Task, copy_workspace

SCHEMA = 1


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "agent"


def new_run_dir(root: Path, agent: str, repeat: int | None = None) -> Path:
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    base = f"{slug(agent)}-{stamp}" + (f"-r{repeat}" if repeat else "")
    path = root / base
    n = 2
    while path.exists():
        path = root / f"{base}-{n}"
        n += 1
    return path


def prepare(tasks: list[Task], run_dir: Path) -> None:
    run_dir.mkdir(parents=True)
    for t in tasks:
        copy_workspace(t, run_dir)
    lines = ["# The prompts", "", "Paste each prompt into your agent, one at a time.", ""]
    for t in tasks:
        lines += [f"## Task {t.number}: {t.title}", "", t.prompt, ""]
    (run_dir / "PROMPTS.md").write_text("\n".join(lines), encoding="utf-8")


def score(task: Task, run_dir: Path) -> dict:
    checks = CHECKERS[task.id](run_dir / task.id)
    return {
        "number": task.number, "id": task.id, "title": task.title,
        "passed": all(c.ok for c in checks),
        "checks": [c.to_dict() for c in checks],
    }


# --------------------------------------------------------------------------
# Manual mode: a person pastes each prompt and presses Enter when done
# --------------------------------------------------------------------------

def run_manual(tasks: list[Task], run_dir: Path) -> list[dict]:
    results = []
    print()
    print(term.bold("Open your agent in this folder:"))
    print("  " + term.green(str(run_dir)))
    print(term.dim("  (cd into it first, so the agent works on these copies)"))
    print()
    term.ask(term.dim("Press Enter when your agent is open and ready... "))

    for i, t in enumerate(tasks, 1):
        print()
        term.rule(f"Task {t.number} · {i} of {len(tasks)}: {t.title}")
        term.box(t.prompt)
        copied = term.copy_to_clipboard(t.prompt)
        print(term.dim("Copied to your clipboard." if copied else "Copy the prompt above."))
        reply = term.ask(term.bold("Press Enter the moment you send it") + term.dim(" (or type s to skip) "))
        if reply.lower() == "s":
            res = score(t, run_dir)
            res.update(seconds=None, skipped=True, helped=False, peak_ram_gb=None, ram_added_gb=None)
            results.append(res)
            print(term.yellow("Skipped."))
            continue
        start = time.perf_counter()
        with RamSampler() as ram:
            print(term.dim("Timer running. Don't help the agent."))
            term.ask(term.bold("Press Enter when the agent says it's done... "))
        seconds = round(time.perf_counter() - start, 1)
        helped = term.ask(term.dim("Did you have to help it, answer a question, or fix something? (y/N) ")).lower().startswith("y")
        res = score(t, run_dir)
        res.update(seconds=seconds, skipped=False, helped=helped, **ram.result())
        results.append(res)
        _print_task_result(res)
    return results


# --------------------------------------------------------------------------
# Auto mode: run a command-line agent with each prompt
# --------------------------------------------------------------------------

def build_argv(template: str, prompt: str) -> list[str]:
    posix = os.name != "nt"
    parts = shlex.split(template, posix=posix)
    if not posix:
        parts = [p[1:-1] if len(p) > 1 and p[0] == p[-1] == '"' else p for p in parts]
    if not any("{prompt}" in p for p in parts):
        parts.append("{prompt}")
    argv = [p.replace("{prompt}", prompt) for p in parts]
    exe = shutil.which(argv[0])
    if exe:
        argv[0] = exe
    return argv


def run_auto(tasks: list[Task], run_dir: Path, command: str, timeout: int) -> list[dict]:
    results = []
    logs = run_dir / ".scorecard-logs"
    logs.mkdir(exist_ok=True)
    for i, t in enumerate(tasks, 1):
        print()
        term.rule(f"Task {t.number} · {i} of {len(tasks)}: {t.title}")
        argv = build_argv(command, t.prompt)
        print(term.dim("Running: ") + " ".join(shlex.quote(a) if " " in a else a for a in argv[:1]) + term.dim(" ... (prompt sent as an argument)"))
        start = time.perf_counter()
        timed_out, code, output = False, None, ""
        with RamSampler() as ram:
            try:
                proc = subprocess.run(argv, cwd=run_dir, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace",
                                      timeout=timeout, stdin=subprocess.DEVNULL)
                code, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                output = str(exc.stdout or "") + str(exc.stderr or "")
            except FileNotFoundError:
                raise SystemExit(term.red(f"Can't find the command '{argv[0]}'. Is the agent installed and on your PATH?"))
        seconds = round(time.perf_counter() - start, 1)
        (logs / f"task{t.number}.log").write_text(output, encoding="utf-8")
        res = score(t, run_dir)
        res.update(seconds=seconds, skipped=False, helped=False, exit_code=code,
                   timed_out=timed_out, **ram.result())
        results.append(res)
        _print_task_result(res)
    return results


def _print_task_result(res: dict) -> None:
    secs = res.get("seconds")
    when = f"{secs / 60:.1f} min" if secs else ""
    extra = []
    if res.get("timed_out"):
        extra.append(term.red("timed out"))
    if res.get("helped"):
        extra.append(term.yellow("needed help"))
    print(f"{term.mark(res['passed'])}  {term.bold(res['title'])}  {term.dim(when)} {' '.join(extra)}")
    for c in res["checks"]:
        sign = term.green("✓") if c["ok"] else term.red("✗")
        print(f"   {sign} {c['name']}" + (term.dim(f"  {c['detail']}") if c["detail"] else ""))


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

def summarize(runs: list[dict]) -> dict:
    by_task: dict[str, list[bool]] = {}
    for run in runs:
        for t in run["tasks"]:
            by_task.setdefault(t["id"], []).append(t["passed"] and not t.get("helped"))
    attempts = sum(len(v) for v in by_task.values())
    passes = sum(sum(v) for v in by_task.values())
    first = runs[0]["tasks"]
    secs = [t["seconds"] for t in first if t.get("seconds")]
    peaks = [t["peak_ram_gb"] for r in runs for t in r["tasks"] if t.get("peak_ram_gb")]
    return {
        "tasks": len(by_task),
        "passed": sum(1 for t in first if t["passed"] and not t.get("helped")),
        "pass_rate": round(passes / attempts, 3) if attempts else 0,
        "passed_every_run": sum(1 for v in by_task.values() if all(v)),
        "minutes": round(sum(secs) / 60, 1) if secs else None,
        "peak_ram_gb": max(peaks) if peaks else None,
        "helped": sum(1 for t in first if t.get("helped")),
    }


def build_result(agent: str, model: str, mode: str, command: str | None, runs: list[dict]) -> dict:
    return {
        "schema": SCHEMA,
        "tool": agent,
        "model": model or "",
        "mode": mode,
        "command": command or "",
        "date": dt.date.today().isoformat(),
        "machine": machine_info(),
        "runs": runs,
        "summary": summarize(runs),
    }


def save_result(result: dict, run_dir: Path) -> Path:
    path = run_dir / "scorecard.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return path
