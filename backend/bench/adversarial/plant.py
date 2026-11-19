"""AH-208 planter: build one episode of 4 synthetic sheets from a seed, with its secret key of planted errors and valid
traps, in the format scan.py and judge.py read. Never real data.
usage: python -I plant.py <seed> <sheets_dir> <key.json>
Six subjects (payroll, retail inventory, school grades, field sensors, insurance claims, project budgets); the seed picks
4 and every value, row and plant. Each sheet carries its subject's honest quirks (long tails, sparse optional columns,
categories whose values differ by design, rounded totals, second formulas on purpose) beside the planted mistakes. A
plant in an input recomputes the formulas fed by it, as Excel would, and those cells are accepted for it too.
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

import numpy as np


class Sheet:
    def __init__(self, name, domain, columns, formulas):
        """formulas: {col: [(test(row) -> bool, "={A}*{B}", fn(row) -> value)]}: the first whose test holds is the cell's."""
        self.name, self.domain, self.columns, self.formulas = name, domain, columns, formulas
        self.rows, self.typed, self.errors, self.traps = [], [], [], []

    def add(self, row):
        self.rows.append({c: row.get(c) for c in self.columns})
        self.typed.append(set())

    def r1c1(self, target, expr):
        t = self.columns.index(target)

        def ref(m):
            off = self.columns.index(m[1]) - t
            return "RC" if off == 0 else f"RC[{off}]"
        return re.sub(r"\{([^}]+)\}", ref, expr)

    def deps(self, col):
        """the formula columns fed by col, all the way down"""
        out, todo = set(), [col]
        while todo:
            c = todo.pop()
            for f, alts in self.formulas.items():
                if f not in out and any("{" + c + "}" in e for _, e, _ in alts):
                    out.add(f)
                    todo.append(f)
        return [c for c in self.columns if c in out]

    def compute(self, i):
        r = self.rows[i]
        for c in self.columns:
            if c in self.formulas and c not in self.typed[i]:
                for test, _, fn in self.formulas[c]:
                    if test(r):
                        r[c] = fn(r)
                        break

    def error(self, i, cols, kind, domain_specific, proof, cascade=True):
        cols = list(cols)
        if cascade:
            cols += [d for c in cols for d in self.deps(c) if d not in cols]
        self.errors.append({"row": i, "cols": list(dict.fromkeys(cols)), "kind": kind,
                            "domain_specific": domain_specific, "proof": proof})

    def trap(self, i, col, why):
        self.traps.append({"row": i, "col": col, "why": why})

    def insert_copy(self, i, kind, proof):
        """a row entered twice: the copy goes right after it; every recorded row past it moves down one"""
        self.rows.insert(i + 1, dict(self.rows[i]))
        self.typed.insert(i + 1, set(self.typed[i]))
        for e in self.errors + self.traps:
            if e["row"] > i:
                e["row"] += 1
        self.errors.append({"row": i + 1, "cols": list(self.columns), "kind": kind, "domain_specific": False, "proof": proof})

    def dump(self):
        rows, grid = [], []
        for i, r in enumerate(self.rows):
            rows.append([_out(r[c]) for c in self.columns])
            g = []
            for c in self.columns:
                f = None
                if c in self.formulas and c not in self.typed[i]:
                    f = next(self.r1c1(c, e) for test, e, _ in self.formulas[c] if test(r))
                g.append(f)
            grid.append(g)
        return {"name": self.name, "columns": self.columns, "rows": rows, "formulas": grid}


def _out(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, dt.datetime) else v.isoformat()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        v = float(v)
        return int(v) if v.is_integer() and abs(v) < 1e15 else round(v, 6)
    return v


def yes(_):
    return True


def misspell(word, rng):
    """one honest-looking slip inside a word of 5+ letters: a letter dropped, doubled or two swapped"""
    words = word.split(" ")
    j = max(range(len(words)), key=lambda k: len(words[k]))
    w = words[j]
    k = int(rng.integers(1, len(w) - 2))
    w = [w[:k] + w[k + 1:], w[:k] + w[k] + w[k:], w[:k] + w[k + 1] + w[k] + w[k + 2:]][int(rng.integers(3))]
    words[j] = w
    return " ".join(words)


def swap_digits(x):
    s = f"{x:.2f}"
    digits = [k for k in range(len(s) - 1) if s[k].isdigit() and s[k + 1].isdigit() and s[k] != s[k + 1]]
    k = digits[0]
    return float(s[:k] + s[k + 1] + s[k] + s[k + 2:])


def pick(rng, rows, test, taken):
    cand = [i for i in rows if test(i) and i not in taken]
    i = int(rng.choice(cand))
    taken.add(i)
    return i


# ---------------------------------------------------------------- payroll
def payroll(rng):
    depts = ["Engineering", "Sales", "Operations", "Finance", "Customer Support"]
    states = ["CA", "NY", "TX", "IL", "WA", "FL", "NC"]
    no_tax = {"TX", "WA", "FL"}
    cols = ["Pay Period End", "Employee ID", "Department", "Work State", "Pay Type", "Hourly Rate", "Annual Salary",
            "Regular Hours", "Overtime Hours", "Regular Pay", "Overtime Pay", "Bonus", "Gross Pay", "Federal Tax",
            "State Tax", "401(k) %", "401(k)", "Net Pay", "Note"]
    hourly = lambda r: r["Pay Type"] == "Hourly"
    f = {"Regular Pay": [(hourly, "=ROUND({Regular Hours}*{Hourly Rate},2)", lambda r: round(r["Regular Hours"] * r["Hourly Rate"], 2)),
                         (yes, "=ROUND({Annual Salary}/26,2)", lambda r: round(r["Annual Salary"] / 26, 2))],
         "Overtime Pay": [(hourly, "=ROUND({Overtime Hours}*{Hourly Rate}*1.5,2)", lambda r: round(r["Overtime Hours"] * r["Hourly Rate"] * 1.5, 2)),
                          (yes, "=0", lambda r: 0)],
         "Gross Pay": [(yes, "={Regular Pay}+{Overtime Pay}+{Bonus}", lambda r: round(r["Regular Pay"] + r["Overtime Pay"] + r["Bonus"], 2))],
         "401(k)": [(yes, "=ROUND({Gross Pay}*{401(k) %}/100,2)", lambda r: round(r["Gross Pay"] * r["401(k) %"] / 100, 2))],
         "Net Pay": [(yes, "={Gross Pay}-{Federal Tax}-{State Tax}-{401(k)}", lambda r: round(r["Gross Pay"] - r["Federal Tax"] - r["State Tax"] - r["401(k)"], 2))]}
    s = Sheet("payroll_register", "Biweekly payroll register: one row per employee per pay period, hourly and salaried staff, "
              "gross to net with federal and state withholding and a 401(k) deferral.", cols, f)
    n_emp, n_per = int(rng.integers(30, 42)), int(rng.integers(10, 14))
    emps = []
    for e in range(n_emp):
        kind = "Hourly" if rng.random() < 0.6 else "Salaried"
        sal = float(round(rng.lognormal(np.log(78000), 0.3), -2)) if kind == "Salaried" else None
        emps.append({"Employee ID": f"E{1040 + e * 7}", "Department": str(rng.choice(depts)),
                     "Work State": str(rng.choice(states)), "Pay Type": kind,
                     "Hourly Rate": float(round(rng.uniform(17, 46) * 4) / 4) if kind == "Hourly" else None,
                     "Annual Salary": sal, "401(k) %": float(rng.choice([0, 0, 3, 4, 5, 6, 8, 10])),
                     "fed": float(rng.uniform(0.09, 0.2)), "st": float(rng.uniform(0.03, 0.07))})
    for e in rng.choice([x for x in range(n_emp) if emps[x]["Pay Type"] == "Salaried"], 2, replace=False):
        emps[e]["Annual Salary"] = float(rng.choice([245000, 310000, 280000]))  # executives: the honest long tail
        emps[e]["fed"] = 0.27
    end0 = dt.date(2026, 1, 9) + dt.timedelta(days=14 * int(rng.integers(0, 8)))
    for p in range(n_per):
        for e in emps:
            r = {k: v for k, v in e.items() if k in cols}
            r["Pay Period End"] = end0 + dt.timedelta(days=14 * p)
            if e["Pay Type"] == "Hourly":
                r["Regular Hours"] = float(rng.choice([80] * 8 + [72, 76, 64, 78]))
                r["Overtime Hours"] = 0.0 if rng.random() < 0.65 else float(rng.integers(2, 25) / 2)
            else:
                r["Regular Hours"], r["Overtime Hours"] = 80.0, 0.0
            r["Bonus"] = 0.0 if rng.random() < 0.88 else float(round(rng.uniform(200, 3000), -1))
            r["Note"] = "Spot bonus" if r["Bonus"] else None
            r["Federal Tax"] = r["State Tax"] = 0.0
            s.add(r)
            i = len(s.rows) - 1
            s.compute(i)
            s.rows[i]["Federal Tax"] = round(s.rows[i]["Gross Pay"] * e["fed"], 2)
            s.rows[i]["State Tax"] = 0.0 if e["Work State"] in no_tax else round(s.rows[i]["Gross Pay"] * e["st"], 2)
            s.compute(i)
    n = len(s.rows)
    allrows, taken = range(n), set()

    def retax(i, e=None):
        r = s.rows[i]
        e = e or next(x for x in emps if x["Employee ID"] == r["Employee ID"])
        s.compute(i)
        r["Federal Tax"] = round(r["Gross Pay"] * e["fed"], 2)
        r["State Tax"] = 0.0 if r["Work State"] in no_tax else round(r["Gross Pay"] * e["st"], 2)
        s.compute(i)
    # traps
    big = [x for x in emps if x["Annual Salary"] and x["Annual Salary"] >= 245000]
    i = pick(rng, allrows, lambda i: s.rows[i]["Employee ID"] == big[0]["Employee ID"], taken)
    s.rows[i]["Bonus"], s.rows[i]["Note"] = float(rng.choice([25000, 40000, 31500])), "Annual bonus"
    retax(i)
    s.trap(i, "Bonus", "An executive's annual bonus, paid once a year and named in Note: far above the spot bonuses, and valid.")
    i = pick(rng, allrows, lambda i: hourly(s.rows[i]) and not s.rows[i]["Bonus"], taken)
    s.rows[i]["Bonus"], s.rows[i]["Note"] = -float(round(rng.uniform(150, 600), 0)), "Overpayment recovery"
    retax(i)
    s.trap(i, "Bonus", "A negative adjustment recovers an earlier overpayment, as Note says; gross still adds up.")
    i = pick(rng, allrows, lambda i: hourly(s.rows[i]) and not s.rows[i]["Bonus"], taken)
    s.rows[i]["Regular Hours"], s.rows[i]["Overtime Hours"], s.rows[i]["Note"] = 0.0, 0.0, "Unpaid leave"
    retax(i)
    s.trap(i, "Regular Hours", "Unpaid leave for the whole period: 0 hours and 0 gross are correct.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Work State"] in no_tax and s.rows[i]["Gross Pay"] > 0, taken)
    s.trap(i, "State Tax", f"{s.rows[i]['Work State']} has no state income tax, so 0 withheld is correct.")
    i = pick(rng, allrows, lambda i: hourly(s.rows[i]) and not s.rows[i]["Bonus"] and s.rows[i]["Pay Period End"] == end0, taken)
    s.rows[i]["Regular Hours"], s.rows[i]["Overtime Hours"], s.rows[i]["Note"] = 40.0, 0.0, "New hire"
    retax(i)
    s.trap(i, "Regular Hours", "A new hire's first period starts mid-period: 40 hours is correct.")
    # errors
    i = pick(rng, allrows, lambda i: hourly(s.rows[i]) and s.rows[i]["Regular Hours"] == 80, taken)
    s.rows[i]["Regular Hours"] = 800.0
    retax(i)
    # the taxes are withheld from the gross the hours made, as payroll software does: they are the plant's cells too
    s.error(i, ["Regular Hours", "Federal Tax", "State Tax"], "hours typed x10", False, "800 regular hours in a two-week period (80 is full time).")
    i = pick(rng, allrows, lambda i: hourly(s.rows[i]) and len(set(f"{s.rows[i]['Hourly Rate']:.2f}"[:2])) == 2, taken)
    old = s.rows[i]["Hourly Rate"]
    s.rows[i]["Hourly Rate"] = swap_digits(old)
    retax(i)
    s.error(i, ["Hourly Rate", "Federal Tax", "State Tax"], "rate digits swapped", True, f"Hourly Rate {s.rows[i]['Hourly Rate']} where this employee's every other period is {old}.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Net Pay"] > 500, taken)
    s.rows[i]["Net Pay"] = round(s.rows[i]["Net Pay"] + float(rng.choice([100, -100, 1000])), 2)
    s.typed[i].add("Net Pay")
    s.error(i, ["Net Pay"], "net pay typed over its formula", True, "Net Pay is typed and is not Gross - taxes - 401(k).")
    i = pick(rng, allrows, lambda i: True, taken)
    s.rows[i]["Department"] = misspell(s.rows[i]["Department"], rng)
    s.error(i, ["Department"], "misspelt department", False, f"Department {s.rows[i]['Department']!r} is a misspelling.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Federal Tax"] > 100, taken)
    s.rows[i]["Federal Tax"] = -s.rows[i]["Federal Tax"]
    s.compute(i)
    s.error(i, ["Federal Tax"], "withholding sign flipped", False, "Negative federal tax withheld on an ordinary period.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Work State"] in no_tax and s.rows[i]["Gross Pay"] > 0, taken)
    s.rows[i]["State Tax"] = round(s.rows[i]["Gross Pay"] * 0.05, 2)
    s.compute(i)
    s.error(i, ["State Tax"], "state tax in a state without one", True, f"{s.rows[i]['Work State']} has no state income tax; every other {s.rows[i]['Work State']} row withholds 0.")
    i = pick(rng, allrows, lambda i: True, taken)
    d = s.rows[i]["Pay Period End"]
    s.rows[i]["Pay Period End"] = d.replace(year=2062 if rng.random() < 0.5 else 2016)
    s.error(i, ["Pay Period End"], "year typo", False, "A pay period end years away from every other period.")
    i = pick(rng, allrows, lambda i: i < n - 1, taken)
    s.insert_copy(i, "employee paid twice for one period", "The same employee, period and amounts entered twice.")
    return s


# ---------------------------------------------------------------- retail inventory
def inventory(rng):
    cats = {"Grocery": (0.8, 6), "Household": (2, 14), "Electronics": (18, 320), "Apparel": (6, 40), "Toys": (4, 30)}
    names = {"Grocery": ["Oat Cereal", "Peanut Butter", "Basmati Rice", "Olive Oil", "Green Tea", "Pasta Shells"],
             "Household": ["Paper Towels", "Dish Soap", "Laundry Pods", "Trash Bags", "Sponges"],
             "Electronics": ["USB Charger", "Bluetooth Speaker", "Headphones", "Smart Plug", "Webcam"],
             "Apparel": ["Cotton Socks", "Rain Jacket", "Wool Beanie", "Running Shorts"],
             "Toys": ["Puzzle Box", "Building Blocks", "Card Game", "Toy Truck"]}
    cols = ["SKU", "Product", "Category", "Store", "Week Ending", "Opening Stock", "Received", "Units Sold", "Returned",
            "Shrinkage", "Closing Stock", "Unit Cost", "Unit Price", "Promo", "Sales Value", "Stock Value"]
    f = {"Closing Stock": [(yes, "={Opening Stock}+{Received}-{Units Sold}+{Returned}-{Shrinkage}",
                            lambda r: r["Opening Stock"] + r["Received"] - r["Units Sold"] + r["Returned"] - r["Shrinkage"])],
         "Sales Value": [(yes, "=ROUND({Units Sold}*{Unit Price},2)", lambda r: round(r["Units Sold"] * r["Unit Price"], 2))],
         "Stock Value": [(yes, "=ROUND({Closing Stock}*{Unit Cost},2)", lambda r: round(r["Closing Stock"] * r["Unit Cost"], 2))]}
    s = Sheet("store_inventory", "Weekly store inventory by SKU: opening + received - sold + returned - shrinkage = "
              "closing, the next week opening where the last closed; promo weeks sell at a discount.", cols, f)
    skus = []
    for c, ns in names.items():
        for nm in ns:
            lo, hi = cats[c]
            cost = float(round(np.exp(rng.uniform(np.log(lo), np.log(hi))), 2))
            price = float(np.floor(cost * rng.uniform(1.35, 1.9)) + 0.99)
            skus.append({"SKU": f"SKU-{int(rng.integers(10000, 99999))}", "Product": nm, "Category": c,
                         "Unit Cost": cost, "Unit Price": price, "demand": float(rng.uniform(3, 40) * (0.3 if c == "Electronics" else 1)),
                         "case": int(rng.choice([6, 12, 24, 48]))})
    stores = [f"S{k:02d}" for k in range(1, int(rng.integers(3, 5)) + 1)]
    weeks = int(rng.integers(5, 8))
    w0 = dt.date(2026, 3, 1) + dt.timedelta(days=int(rng.integers(0, 6)) * 7)
    for k in skus:
        for st in stores:
            stock = int(rng.integers(20, 160))
            for w in range(weeks):
                promo = rng.random() < 0.08
                sold = int(min(stock, rng.poisson(k["demand"] * (1.8 if promo else 1))))
                recv = 0 if rng.random() < 0.7 else k["case"] * int(rng.integers(1, 5))
                r = dict(k, Store=st, **{"Week Ending": w0 + dt.timedelta(days=7 * w), "Opening Stock": stock,
                                          "Received": recv, "Units Sold": sold,
                                          "Returned": 0 if rng.random() < 0.85 else int(rng.integers(1, 4)),
                                          "Shrinkage": 0 if rng.random() < 0.9 else int(rng.integers(1, 3)),
                                          "Promo": "Y" if promo else "N"})
                if promo:
                    r["Unit Price"] = float(round(k["Unit Price"] * 0.75, 2))
                s.add(r)
                s.compute(len(s.rows) - 1)
                stock = s.rows[-1]["Closing Stock"]
    n = len(s.rows)
    allrows, taken = range(n), set()
    same = lambda i: i + 1 < n and s.rows[i + 1]["SKU"] == s.rows[i]["SKU"] and s.rows[i + 1]["Store"] == s.rows[i]["Store"]

    def carry(i):  # the weeks after i open where i closed
        while same(i):
            s.rows[i + 1]["Opening Stock"] = s.rows[i]["Closing Stock"]
            s.compute(i + 1)
            i += 1
    # traps
    i = pick(rng, allrows, lambda i: s.rows[i]["Promo"] == "Y", taken)
    s.trap(i, "Unit Price", "A promo week sells at 25% off, as Promo = Y says: the SKU's other weeks' price is not this one's.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Category"] == "Electronics", taken)
    s.trap(i, "Unit Cost", "Electronics cost tens to hundreds of dollars a unit beside groceries at a few: valid for its category.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Units Sold"] > 0 and s.rows[i]["Promo"] == "N", taken)
    s.rows[i]["Units Sold"] = 0
    s.compute(i)
    carry(i)
    s.trap(i, "Units Sold", "A week with no sales of a slow item: 0 sold is valid.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Received"] == 0, taken)
    s.rows[i]["Received"] = next(k["case"] for k in skus if k["SKU"] == s.rows[i]["SKU"]) * 20
    s.compute(i)
    carry(i)
    s.trap(i, "Received", "A seasonal restock of 20 cases at once: far above the usual delivery, and valid (closing adds up).")
    # errors
    i = pick(rng, allrows, lambda i: s.rows[i]["Promo"] == "N", taken)
    s.rows[i]["Unit Cost"] = round(s.rows[i]["Unit Cost"] * 10, 2)
    s.compute(i)
    s.error(i, ["Unit Cost"], "cost decimal slip x10", False, "Unit Cost is 10x this SKU's cost on every other row.")
    i = pick(rng, allrows, lambda i: i > 0 and s.rows[i - 1]["SKU"] == s.rows[i]["SKU"] and s.rows[i - 1]["Store"] == s.rows[i]["Store"], taken)
    s.rows[i]["Opening Stock"] += int(rng.choice([20, -15, 30]))
    s.compute(i)
    carry(i)
    s.error(i, ["Opening Stock"], "opening is not last week's closing", True, "Opening Stock differs from the same SKU and store's Closing Stock the week before.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Closing Stock"] > 10, taken)
    s.rows[i]["Closing Stock"] += int(rng.choice([10, -8, 100]))
    s.typed[i].add("Closing Stock")
    s.compute(i)
    s.error(i, ["Closing Stock"], "closing typed over its formula", True, "Closing Stock is typed and is not opening + received - sold + returned - shrinkage.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Units Sold"] > 3, taken)
    s.rows[i]["Units Sold"] = -s.rows[i]["Units Sold"]
    s.compute(i)
    carry(i)
    s.error(i, ["Units Sold"], "sold sign flipped", False, "A negative number of units sold.")
    i = pick(rng, allrows, lambda i: True, taken)
    s.rows[i]["Category"] = misspell(s.rows[i]["Category"], rng)
    s.error(i, ["Category"], "misspelt category", False, f"Category {s.rows[i]['Category']!r} is a misspelling.")
    i = pick(rng, allrows, lambda i: True, taken)
    other = next(k["Product"] for k in skus if k["Category"] == s.rows[i]["Category"] and k["Product"] != s.rows[i]["Product"])
    s.rows[i]["Product"] = other
    s.error(i, ["Product"], "another product's name on this SKU", True, f"Product {other!r} on {s.rows[i]['SKU']}, whose every other row names another product.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Promo"] == "N", taken)
    s.rows[i]["Unit Cost"], s.rows[i]["Unit Price"] = s.rows[i]["Unit Price"], s.rows[i]["Unit Cost"]
    s.compute(i)
    s.error(i, ["Unit Cost", "Unit Price"], "cost and price swapped", True, "Unit Cost above Unit Price on a full-price week: the two are swapped.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Received"] > 0, taken)
    s.rows[i]["Received"] *= 100
    s.compute(i)
    carry(i)
    s.error(i, ["Received"], "received x100", False, "Received is 100x a delivery of this SKU's case size.")
    return s


# ---------------------------------------------------------------- school grades
def grades(rng):
    classes = {"Math 7A": "Ms. Alvarez", "Science 7B": "Mr. Okafor", "English 8A": "Mrs. Lindqvist", "History 8B": "Mr. Tanaka"}
    kinds = [("Homework", 10, 6), ("Quiz", 20, 3), ("Test", 100, 2), ("Project", 50, 1)]
    cols = ["Student ID", "Grade Level", "Class", "Teacher", "Assessment", "Type", "Date", "Max Points", "Score",
            "Percent", "Letter", "Status", "Note"]
    letter = lambda p: "A" if p >= 90 else "B" if p >= 80 else "C" if p >= 70 else "D" if p >= 60 else "F"
    exc = lambda r: r["Status"] == "Excused"
    f = {"Percent": [(exc, '=IF({Status}="Excused","",ROUND({Score}/{Max Points}*100,1))', lambda r: None),
                     (yes, '=IF({Status}="Excused","",ROUND({Score}/{Max Points}*100,1))', lambda r: round(r["Score"] / r["Max Points"] * 100, 1))],
         "Letter": [(exc, '=IF({Percent}="","",IF({Percent}>=90,"A",IF({Percent}>=80,"B",IF({Percent}>=70,"C",IF({Percent}>=60,"D","F")))))', lambda r: None),
                    (yes, '=IF({Percent}="","",IF({Percent}>=90,"A",IF({Percent}>=80,"B",IF({Percent}>=70,"C",IF({Percent}>=60,"D","F")))))', lambda r: letter(r["Percent"]))]}
    s = Sheet("gradebook", "Middle-school gradebook: one row per student per assessment; homework out of 10, quizzes 20, "
              "tests 100, projects 50; excused work has no score, missing work scores 0.", cols, f)
    for cl, teacher in classes.items():
        students = [f"S{2400 + int(x)}" for x in rng.choice(900, int(rng.integers(8, 13)), replace=False)]
        ability = {st: float(np.clip(rng.normal(0.8, 0.1), 0.45, 0.99)) for st in students}
        d0 = dt.date(2026, 9, 7)
        plan = []
        for kind, mx, cnt in kinds:
            plan += [(f"{kind} {k + 1}" if cnt > 1 else kind, kind, mx) for k in range(cnt)]
        dates = sorted(d0 + dt.timedelta(days=int(x)) for x in rng.choice(80, len(plan), replace=False))
        for (name, kind, mx), d in zip(plan, dates):
            for st in students:
                status = "Excused" if rng.random() < 0.02 else "Missing" if kind == "Homework" and rng.random() < 0.05 else "Turned in"
                sc = None if status == "Excused" else 0.0 if status == "Missing" else \
                    float(min(mx, round(mx * np.clip(ability[st] + rng.normal(0, 0.08), 0.2, 1) * 2) / 2))
                if kind != "Test" and sc is not None:
                    sc = float(round(sc))
                s.add({"Student ID": st, "Grade Level": int(cl[-2]), "Class": cl, "Teacher": teacher, "Assessment": name,
                       "Type": kind, "Date": d, "Max Points": mx, "Score": sc, "Status": status})
                s.compute(len(s.rows) - 1)
    n = len(s.rows)
    allrows, taken = range(n), set()
    ok = lambda i: s.rows[i]["Status"] == "Turned in"
    # traps
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Type"] == "Project", taken)
    s.rows[i]["Score"], s.rows[i]["Note"] = 53.0, "Extra credit"
    s.compute(i)
    s.trap(i, "Score", "53 of 50 with the extra credit Note says: above the maximum, and valid.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Status"] == "Excused", taken)
    s.trap(i, "Score", "Excused work has no score and no percent: the blanks are correct.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Status"] == "Missing", taken)
    s.trap(i, "Score", "Missing homework scores 0, as Status says.")
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Type"] == "Test", taken)
    s.rows[i]["Score"] = 100.0
    s.compute(i)
    s.trap(i, "Score", "A perfect test: 100 of 100.")
    # errors
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Type"] == "Homework" and 5 <= s.rows[i]["Score"] < 10, taken)
    s.rows[i]["Score"] *= 10
    s.compute(i)
    s.error(i, ["Score"], "score x10", False, "A homework out of 10 scored 10x its scale.")
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Percent"] >= 60, taken)
    s.rows[i]["Letter"] = {"A": "B", "B": "A", "C": "B", "D": "C"}[s.rows[i]["Letter"]]
    s.typed[i].add("Letter")
    s.error(i, ["Letter"], "letter typed over its formula", True, "Letter is typed and does not match Percent's band.")
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Type"] == "Test" and s.rows[i]["Score"] > 10, taken)
    s.rows[i]["Max Points"] = 10
    s.compute(i)
    s.error(i, ["Max Points"], "wrong maximum for a test", True, "A test out of 10 where every other test is out of 100 (Percent over 100).")
    i = pick(rng, allrows, lambda i: True, taken)
    s.rows[i]["Type"] = {"Homework": "Homwork", "Quiz": "Quizz", "Test": "Tset", "Project": "Projcet"}[s.rows[i]["Type"]]
    s.error(i, ["Type"], "misspelt type", False, f"Type {s.rows[i]['Type']!r} is a misspelling.")
    i = pick(rng, allrows, lambda i: True, taken)
    s.rows[i]["Date"] = s.rows[i]["Date"].replace(year=2206 if rng.random() < 0.5 else 2062)
    s.error(i, ["Date"], "year typo", False, "A date centuries or decades from the school year.")
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Score"] >= 3, taken)
    s.rows[i]["Score"] = -s.rows[i]["Score"]
    s.compute(i)
    s.error(i, ["Score"], "negative score", False, "A negative score.")
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Type"] == "Quiz" and s.rows[i]["Score"] >= 14 and not s.rows[i]["Note"], taken)
    s.rows[i]["Score"] = s.rows[i]["Score"] + 8
    s.compute(i)
    s.error(i, ["Score"], "score above the maximum with no extra credit", True, "A quiz scored above its 20 points with no extra credit noted.")
    i = pick(rng, allrows, lambda i: i < n - 1, taken)
    s.insert_copy(i, "grade entered twice", "The same student and assessment entered twice.")
    return s


# ---------------------------------------------------------------- field sensors
def sensors(rng):
    sites = [("ST-01", "Valley", 120, 18, 9, 1012, 55), ("ST-02", "Ridge", 1480, 6, 6, 852, 65),
             ("ST-03", "Coast", 15, 15, 4, 1014, 80), ("ST-04", "Desert", 640, 30, 12, 940, 18)]
    cols = ["Station", "Site", "Elevation (m)", "Timestamp", "Temperature (C)", "Temperature (F)", "Humidity (%)",
            "Pressure (hPa)", "Wind Speed (m/s)", "Rainfall (mm)", "Battery (V)", "Status"]
    on = lambda r: r["Temperature (C)"] is not None
    f = {"Temperature (F)": [(on, '=IF({Temperature (C)}="","",ROUND({Temperature (C)}*9/5+32,1))', lambda r: round(r["Temperature (C)"] * 9 / 5 + 32, 1)),
                             (yes, '=IF({Temperature (C)}="","",ROUND({Temperature (C)}*9/5+32,1))', lambda r: None)]}
    s = Sheet("station_log", "Hourly weather-station log from four field sites at different heights and climates; "
              "offline hours carry no readings, a battery swap shows as Maintenance.", cols, f)
    hours = int(rng.integers(96, 145))
    t0 = dt.datetime(2026, 7, int(rng.integers(1, 20)))
    storm = (int(rng.integers(30, hours - 20)), int(rng.integers(4, 8)))
    for st, site, elev, tbase, amp, p0, h0 in sites:
        batt = float(rng.uniform(12.9, 13.4))
        off = int(rng.integers(10, hours - 10)) if site == "Ridge" else -99
        swap = int(rng.integers(20, hours - 10)) if site == "Desert" else -99
        drift = 0.0
        for h in range(hours):
            ts = t0 + dt.timedelta(hours=h)
            temp = tbase + amp * np.sin((ts.hour - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.7)
            drift += rng.normal(0, 0.3)
            rain = 0.0
            if site == "Coast" and storm[0] <= h < storm[0] + storm[1]:
                rain = float(round(rng.uniform(10 if h == storm[0] + 1 else 2, 18), 1))
            elif rng.random() < 0.02:
                rain = float(round(rng.uniform(0.2, 1.5), 1))
            batt -= 0.004
            status = "OK"
            if h == swap:
                batt, status = float(rng.uniform(13.3, 13.6)), "Maintenance"
            r = {"Station": st, "Site": site, "Elevation (m)": elev, "Timestamp": ts, "Status": status,
                 "Temperature (C)": float(round(temp, 1)),
                 "Humidity (%)": float(round(np.clip(h0 - 1.5 * (temp - tbase) + rng.normal(0, 4) + (25 if rain else 0), 4, 100), 0)),
                 "Pressure (hPa)": float(round(p0 + drift - (6 if rain else 0), 1)),
                 "Wind Speed (m/s)": float(round(rng.gamma(2, 1.6 + (3 if rain else 0)), 1)), "Rainfall (mm)": rain,
                 "Battery (V)": float(round(batt, 2))}
            if off <= h < off + 3:
                r.update({c: None for c in cols[4:11]}, Status="Offline")
            s.add(r)
            s.compute(len(s.rows) - 1)
    n = len(s.rows)
    allrows, taken = range(n), set()
    ok = lambda i: s.rows[i]["Status"] == "OK"
    # traps
    i = pick(rng, allrows, lambda i: (s.rows[i]["Rainfall (mm)"] or 0) >= 10, taken)
    s.trap(i, "Rainfall (mm)", "A coastal storm: over 10 mm in an hour among mostly dry hours, and valid.")
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Site"] == "Ridge", taken)
    s.trap(i, "Pressure (hPa)", "At 1,480 m the air pressure is about 850 hPa: valid for the ridge station.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Status"] == "Maintenance", taken)
    s.trap(i, "Battery (V)", "The battery was swapped in this maintenance hour, so the voltage jumps back up.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Status"] == "Offline", taken)
    s.trap(i, "Temperature (C)", "The station was offline: no readings is correct.")
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Site"] == "Desert" and s.rows[i]["Temperature (C)"] > 38, taken)
    s.trap(i, "Temperature (C)", "A desert afternoon over 38 C is valid.")
    # errors
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Humidity (%)"] > 70, taken)
    s.rows[i]["Humidity (%)"] = float(rng.choice([104, 108, 112]))
    s.error(i, ["Humidity (%)"], "humidity above 100%", True, "Relative humidity cannot exceed 100%.")
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Site"] != "Ridge", taken)
    s.rows[i]["Pressure (hPa)"] = round(s.rows[i]["Pressure (hPa)"] / 10, 2)
    s.error(i, ["Pressure (hPa)"], "pressure in kPa", False, "Pressure written in kPa (one tenth) under an hPa header.")
    i = pick(rng, allrows, lambda i: ok(i) and s.rows[i]["Temperature (C)"] > 12, taken)
    s.rows[i]["Temperature (C)"] = -s.rows[i]["Temperature (C)"]
    s.compute(i)
    s.error(i, ["Temperature (C)"], "temperature sign flipped", False, "A minus sign on an ordinary hour at this site.")
    i = pick(rng, allrows, lambda i: ok(i), taken)
    s.rows[i]["Battery (V)"] = round(s.rows[i]["Battery (V)"] * 10, 1)
    s.error(i, ["Battery (V)"], "battery decimal slip", False, "A 12 V battery read as 10x.")
    i = pick(rng, allrows, lambda i: ok(i) and 0 < i < n - 1 and s.rows[i - 1]["Station"] == s.rows[i]["Station"] == s.rows[i + 1]["Station"], taken)
    s.rows[i]["Timestamp"] = s.rows[i]["Timestamp"] - dt.timedelta(days=1)
    s.error(i, ["Timestamp"], "timestamp a day off", True, "This station's hourly readings run in order; this one is stamped the day before its neighbours.")
    i = pick(rng, allrows, lambda i: ok(i), taken)
    s.rows[i]["Humidity (%)"] = None
    s.error(i, ["Humidity (%)"], "reading missing while OK", True, "A blank humidity on an hour whose Status is OK and every other reading is there.")
    i = pick(rng, allrows, lambda i: ok(i) and (s.rows[i]["Rainfall (mm)"] or 0) > 0, taken)
    s.rows[i]["Rainfall (mm)"] = -s.rows[i]["Rainfall (mm)"]
    s.error(i, ["Rainfall (mm)"], "negative rainfall", False, "Rainfall cannot be negative.")
    i = pick(rng, allrows, lambda i: ok(i) and i < n - 1, taken)
    s.insert_copy(i, "reading logged twice", "The same station and hour logged twice.")
    return s


# ---------------------------------------------------------------- insurance claims
def claims(rng):
    lines = {"Auto": (3500, 0.9, [500, 1000]), "Home": (9000, 1.1, [1000, 2500]), "Health": (1400, 0.8, [0]),
             "Travel": (700, 0.7, [100])}
    regions = ["North", "South", "East", "West", "Central"]
    cols = ["Claim ID", "Policy No", "Line", "Region", "Incident Date", "Report Date", "Days to Report", "Close Date",
            "Status", "Claimed Amount", "Deductible", "Approved Amount", "Paid Amount", "Adjuster"]
    has = lambda r: r["Approved Amount"] is not None
    f = {"Days to Report": [(yes, "={Report Date}-{Incident Date}", lambda r: (r["Report Date"] - r["Incident Date"]).days)],
         "Paid Amount": [(has, '=IF({Approved Amount}="","",MAX(0,{Approved Amount}-{Deductible}))', lambda r: round(max(0, r["Approved Amount"] - r["Deductible"]), 2)),
                         (yes, '=IF({Approved Amount}="","",MAX(0,{Approved Amount}-{Deductible}))', lambda r: None)]}
    s = Sheet("claims_register", "Insurance claims register across four lines: closed claims are approved and paid net "
              "of the deductible, denied ones approve 0, open ones have no close date or approval yet.", cols, f)
    n = int(rng.integers(380, 520))
    d0 = dt.date(2026, 1, 1)
    policies = [f"P-{int(x)}" for x in rng.choice(np.arange(100000, 999999), n // 2 + 20, replace=False)]
    adjusters = [f"ADJ-{k:02d}" for k in rng.choice(40, 9, replace=False)]
    for k in range(n):
        line = str(rng.choice(list(lines), p=[0.4, 0.25, 0.25, 0.1]))
        med, sd, deds = lines[line]
        inc = d0 + dt.timedelta(days=int(rng.integers(0, 250)))
        rep = inc + dt.timedelta(days=int(min(rng.exponential(4), 60)))
        status = str(rng.choice(["Closed", "Open", "Denied"], p=[0.65, 0.25, 0.1]))
        claimed = float(round(rng.lognormal(np.log(med), sd), 2))
        r = {"Claim ID": f"CLM-26-{10000 + k * 3}", "Policy No": str(rng.choice(policies)), "Line": line,
             "Region": str(rng.choice(regions)), "Incident Date": inc, "Report Date": rep, "Status": status,
             "Close Date": None if status == "Open" else rep + dt.timedelta(days=int(rng.integers(5, 90))),
             "Claimed Amount": claimed, "Deductible": float(rng.choice(deds)), "Adjuster": str(rng.choice(adjusters)),
             "Approved Amount": None if status == "Open" else 0.0 if status == "Denied" else float(round(claimed * rng.uniform(0.6, 1), 2))}
        s.add(r)
        s.compute(len(s.rows) - 1)
    allrows, taken = range(n), set()
    st = lambda i, x: s.rows[i]["Status"] == x
    # traps
    i = pick(rng, allrows, lambda i: st(i, "Closed") and s.rows[i]["Line"] == "Home", taken)
    s.rows[i]["Claimed Amount"] = float(rng.choice([850000, 640000, 1120000]))
    s.rows[i]["Approved Amount"] = round(s.rows[i]["Claimed Amount"] * 0.92, 2)
    s.compute(i)
    s.trap(i, "Claimed Amount", "A house lost to fire: a claim far above the line's usual, approved and valid.")
    i = pick(rng, allrows, lambda i: st(i, "Denied"), taken)
    s.trap(i, "Approved Amount", "A denied claim approves 0.")
    i = pick(rng, allrows, lambda i: st(i, "Open"), taken)
    s.trap(i, "Close Date", "An open claim has no close date yet.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Line"] == "Health", taken)
    s.trap(i, "Deductible", "Health claims carry no per-claim deductible on these policies: 0 is valid.")
    i = pick(rng, allrows, lambda i: st(i, "Closed"), taken)
    s.rows[i]["Report Date"] = s.rows[i]["Incident Date"] + dt.timedelta(days=int(rng.integers(120, 200)))
    s.rows[i]["Close Date"] = s.rows[i]["Report Date"] + dt.timedelta(days=20)
    s.compute(i)
    s.trap(i, "Days to Report", "A late report months after the incident: rare but within the policy's filing window.")
    # errors
    i = pick(rng, allrows, lambda i: s.rows[i]["Days to Report"] >= 2, taken)
    s.rows[i]["Report Date"] = s.rows[i]["Incident Date"] - dt.timedelta(days=int(rng.integers(3, 30)))
    s.compute(i)
    s.error(i, ["Report Date", "Incident Date"], "reported before it happened", True, "Report Date is before Incident Date (Days to Report negative).")
    i = pick(rng, allrows, lambda i: st(i, "Open"), taken)
    s.rows[i]["Close Date"] = s.rows[i]["Report Date"] + dt.timedelta(days=30)
    s.error(i, ["Close Date", "Status"], "close date on an open claim", True, "An open claim with a close date.")
    i = pick(rng, allrows, lambda i: st(i, "Closed") and s.rows[i]["Claimed Amount"] < 50000, taken)
    s.rows[i]["Approved Amount"] = round(s.rows[i]["Claimed Amount"] * float(rng.choice([1.5, 2, 3])), 2)
    s.compute(i)
    s.error(i, ["Approved Amount"], "approved more than claimed", True, "Approved Amount above Claimed Amount.")
    i = pick(rng, allrows, lambda i: st(i, "Open"), taken)
    s.rows[i]["Claimed Amount"] = round(s.rows[i]["Claimed Amount"] * 100, 2)
    s.error(i, ["Claimed Amount"], "claimed x100", False, "Claimed Amount 100x its line's usual size (a lost decimal point).")
    i = pick(rng, allrows, lambda i: True, taken)
    s.rows[i]["Region"] = misspell(s.rows[i]["Region"], rng)
    s.error(i, ["Region"], "misspelt region", False, f"Region {s.rows[i]['Region']!r} is a misspelling.")
    i = pick(rng, allrows, lambda i: st(i, "Closed") and s.rows[i]["Line"] == "Health", taken)
    s.rows[i]["Deductible"] = 1000.0
    s.compute(i)
    s.error(i, ["Deductible"], "deductible on a health claim", True, "Every other Health claim has a deductible of 0.")
    i = pick(rng, allrows, lambda i: st(i, "Closed") and s.rows[i]["Paid Amount"] > 100, taken)
    s.rows[i]["Paid Amount"] = s.rows[i]["Approved Amount"]
    s.typed[i].add("Paid Amount")
    s.error(i, ["Paid Amount"], "paid typed without the deductible", True, "Paid Amount is typed as the full approval, the deductible not taken off.")
    i = pick(rng, allrows, lambda i: i < n - 1, taken)
    s.insert_copy(i, "claim entered twice", "The same claim ID and values entered twice.")
    return s


# ---------------------------------------------------------------- project budgets
def budgets(rng):
    cats = [("Labour", 0.45), ("Materials", 0.25), ("Subcontract", 0.2), ("Travel", 0.03), ("Contingency", 0.07)]
    cols = ["Project Code", "Project Manager", "Cost Category", "Month", "Budget", "Actual", "Committed", "Variance",
            "Variance %", "Forecast"]
    nz = lambda r: bool(r["Budget"])
    f = {"Variance": [(yes, "={Budget}-{Actual}", lambda r: round(r["Budget"] - r["Actual"], 2))],
         "Variance %": [(nz, '=IF({Budget}=0,"",ROUND({Variance}/{Budget}*100,1))', lambda r: round(r["Variance"] / r["Budget"] * 100, 1)),
                        (yes, '=IF({Budget}=0,"",ROUND({Variance}/{Budget}*100,1))', lambda r: None)],
         "Forecast": [(yes, "={Actual}+{Committed}", lambda r: round(r["Actual"] + r["Committed"], 2))]}
    s = Sheet("project_costs", "Monthly project cost report: budget against actual by cost category, variance = "
              "budget - actual (negative = overspend); travel is often unused and contingency drawn only when needed.", cols, f)
    months = int(rng.integers(7, 10))
    pms = ["PM-A", "PM-B", "PM-C", "PM-D", "PM-E"]
    for p in range(int(rng.integers(9, 13))):
        size = float(rng.lognormal(np.log(400000), 0.9))
        start = int(rng.integers(0, 3))
        code, pm = f"PRJ-26{p + 11:02d}", str(rng.choice(pms))
        for m in range(months):
            month = (dt.date(2026, m + 2, 1) - dt.timedelta(days=1))
            w = 0 if m < start else np.sin(np.pi * (m - start + 0.5) / (months - start)) + 0.2
            for cat, share in cats:
                b = float(round(size * share * w / months, -2))
                if cat == "Contingency":
                    a = 0.0 if rng.random() < 0.8 else float(round(b * rng.uniform(0.5, 2.5), 2))
                elif cat == "Travel":
                    a = 0.0 if rng.random() < 0.5 else float(round(b * rng.uniform(0.3, 1.6), 2))
                else:
                    a = float(round(b * rng.normal(1, 0.12), 2))
                if b == 0:
                    a = 0.0
                s.add({"Project Code": code, "Project Manager": pm, "Cost Category": cat, "Month": month, "Budget": b,
                       "Actual": a, "Committed": float(round(b * rng.uniform(0, 0.3), -1)) if b else 0.0})
                s.compute(len(s.rows) - 1)
    n = len(s.rows)
    allrows, taken = range(n), set()
    main = lambda i: s.rows[i]["Cost Category"] in ("Labour", "Materials", "Subcontract") and s.rows[i]["Budget"] > 0
    # traps
    i = pick(rng, allrows, lambda i: main(i), taken)
    s.rows[i]["Actual"] = round(s.rows[i]["Budget"] * 1.45, 2)
    s.compute(i)
    s.trap(i, "Variance %", "A real 45% overspend in one month: a negative variance that is the report's point, valid.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Cost Category"] == "Travel" and s.rows[i]["Budget"] > 0 and s.rows[i]["Actual"] == 0, taken)
    s.trap(i, "Actual", "Travel budgeted but not used this month: 0 actual is valid.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Budget"] == 0, taken)
    s.trap(i, "Variance %", "The project had not started: no budget, so no variance percent.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Cost Category"] == "Contingency" and s.rows[i]["Actual"] > s.rows[i]["Budget"] > 0, taken)
    s.trap(i, "Actual", "Contingency drawn above its monthly share to cover a risk: valid.")
    # errors
    i = pick(rng, allrows, lambda i: main(i), taken)
    s.rows[i]["Actual"] = round(s.rows[i]["Actual"] * 10, 2)
    s.compute(i)
    s.error(i, ["Actual"], "actual x10", False, "Actual is 10x its budget and its neighbours: a slipped decimal point.")
    i = pick(rng, allrows, lambda i: main(i), taken)
    s.rows[i]["Budget"] = -s.rows[i]["Budget"]
    s.compute(i)
    s.error(i, ["Budget"], "budget sign flipped", False, "A negative budget.")
    i = pick(rng, allrows, lambda i: main(i) and abs(s.rows[i]["Variance"]) > 100, taken)
    s.rows[i]["Variance"] = -s.rows[i]["Variance"]
    s.typed[i].add("Variance")
    s.compute(i)
    s.error(i, ["Variance"], "variance typed with the wrong sign", True, "Variance is typed as Actual - Budget, not Budget - Actual.")
    i = pick(rng, allrows, lambda i: True, taken)
    s.rows[i]["Cost Category"] = misspell(s.rows[i]["Cost Category"], rng)
    s.error(i, ["Cost Category"], "misspelt category", False, f"Cost Category {s.rows[i]['Cost Category']!r} is a misspelling.")
    i = pick(rng, allrows, lambda i: main(i) and abs(s.rows[i]["Variance %"]) > 2, taken)
    s.rows[i]["Variance %"] = round(s.rows[i]["Variance %"] * 10, 1)
    s.typed[i].add("Variance %")
    s.error(i, ["Variance %"], "variance percent typed wrong", True, "Variance % is typed and is not Variance / Budget.")
    i = pick(rng, allrows, lambda i: s.rows[i]["Committed"] > 0, taken)
    s.rows[i]["Committed"] = -s.rows[i]["Committed"]
    s.compute(i)
    s.error(i, ["Committed"], "committed sign flipped", False, "Negative open commitments.")
    i = pick(rng, allrows, lambda i: i < n - 1, taken)
    s.insert_copy(i, "cost line entered twice", "The same project, category and month entered twice.")
    return s


SUBJECTS = {"payroll": payroll, "inventory": inventory, "grades": grades, "sensors": sensors, "claims": claims,
            "budgets": budgets}

if __name__ == "__main__":
    seed, out, keyfile = int(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)
    key = {}
    for subject in rng.choice(sorted(SUBJECTS), 4, replace=False):
        s = SUBJECTS[str(subject)](rng)
        (out / f"{s.name}.json").write_text(json.dumps(s.dump()))
        key[s.name] = {"domain": s.domain, "errors": s.errors, "traps": s.traps}
        print(s.name, len(s.rows), "rows,", len(s.errors), "errors,", len(s.traps), "traps")
    keyfile.parent.mkdir(parents=True, exist_ok=True)
    keyfile.write_text(json.dumps(key, indent=1))
