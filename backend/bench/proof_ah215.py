"""AH-215 proof: does the scan adapt to what the sheet is about, to its groups and to what the user taught it?
Run once against each engine and compare: python backend/bench/proof_ah215.py <repo>  (main, then this branch).

Four questions, each graded on sheets with planted slips whose true values are known (synthetic only):
1 subject: does it say what the sheet is, and which column sets each group's normal?
2 groups: is a small group's slip caught as often as a big group's, at strength 5 and 8, honest rows left alone?
3 learning: after a Dismiss, is that value quiet on the next scan, in that column only?
4 lazy clicks: after the user dismisses every flag, are the next day's new slips caught as often as with nothing learned?"""
import json
import random
import sys

sys.path.insert(0, sys.argv[1])
from anomaly_hunter.server import create_app  # noqa: E402

APP = create_app().test_client()
SUBJECTS = {  # subject: (group column, big label, small label, value column, big's usual value, small's / big's)
    "retail prices": ("Product line", "Widget", "Gadget", "Price", 100, 3),
    "payroll by region": ("Region", "North", "South", "Salary", 52000, 2.5),
    "shipping by mode": ("Mode", "Ground", "Air", "Cost", 40, 4),
    "clinic waits": ("Clinic", "Main", "Satellite", "Wait minutes", 60, 0.4),
}
SEEDS = range(10)


def post(route, body):
    r = APP.post(route, json=body)
    return r.get_json() if r.status_code == 200 else {}


def sheet(seed, group, big, small, value, usual, mult, slips=True):
    r = random.Random(seed)
    rows = [[f"R{i:04d}", big, round(r.gauss(usual, usual / 8), 2), r.randint(1, 9)] for i in range(400)]
    rows += [[f"S{i:04d}", small, round(r.gauss(usual * mult, usual * mult / 8), 2), r.randint(1, 9)] for i in range(40)]
    r.shuffle(rows)
    planted = {}
    if slips:
        for label in (big, small):
            at = [i for i, x in enumerate(rows) if x[1] == label]
            for i, slip in zip(r.sample(at, 2), (0.1, 10), strict=True):
                rows[i][2] = round(rows[i][2] * slip, 2)
                planted[i] = label
    return ["ID", group, value, "Qty"], rows, planted


flag = lambda r: r["severity"] not in (None, "Noted")  # noqa: E731
result = {}

# 1 subject
spec = SUBJECTS["payroll by region"]
cols, rows, _ = sheet(0, *spec)
result["1 subject: what Before you scan says"] = post("/profile", {"columns": cols, "rows": rows}).get("lines", [])
said = {}
for name, s in SUBJECTS.items():
    cols, rows, planted = sheet(0, *s)
    out = post("/scan", {"columns": cols, "rows": rows})["rows"]
    small = next(i for i, g in planted.items() if g == s[2] and rows[i][2] < s[4] * s[5])
    said[name] = out[small]["reason"] or "(not flagged)"
result["1 subject: the small group's dropped decimal point, as the scan says it"] = said

# 2 groups
for strength in (5, 8):
    table = {}
    for name, s in SUBJECTS.items():
        t = {s[1]: [0, 0, 0, 0], s[2]: [0, 0, 0, 0]}  # planted, caught, clean, false alarms
        for seed in SEEDS:
            cols, rows, planted = sheet(seed, *s)
            for i, r in enumerate(post("/scan", {"columns": cols, "rows": rows, "strength": strength})["rows"]):
                g = t[rows[i][1]]
                if i in planted:
                    g[0] += 1
                    g[1] += flag(r)
                else:
                    g[2] += 1
                    g[3] += flag(r)
        table[name] = {k: f"caught {v[1]}/{v[0]}, false alarms {v[3] / v[2]:.2%}" for k, v in t.items()}
    result[f"2 groups at strength {strength}"] = table

# 3 learning, 4 lazy clicks
cols, rows, planted = sheet(3, *SUBJECTS["retail prices"])
first = post("/scan", {"columns": cols, "rows": rows})["rows"]
taught = [i for i in planted if flag(first[i])][0]
accept = [["Price", str(rows[taught][2])]]
again = post("/scan", {"columns": cols, "rows": rows, "learned": {"accept": accept}})["rows"]
result["3 learning: the dismissed value on the next scan"] = {"before": first[taught]["severity"], "after": again[taught]["severity"]}
lazy = [[c, str(rows[i][cols.index(c)])] for i, r in enumerate(first) if flag(r) for c in r.get("cells", [])]
r = random.Random(99)
fresh = [i for g in ("Widget", "Gadget") for i in r.sample([i for i, x in enumerate(rows) if x[1] == g and i not in planted], 2)]
for i, slip in zip(fresh, (0.1, 10, 0.1, 10), strict=True):
    rows[i][2] = round(rows[i][2] * slip, 2)
out = post("/scan", {"columns": cols, "rows": rows, "learned": {"accept": lazy}})["rows"]
plain = post("/scan", {"columns": cols, "rows": rows})["rows"]
result["4 lazy clicks: every flag dismissed, then 4 new slips (2 in each group)"] = {
    "dismissed": len(lazy), "caught after the lazy clicks": f"{sum(flag(out[i]) for i in fresh)}/4",
    "caught with nothing learned": f"{sum(flag(plain[i]) for i in fresh)}/4"}
print(json.dumps(result, indent=1))
