def make_report(data):
    # data is a list of dicts: {"name": str, "dept": str, "salary": number, "active": bool}
    r = ""
    t = 0
    c = 0
    d = {}
    for i in range(len(data)):
        x = data[i]
        if x["active"] == True:
            t = t + x["salary"]
            c = c + 1
            if x["dept"] in d:
                d[x["dept"]] = d[x["dept"]] + [x["salary"]]
            else:
                d[x["dept"]] = [x["salary"]]
        else:
            pass
    if c > 0:
        avg = t / c
    else:
        avg = 0
    r = r + "Active employees: " + str(c) + "\n"
    r = r + "Total salary: " + str(round(t, 2)) + "\n"
    r = r + "Average salary: " + str(round(avg, 2)) + "\n"
    keys = list(d.keys())
    keys.sort()
    for k in keys:
        s = 0
        for v in d[k]:
            s = s + v
        a = s / len(d[k])
        hi = d[k][0]
        for v in d[k]:
            if v > hi:
                hi = v
        lo = d[k][0]
        for v in d[k]:
            if v < lo:
                lo = v
        r = r + "Dept " + k + ": count=" + str(len(d[k]))
        r = r + ", avg=" + str(round(a, 2))
        r = r + ", max=" + str(hi)
        r = r + ", min=" + str(lo) + "\n"
    if c == 0:
        r = r + "No active employees\n"
    else:
        if c == 1:
            r = r + "Note: only one active employee\n"
        else:
            if c > 100:
                r = r + "Note: large team\n"
            else:
                r = r + "Note: normal team\n"
    return r
