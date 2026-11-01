"""Checkers for the five tasks.

Every checker takes the task folder inside a run (for example
``~/agent-scorecard-runs/hermes-2026-11-01-0930/1-fix-bug``) and returns a list
of ``Check`` results. A task passes only when every check passes.

The checkers are stricter than the files the agent can see. Task 1 and task 5
run hidden tests on top of the visible ones, so an agent can't pass by
special-casing the visible tests.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import runpy
import subprocess
import sys
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from pathlib import Path

from .paths import TASKS_DIR


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unchanged(run_file: Path, original: Path, label: str) -> Check:
    if not run_file.exists():
        return Check(f"{label} not changed", False, f"{run_file.name} was deleted")
    same = _sha(run_file) == _sha(original)
    return Check(f"{label} not changed", same, "" if same else f"{run_file.name} was edited")


def _load_function(py_file: Path, name: str):
    """Run a module file in a clean namespace and return one function from it."""
    sys.dont_write_bytecode = True
    namespace = runpy.run_path(str(py_file), run_name="scorecard_target")
    fn = namespace.get(name)
    if not callable(fn):
        raise AttributeError(f"{py_file.name} has no function named {name}()")
    return fn


def _run_visible_tests(folder: Path, test_file: str) -> Check:
    try:
        proc = subprocess.run(
            [sys.executable, "-B", test_file],
            cwd=folder, capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return Check("visible tests pass", False, "tests took longer than 60 seconds")
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+) of (\d+) tests passed", out)
    ok = proc.returncode == 0 and m is not None and m.group(1) == m.group(2)
    detail = m.group(0) if m else (out.strip().splitlines() or ["no output"])[-1][:160]
    return Check("visible tests pass", ok, detail)


# --------------------------------------------------------------------------
# Task 1: fix a bug
# --------------------------------------------------------------------------

def _cart_reference(items, code=None):
    subtotal = sum(i["price"] * i["qty"] for i in items)
    shipping = 0 if subtotal >= 50 else 5
    if code == "SAVE10":
        subtotal *= 0.9
    return round(subtotal + shipping, 2)


CART_HIDDEN_CASES = [
    ("empty cart pays shipping", [], None),
    ("free shipping is decided before the discount", [{"price": 52.0, "qty": 1}], "SAVE10"),
    ("discount under 50 still pays shipping", [{"price": 45.0, "qty": 1}], "SAVE10"),
    ("cents add up correctly", [{"price": 9.99, "qty": 3}], None),
    ("three items with a code", [{"price": 12.5, "qty": 2}, {"price": 4.0, "qty": 3}, {"price": 1.25, "qty": 4}], "SAVE10"),
    ("quantity of zero", [{"price": 99.0, "qty": 0}, {"price": 10.0, "qty": 1}], None),
    ("large order", [{"price": 250.0, "qty": 4}], "SAVE10"),
]


def check_fix_bug(folder: Path) -> list[Check]:
    original = TASKS_DIR / "1-fix-bug" / "workspace"
    checks = [_unchanged(folder / "test_cart.py", original / "test_cart.py", "test_cart.py")]
    checks.append(_run_visible_tests(folder, "test_cart.py"))
    try:
        cart_total = _load_function(folder / "cart.py", "cart_total")
    except Exception as exc:  # noqa: BLE001 - any import error is a fail
        checks.append(Check("hidden tests pass", False, f"could not load cart.py: {exc}"))
        return checks
    failed = []
    for label, items, code in CART_HIDDEN_CASES:
        want = _cart_reference(items, code)
        try:
            got = cart_total(items, code)
            if abs(got - want) > 0.001:
                failed.append(f"{label} (got {got}, want {want})")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{label} (error: {exc})")
    n = len(CART_HIDDEN_CASES)
    checks.append(Check("hidden tests pass", not failed,
                        f"{n - len(failed)} of {n} passed" + (": " + "; ".join(failed[:3]) if failed else "")))
    return checks


# --------------------------------------------------------------------------
# Task 2: build a web page
# --------------------------------------------------------------------------

class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.viewport = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and (a.get("name") or "").lower() == "viewport":
            self.viewport = True
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PRICE_RE = re.compile(r"[$£€]\s?\d{1,3}(?:[.,]\d{2})?|\b\d{1,3}[.,]\d{2}\b")
PHONE_RE = re.compile(r"\+?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}")
ADDRESS_RE = re.compile(
    r"\b(?:\d{1,5}\s+[A-Za-z][\w.'-]*(?:\s+[A-Za-z][\w.'-]*)*|[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*)\s+(?i:street|st|road|rd|avenue|ave|lane|ln|boulevard|blvd|way|drive|dr|square|sq|place|pl|court|ct)\b"
)


def _days_covered(text: str) -> set[str]:
    low = text.lower()
    found = set()
    for i, day in enumerate(DAYS):
        if re.search(rf"\b({day}|{day[:3]})\b", low):
            found.add(day)
    # Ranges such as "Mon - Fri" or "Monday to Friday" cover the days between.
    pat = r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\s*(?:-|–|—|to|through|thru)\s*(mon|tue|wed|thu|fri|sat|sun)[a-z]*"
    for a, b in re.findall(pat, low):
        ia = [d[:3] for d in DAYS].index(a)
        ib = [d[:3] for d in DAYS].index(b)
        span = range(ia, ib + 1) if ia <= ib else list(range(ia, 7)) + list(range(0, ib + 1))
        found.update(DAYS[j] for j in span)
    return found


def check_build_page(folder: Path) -> list[Check]:
    page = folder / "index.html"
    if not page.exists():
        return [Check("index.html exists", False, "no index.html in 2-build-page")]
    html = page.read_text(encoding="utf-8", errors="replace")
    parser = _PageParser()
    parser.feed(html)
    text = " ".join(" ".join(parser.text).split())
    low = text.lower()

    checks = [Check("index.html exists", True, f"{len(html):,} bytes")]
    has_name = "bean there" in low
    checks.append(Check("shows the shop name", has_name))

    prices = PRICE_RE.findall(text)
    checks.append(Check("menu has 4+ prices", len(prices) >= 4, f"{len(prices)} prices found"))

    days = _days_covered(text)
    missing = [d.title() for d in DAYS if d not in days]
    checks.append(Check("hours for all 7 days", not missing,
                        "all days covered" if not missing else "missing: " + ", ".join(missing)))

    phone = PHONE_RE.search(text)
    address = ADDRESS_RE.search(text)
    checks.append(Check("has a phone number", phone is not None, phone.group(0) if phone else ""))
    checks.append(Check("has a street address", address is not None, address.group(0) if address else ""))

    mobile = parser.viewport or "@media" in html
    checks.append(Check("works on phones", mobile,
                        "viewport meta tag" if parser.viewport else ("media query" if mobile else "no viewport tag or media query")))

    # The four sections must come in the order the brief asks for.
    positions = {
        "name": low.find("bean there"),
        "menu": (PRICE_RE.search(text).start() if prices else -1),
        "hours": min((m.start() for d in DAYS for m in [re.search(rf"\b({d}|{d[:3]})\b", low)] if m), default=-1),
        "contact": (phone.start() if phone else -1),
    }
    order = [positions[k] for k in ("name", "menu", "hours", "contact")]
    in_order = all(p >= 0 for p in order) and order == sorted(order)
    checks.append(Check("sections in the right order", in_order, "header, menu, hours, contact"))
    return checks


# --------------------------------------------------------------------------
# Task 3: summarize a PDF
# --------------------------------------------------------------------------

NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|m|million|thousand)?(?![\w])", re.I)

KEY_FACTS = {
    "revenue": {"numbers": {"4.2", "3.5"}, "words": []},
    "online vs shops": {"numbers": {"58", "42"}, "words": []},
    "bikes sold": {"numbers": {"3100", "1240", "610"}, "words": ["commuter e2"]},
    "York shop": {"numbers": {"180000"}, "words": ["york"]},
    "Northwind Care": {"numbers": {"820"}, "words": ["northwind care", "repair subscription"]},
    "supplier delay": {"numbers": {"300"}, "words": ["supplier", "delay"]},
    "customer score": {"numbers": {"4.6", "2900"}, "words": ["satisfaction"]},
    "team size": {"numbers": {"46", "38"}, "words": ["staff"]},
    "2026 plans": {"numbers": {"2000"}, "words": ["cargo"]},
}


def _norm_numbers(text: str) -> list[str]:
    out = []
    for raw, unit in NUM_RE.findall(text):
        value = float(raw.replace(",", ""))
        unit = (unit or "").lower()
        if unit in ("k", "thousand"):
            value *= 1000
        # "4.2 million" stays 4.2: the PDF writes millions the same way.
        out.append(f"{value:g}" if value != int(value) else str(int(value)))
    return out


def _bullets(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return [re.sub(r"^([-*•·▪‣]|\d+[.)])\s*", "", ln) for ln in lines]


def check_pdf_summary(folder: Path) -> list[Check]:
    summary = folder / "summary.txt"
    if not summary.exists():
        return [Check("summary.txt exists", False, "no summary.txt in 3-pdf-summary")]
    text = summary.read_text(encoding="utf-8", errors="replace")
    source = json.loads((TASKS_DIR / "3-pdf-summary" / "source.json").read_text(encoding="utf-8"))["source_text"]
    allowed = set(_norm_numbers(source))

    bullets = _bullets(text)
    checks = [Check("summary.txt exists", True)]
    checks.append(Check("exactly 5 bullet points", len(bullets) == 5, f"{len(bullets)} found"))

    body = "\n".join(bullets)  # list markers like "1." are not numbers
    made_up = sorted({n for n in _norm_numbers(body) if n not in allowed})
    checks.append(Check("no made-up numbers", not made_up,
                        "every number is in the PDF" if not made_up else "not in the PDF: " + ", ".join(made_up)))

    low = text.lower()
    nums = set(_norm_numbers(body))
    covered = [name for name, f in KEY_FACTS.items()
               if nums & f["numbers"] or any(w in low for w in f["words"])]
    checks.append(Check("covers 4+ key facts", len(covered) >= 4,
                        f"{len(covered)} of {len(KEY_FACTS)}: " + ", ".join(covered)))
    return checks


# --------------------------------------------------------------------------
# Task 4: totals from a CSV
# --------------------------------------------------------------------------

def _paid_totals(csv_path: Path) -> dict[str, float]:
    import csv
    totals: dict[str, float] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            totals.setdefault(row["customer"], 0.0)
            if row["status"].strip().lower() == "paid":
                totals[row["customer"]] += float(row["amount"])
    return totals


def check_csv_totals(folder: Path) -> list[Check]:
    out = folder / "results.txt"
    if not out.exists():
        return [Check("results.txt exists", False, "no results.txt in 4-csv-totals")]
    want = _paid_totals(TASKS_DIR / "4-csv-totals" / "workspace" / "orders.csv")
    lines = [ln for ln in out.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    checks = [Check("results.txt exists", True)]

    def last_number(line: str):
        found = re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", line)
        return float(found[-1].replace(",", "")) if found else None

    wrong = []
    for name, amount in want.items():
        line = next((ln for ln in lines if re.search(rf"\b{re.escape(name)}\b", ln, re.I)), None)
        got = last_number(line) if line else None
        if got is None or abs(got - amount) > 0.005:
            wrong.append(f"{name} (got {got}, want {amount:.2f})")
    checks.append(Check("every customer total is right", not wrong,
                        "4 of 4 right" if not wrong else "; ".join(wrong)))

    total_line = next((ln for ln in lines if re.search(r"\btotal\b", ln, re.I)
                       and not any(re.search(rf"\b{n}\b", ln, re.I) for n in want)), None)
    grand = round(sum(want.values()), 2)
    got = last_number(total_line) if total_line else None
    checks.append(Check("total line is right", got is not None and abs(got - grand) <= 0.005,
                        f"got {got:.2f}, want {grand:.2f}" if got is not None else f"no total line, want {grand:.2f}"))
    return checks


# --------------------------------------------------------------------------
# Task 5: refactor messy code
# --------------------------------------------------------------------------

def _code_lines(path: Path) -> int:
    count = 0
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if s and not s.startswith("#"):
            count += 1
    return count


def _random_datasets(n: int = 300, seed: int = 7):
    rng = random.Random(seed)
    depts = ["eng", "ops", "sales", "hr", "data", "Design", "legal"]
    sets = [[]]
    for _ in range(n):
        size = rng.choice([1, 2, 3, 5, 8, 20, 101, 102, 130])
        rows = []
        for i in range(size):
            # Quarter steps are exact in binary, so a correct refactor can't
            # fail on float rounding noise.
            salary = rng.choice([rng.randint(30, 300), rng.randint(120, 1200) / 4])
            rows.append({"name": f"p{i}", "dept": rng.choice(depts),
                         "salary": salary, "active": rng.random() < 0.85})
        sets.append(rows)
    sets.append([{"name": "x", "dept": "eng", "salary": 50, "active": False}])
    return sets


def check_refactor(folder: Path) -> list[Check]:
    original_dir = TASKS_DIR / "5-refactor" / "workspace"
    checks = [_unchanged(folder / "test_report.py", original_dir / "test_report.py", "test_report.py")]
    checks.append(_run_visible_tests(folder, "test_report.py"))
    try:
        new = _load_function(folder / "report.py", "make_report")
        old = _load_function(original_dir / "report.py", "make_report")
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("same output on 300 hidden inputs", False, f"could not load report.py: {exc}"))
        return checks

    datasets = _random_datasets()
    diffs = 0
    first = ""
    for rows in datasets:
        want = old([dict(r) for r in rows])
        try:
            got = new([dict(r) for r in rows])
        except Exception as exc:  # noqa: BLE001
            got = f"<error: {exc}>"
        if got != want:
            diffs += 1
            if not first:
                first = f"first difference with {len(rows)} rows"
    checks.append(Check(f"same output on {len(datasets)} hidden inputs", diffs == 0,
                        "identical every time" if diffs == 0 else f"{diffs} different. {first}"))

    before, after = _code_lines(original_dir / "report.py"), _code_lines(folder / "report.py")
    shorter = after <= before * 0.8
    checks.append(Check("code is at least 20% shorter", shorter, f"{before} lines before, {after} after"))
    return checks


CHECKERS = {
    "1-fix-bug": check_fix_bug,
    "2-build-page": check_build_page,
    "3-pdf-summary": check_pdf_summary,
    "4-csv-totals": check_csv_totals,
    "5-refactor": check_refactor,
}
