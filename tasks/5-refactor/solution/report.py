def make_report(data):
    """Build a text report of active employees and per-department salary stats."""
    active = [person for person in data if person["active"] == True]
    count = len(active)
    total = 0
    for person in active:
        total = total + person["salary"]
    average = total / count if count else 0

    lines = [
        f"Active employees: {count}",
        f"Total salary: {round(total, 2)}",
        f"Average salary: {round(average, 2)}",
    ]

    by_dept = {}
    for person in active:
        by_dept.setdefault(person["dept"], []).append(person["salary"])

    for dept in sorted(by_dept):
        salaries = by_dept[dept]
        dept_total = 0
        for salary in salaries:
            dept_total = dept_total + salary
        lines.append(
            f"Dept {dept}: count={len(salaries)}, avg={round(dept_total / len(salaries), 2)}, "
            f"max={max(salaries)}, min={min(salaries)}"
        )

    if count == 0:
        lines.append("No active employees")
    elif count == 1:
        lines.append("Note: only one active employee")
    elif count > 100:
        lines.append("Note: large team")
    else:
        lines.append("Note: normal team")
    return "\n".join(lines) + "\n"
