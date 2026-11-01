"""Write a self-contained HTML report for one scorecard result."""
from __future__ import annotations

from html import escape
from pathlib import Path

REPO_URL = "https://github.com/beraiautomation/agent-scorecard"

CSS = """
:root{--bg:#f7f6f3;--card:#fff;--ink:#1c1b22;--muted:#6b6878;--line:#e6e3ec;--pass:#0f9f6e;--pass-bg:#e5f6ef;
--fail:#d93a52;--fail-bg:#fdecef;--warn:#b7791f;--accent:#6d28d9;--accent2:#db2777}
@media (prefers-color-scheme:dark){:root{--bg:#121117;--card:#1b1a22;--ink:#f1eff7;--muted:#a19dae;--line:#2c2a36;
--pass:#34d399;--pass-bg:#10291f;--fail:#fb7185;--fail-bg:#33161d;--warn:#fbbf24;--accent:#a78bfa;--accent2:#f472b6}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:920px;margin:0 auto;padding:40px 20px 60px}
.kick{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:600}
h1{font-size:34px;line-height:1.1;margin:6px 0 4px;letter-spacing:-.02em}
h1 span{background:linear-gradient(90deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;color:transparent}
.sub{color:var(--muted);margin:0}
.hero{display:grid;grid-template-columns:auto 1fr;gap:28px;align-items:center;background:var(--card);border:1px solid var(--line);
border-radius:20px;padding:26px 28px;margin:26px 0}
.ring{position:relative;width:150px;height:150px}
.ring svg{transform:rotate(-90deg)}
.ring .n{position:absolute;inset:0;display:grid;place-items:center;text-align:center}
.ring b{font-size:40px;line-height:1;letter-spacing:-.03em}.ring small{display:block;color:var(--muted);font-size:12px;margin-top:4px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
.stat{border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.stat small{display:block;color:var(--muted);font-size:12px}.stat b{font-size:20px}
.tasks{display:grid;gap:12px}
.task{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.top{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.num{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;font-weight:700;font-size:14px;background:var(--line)}
.title{font-weight:650;font-size:16px}.skill{color:var(--muted);font-size:13px}
.pill{margin-left:auto;font-weight:700;font-size:12px;letter-spacing:.06em;padding:4px 10px;border-radius:999px}
.pill.pass{color:var(--pass);background:var(--pass-bg)}.pill.fail{color:var(--fail);background:var(--fail-bg)}
.meta{color:var(--muted);font-size:13px;margin:6px 0 8px 42px}
.meta .warn{color:var(--warn);font-weight:600}
ul{list-style:none;margin:0 0 0 42px;padding:0}
li{display:flex;gap:8px;font-size:14px;padding:3px 0;border-top:1px dashed var(--line)}
li:first-child{border-top:0}
li i{font-style:normal;font-weight:700;width:16px;flex:none}
li.ok i{color:var(--pass)}li.no i{color:var(--fail)}
li span{color:var(--muted)}
.runs{color:var(--muted);font-size:13px;margin:-4px 0 14px}
footer{margin-top:28px;color:var(--muted);font-size:13px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
footer a{color:var(--accent)}
@media (max-width:620px){.hero{grid-template-columns:1fr;justify-items:center;text-align:center}.stats{width:100%;grid-template-columns:1fr 1fr}.meta,ul{margin-left:0}}
"""


def _ring(passed: int, total: int) -> str:
    r, c = 62, 2 * 3.14159 * 62
    frac = passed / total if total else 0
    color = "var(--pass)" if frac >= 0.8 else ("var(--warn)" if frac >= 0.4 else "var(--fail)")
    return (f'<div class="ring"><svg width="150" height="150" viewBox="0 0 150 150">'
            f'<circle cx="75" cy="75" r="{r}" fill="none" stroke="var(--line)" stroke-width="14"/>'
            f'<circle cx="75" cy="75" r="{r}" fill="none" stroke="{color}" stroke-width="14" stroke-linecap="round" '
            f'stroke-dasharray="{c * frac:.1f} {c:.1f}"/></svg>'
            f'<div class="n"><div><b>{passed}/{total}</b><small>tasks passed</small></div></div></div>')


def _stat(label: str, value: str) -> str:
    return f'<div class="stat"><small>{escape(label)}</small><b>{escape(value)}</b></div>'


def render(result: dict) -> str:
    s = result["summary"]
    m = result.get("machine", {})
    tool = escape(result["tool"])
    model = escape(result.get("model") or "")
    repeats = len(result["runs"])

    stats = [
        _stat("Total time", f"{s['minutes']} min" if s.get("minutes") is not None else "n/a"),
        _stat("Peak RAM in use", f"{s['peak_ram_gb']} GB" if s.get("peak_ram_gb") else "n/a"),
        _stat("Machine RAM", f"{m.get('ram_gb')} GB" if m.get("ram_gb") else "n/a"),
    ]
    if repeats > 1:
        stats.insert(0, _stat(f"Passed all {repeats} runs", f"{s['passed_every_run']}/{s['tasks']}"))
        stats.insert(1, _stat("Pass rate", f"{round(s['pass_rate'] * 100)}%"))
    if s.get("helped"):
        stats.append(_stat("Needed help", f"{s['helped']} task(s)"))

    cards = []
    for t in result["runs"][0]["tasks"]:
        ok = t["passed"] and not t.get("helped")
        meta = []
        if t.get("seconds"):
            meta.append(f"{t['seconds'] / 60:.1f} min")
        if t.get("ram_added_gb") is not None and t.get("peak_ram_gb"):
            meta.append(f"+{t['ram_added_gb']} GB RAM (peak {t['peak_ram_gb']} GB)")
        if t.get("helped"):
            meta.append('<span class="warn">needed help, so it counts as a fail</span>')
        if t.get("timed_out"):
            meta.append('<span class="warn">timed out</span>')
        if t.get("skipped"):
            meta.append('<span class="warn">skipped</span>')
        if repeats > 1:
            wins = sum(1 for r in result["runs"] for x in r["tasks"] if x["id"] == t["id"] and x["passed"])
            meta.append(f"passed {wins} of {repeats} runs")
        checks = "".join(
            f'<li class="{"ok" if c["ok"] else "no"}"><i>{"✓" if c["ok"] else "✗"}</i>'
            f'<div>{escape(c["name"])}{" <span>· " + escape(c["detail"]) + "</span>" if c.get("detail") else ""}</div></li>'
            for c in t["checks"])
        cards.append(
            f'<section class="task"><div class="top"><div class="num">{t["number"]}</div>'
            f'<div><div class="title">{escape(t["title"])}</div></div>'
            f'<div class="pill {"pass" if ok else "fail"}">{"PASS" if ok else "FAIL"}</div></div>'
            f'<div class="meta">{" · ".join(meta)}</div><ul>{checks}</ul></section>')

    machine = " · ".join(escape(str(x)) for x in [m.get("os"), m.get("cpu"),
                                                    f"{m.get('ram_gb')} GB RAM" if m.get("ram_gb") else None] if x)
    mode = "Run automatically" if result.get("mode") == "auto" else "Run by hand, timed with the scorecard"
    runs_line = f'<p class="runs">{repeats} runs, each in a fresh folder.</p>' if repeats > 1 else ""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{tool} scorecard</title><style>{CSS}</style></head><body><main>
<div class="kick">Agent Scorecard · {escape(result.get('date', ''))}</div>
<h1><span>{tool}</span></h1>
<p class="sub">{model + ' · ' if model else ''}{machine}</p>
<div class="hero">{_ring(s['passed'], s['tasks'])}<div class="stats">{''.join(stats)}</div></div>
{runs_line}
<div class="tasks">{''.join(cards)}</div>
<footer><span>{escape(mode)}. Every check is done by code, not by another AI.</span>
<a href="{REPO_URL}">agent-scorecard</a></footer>
</main></body></html>"""


def write_report(result: dict, run_dir: Path) -> Path:
    path = run_dir / "report.html"
    path.write_text(render(result), encoding="utf-8")
    return path
