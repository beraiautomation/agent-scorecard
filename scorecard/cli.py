"""Command line: python -m scorecard <command>"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import webbrowser
from pathlib import Path

from . import __version__, term
from .leaderboard import update as update_leaderboard
from .paths import DEFAULT_RUNS_DIR, RESULTS_DIR
from .report import write_report
from .runner import (build_result, new_run_dir, prepare, run_auto, run_manual,
                     save_result, score, slug, summarize)
from .selftest import run_selftest
from .tasks import load_tasks, select


def cmd_tasks(_args) -> int:
    for t in load_tasks():
        print(f"{term.bold(str(t.number))}  {term.bold(t.title):<28} {term.dim(t.skill)}")
        print(f"   {t.summary}")
    return 0


def cmd_run(args) -> int:
    tasks = select(load_tasks(), args.tasks)
    root = Path(args.runs_dir).expanduser()
    repeats = max(1, args.repeat)
    if repeats > 1 and not args.cmd:
        raise SystemExit("--repeat needs --cmd. Repeats only make sense when the agent runs on its own.")

    print()
    term.rule(f"Agent Scorecard · {args.agent}")
    print(f"{len(tasks)} task(s)" + (f", {repeats} runs" if repeats > 1 else "") +
          ". Each run gets fresh copies of the starting files.")

    runs, first_dir = [], None
    for r in range(1, repeats + 1):
        run_dir = new_run_dir(root, args.agent, r if repeats > 1 else None)
        first_dir = first_dir or run_dir
        prepare(tasks, run_dir)
        if repeats > 1:
            print()
            print(term.bold(f"Run {r} of {repeats}") + term.dim(f"  {run_dir}"))
        if args.cmd:
            results = run_auto(tasks, run_dir, args.cmd, args.timeout)
        else:
            results = run_manual(tasks, run_dir)
        runs.append({"run": r, "folder": str(run_dir), "tasks": results})

    result = build_result(args.agent, args.model, "auto" if args.cmd else "manual", args.cmd, runs)
    save_result(result, first_dir)
    report = write_report(result, first_dir)
    _print_summary(result, first_dir, report)
    if not args.no_open:
        webbrowser.open(report.resolve().as_uri())
    return 0


def _print_summary(result: dict, run_dir: Path, report: Path) -> None:
    s = result["summary"]
    print()
    term.rule("Result")
    line = f"{term.bold(result['tool'])}: {term.bold(str(s['passed']))} of {s['tasks']} tasks passed"
    if len(result["runs"]) > 1:
        line += f", {s['passed_every_run']} passed every run ({round(s['pass_rate'] * 100)}% pass rate)"
    print(line)
    if s.get("minutes") is not None:
        print(term.dim(f"Total time {s['minutes']} min") +
              (term.dim(f" · peak RAM in use {s['peak_ram_gb']} GB") if s.get("peak_ram_gb") else ""))
    print()
    print("Report:  " + term.green(str(report)))
    print("Share it on the results table:  " + term.bold(f"python -m scorecard save \"{run_dir}\""))


def cmd_check(args) -> int:
    """Score a run folder again, keeping the times that were recorded."""
    run_dir = Path(args.run_dir).expanduser()
    saved = run_dir / "scorecard.json"
    tasks = {t.id: t for t in load_tasks()}
    if saved.exists():
        result = json.loads(saved.read_text(encoding="utf-8"))
        for run in result["runs"]:
            for t in run["tasks"]:
                fresh = score(tasks[t["id"]], Path(run["folder"]))
                t.update(passed=fresh["passed"], checks=fresh["checks"])
        result["summary"] = summarize(result["runs"])
    else:
        present = [t for t in tasks.values() if (run_dir / t.id).exists()]
        if not present:
            raise SystemExit(f"No task folders found in {run_dir}")
        found = [dict(score(t, run_dir), seconds=None, helped=False) for t in present]
        result = build_result(args.agent or run_dir.name, "", "manual", None,
                              [{"run": 1, "folder": str(run_dir), "tasks": found}])
    for t in result["runs"][0]["tasks"]:
        print(f"{term.mark(t['passed'])}  {t['title']}")
        for c in t["checks"]:
            if not c["ok"]:
                print(term.red(f"     ✗ {c['name']}") + term.dim(f"  {c['detail']}"))
    save_result(result, run_dir)
    report = write_report(result, run_dir)
    print("\nReport: " + term.green(str(report)))
    return 0


def cmd_save(args) -> int:
    run_dir = Path(args.run_dir).expanduser()
    src = run_dir / "scorecard.json"
    if not src.exists():
        raise SystemExit(f"No scorecard.json in {run_dir}. Run the tasks first.")
    result = json.loads(src.read_text(encoding="utf-8"))
    RESULTS_DIR.mkdir(exist_ok=True)
    name = f"{result['date']}-{slug(result['tool'])}" + (f"-{slug(result['model'])}" if result.get("model") else "")
    dest = RESULTS_DIR / f"{name}.json"
    n = 2
    while dest.exists():
        dest = RESULTS_DIR / f"{name}-{n}.json"
        n += 1
    shutil.copy2(src, dest)
    print("Saved " + term.green(str(dest)))
    print(update_leaderboard())
    return 0


def cmd_leaderboard(_args) -> int:
    print(update_leaderboard())
    return 0


def cmd_selftest(_args) -> int:
    return 0 if run_selftest() else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m scorecard",
        description="Test an AI coding agent on 5 real tasks. Every check is done by code.")
    p.add_argument("--version", action="version", version=f"agent-scorecard {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run the tasks against an agent")
    r.add_argument("--agent", required=True, help='name of the tool you test, e.g. "Hermes Agent"')
    r.add_argument("--model", default="", help='model it uses, e.g. "qwen3-coder:480b-cloud"')
    r.add_argument("--cmd", help='run a command-line agent on its own, e.g. "claude -p {prompt}"')
    r.add_argument("--tasks", help="only some tasks, e.g. 1,3")
    r.add_argument("--repeat", type=int, default=1, help="run everything N times in fresh folders (needs --cmd)")
    r.add_argument("--timeout", type=int, default=1200, help="seconds per task in auto mode (default 1200)")
    r.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR), help=f"where run folders go (default {DEFAULT_RUNS_DIR})")
    r.add_argument("--no-open", action="store_true", help="don't open the report when done")
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("check", help="score a run folder again")
    c.add_argument("run_dir")
    c.add_argument("--agent", help="name to show if the folder has no scorecard yet")
    c.set_defaults(func=cmd_check)

    s = sub.add_parser("save", help="add a run to the results table")
    s.add_argument("run_dir")
    s.set_defaults(func=cmd_save)

    sub.add_parser("tasks", help="list the tasks").set_defaults(func=cmd_tasks)
    sub.add_parser("leaderboard", help="rebuild the results table").set_defaults(func=cmd_leaderboard)
    sub.add_parser("selftest", help="check that the checkers work").set_defaults(func=cmd_selftest)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
