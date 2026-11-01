"""Build the results table from saved scorecards in results/."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .paths import REPO_DIR, RESULTS_DIR

START, END = "<!-- results:start -->", "<!-- results:end -->"


def load_results(folder: Path = RESULTS_DIR) -> list[dict]:
    out = []
    for f in sorted(folder.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        data["_file"] = f.name
        out.append(data)
    return out


def table(results: list[dict]) -> str:
    if not results:
        return "_No results yet. The first tests are on the way._"
    rows = sorted(results, key=lambda r: (-r["summary"]["passed"], r["summary"].get("minutes") or 1e9))
    lines = [
        "| Tool | Model | Passed | Time | Peak RAM | Machine | Date |",
        "|---|---|:---:|---:|---:|---|---|",
    ]
    for r in rows:
        s, m = r["summary"], r.get("machine", {})
        passed = f"**{s['passed']}/{s['tasks']}**"
        if len(r["runs"]) > 1:
            passed += f" ({s['passed_every_run']}/{s['tasks']} every run)"
        if s.get("helped"):
            passed += " ⚠️"
        machine = ", ".join(x for x in [m.get("os"), f"{m['ram_gb']} GB" if m.get("ram_gb") else ""] if x)
        lines.append(
            f"| {r['tool']} | {r.get('model') or ''} | {passed} | "
            f"{str(s['minutes']) + ' min' if s.get('minutes') is not None else ''} | "
            f"{str(s['peak_ram_gb']) + ' GB' if s.get('peak_ram_gb') else ''} | {machine} | {r.get('date', '')} |"
        )
    return "\n".join(lines)


def update(readme: Path = REPO_DIR / "README.md") -> str:
    block = table(load_results())
    text = readme.read_text(encoding="utf-8")
    if START in text and END in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), f"{START}\n{block}\n{END}", text, flags=re.S)
        readme.write_text(text, encoding="utf-8")
    return block
