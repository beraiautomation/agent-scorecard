from report import make_report

DATA = [
    {"name": "A", "dept": "eng", "salary": 100, "active": True},
    {"name": "B", "dept": "eng", "salary": 120, "active": True},
    {"name": "C", "dept": "ops", "salary": 90, "active": False},
    {"name": "D", "dept": "ops", "salary": 80, "active": True},
]
WANT = ("Active employees: 3\nTotal salary: 300\nAverage salary: 100.0\n"
        "Dept eng: count=2, avg=110.0, max=120, min=100\n"
        "Dept ops: count=1, avg=80.0, max=80, min=80\nNote: normal team\n")
tests = [
    ("normal data", make_report(DATA) == WANT),
    ("empty list", make_report([]) == "Active employees: 0\nTotal salary: 0\nAverage salary: 0\nNo active employees\n"),
    ("one person", make_report(DATA[:1]).endswith("Note: only one active employee\n")),
]
for name, ok in tests:
    print(("PASS" if ok else "FAIL") + "  " + name)
print(f"\n{sum(ok for _, ok in tests)} of {len(tests)} tests passed")
