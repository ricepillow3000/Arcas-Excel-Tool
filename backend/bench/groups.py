"""Group scorecard (AH-223, the ML engineer's advice, John 2026-11-25: "keep a small set of data where you planted known
errors, and check precision and recall on it, broken down by group, every time you change the model"). The industry
and blind benches grade every planted mistake together, so a small group's misses hid among the big group's catches:
a product line priced 3x the big one had its decimal slips caught 0 times in 20 while the totals read 51 of 51.

Each subject is a sheet of a big group (400 rows) and a small one (40) whose usual sizes differ, with known slips
planted in both (a lost decimal point, x0.1, and an extra zero, x10). Per group: recall (planted rows flagged) and the
false-alarm rate (clean rows flagged), at strengths 5 and 8. Synthetic sheets only.

Usage: python backend/bench/groups.py .  Exit 1 when a small group is caught less often (by more than GAP) or falsely
flagged more often (by more than FA_GAP) than its big group."""
import random
import sys

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from anomaly_hunter.server import create_app  # noqa: E402

APP = create_app().test_client()
SEEDS = range(5)
GAP, FA_GAP = 0.10, 0.01
BIG, SMALL = 400, 40
# subject: (group column, big label, small label, value column, big's usual value, small's / big's)
SUBJECTS = {
    "retail prices": ("Product line", "Widget", "Gadget", "Price", 100, 3),
    "payroll by region": ("Region", "North", "South", "Salary", 52000, 2.5),
    "shipping by mode": ("Mode", "Ground", "Air", "Cost", 40, 4),
    "clinic waits": ("Clinic", "Main", "Satellite", "Wait minutes", 60, 0.4),
}


def sheet(seed, group, big, small, value, usual, mult):
    r = random.Random(seed)
    rows = [[f"R{i:04d}", big, round(r.gauss(usual, usual / 8), 2), r.randint(1, 9)] for i in range(BIG)]
    rows += [[f"S{i:04d}", small, round(r.gauss(usual * mult, usual * mult / 8), 2), r.randint(1, 9)] for i in range(SMALL)]
    r.shuffle(rows)
    planted = set()
    for label in (big, small):
        at = [i for i, x in enumerate(rows) if x[1] == label]
        for i, slip in zip(r.sample(at, 2), (0.1, 10), strict=True):
            rows[i][2] = round(rows[i][2] * slip, 2)
            planted.add(i)
    return ["ID", group, value, "Qty"], rows, planted


def grade(strength):
    """-> {subject: {label: [planted, caught, clean, false alarms]}}"""
    out = {}
    for name, (group, big, small, value, usual, mult) in SUBJECTS.items():
        tally = {big: [0, 0, 0, 0], small: [0, 0, 0, 0]}
        for seed in SEEDS:
            cols, rows, planted = sheet(seed, group, big, small, value, usual, mult)
            res = APP.post("/scan", json={"columns": cols, "rows": rows, "strength": strength}).get_json()["rows"]
            for i, (row, r) in enumerate(zip(rows, res, strict=True)):
                t, flagged = tally[row[1]], r["severity"] not in (None, "Noted")
                if i in planted:
                    t[0] += 1
                    t[1] += flagged
                else:
                    t[2] += 1
                    t[3] += flagged
        out[name] = tally
    return out


def main():
    bad = []
    for strength in (5, 8):
        print(f"strength {strength}")
        for name, tally in grade(strength).items():
            (big, b), (small, s) = tally.items()
            rec = lambda t: t[1] / t[0]  # noqa: E731
            fa = lambda t: t[3] / t[2]  # noqa: E731
            print(f"  {name:18s} {big:>9s}: caught {b[1]}/{b[0]} false alarms {fa(b):6.2%} | "
                  f"{small:>9s}: caught {s[1]}/{s[0]} false alarms {fa(s):6.2%}")
            if rec(s) < rec(b) - GAP:
                bad.append(f"{name} at {strength}: {small} caught {rec(s):.0%} vs {big} {rec(b):.0%}")
            if fa(s) > fa(b) + FA_GAP:
                bad.append(f"{name} at {strength}: {small} false alarms {fa(s):.2%} vs {big} {fa(b):.2%}")
    print("GROUPS fail:\n  " + "\n  ".join(bad) if bad else "GROUPS pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
