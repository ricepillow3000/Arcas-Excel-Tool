"""AH-222: a row that writes one formula in every column, its total's too, is a ratio of its own (Gross margin % =
Gross profit / Revenue in each month and in the year), never a sum of its parts: "FY2025 0.535 does not add up: Q1 +
... + Q4 = 6.417" coloured 13 honest cells of a P&L (complex bench, tuning episode 1). Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
MONTHS = [f"M{k}" for k in range(1, 13)]
COLS = ["Line", *MONTHS, "Year"]
RATIO = "=IFERROR(R[-1]C/R[-3]C,0)"


def sheet():
    """40 lines typed month by month with a typed year that adds them, then Revenue, Cost, Profit and the margin row: each
    month and the year =IFERROR(Profit/Revenue,0). -> rows, formulas, the margin row."""
    rows, formulas = [], []
    for i in range(40):
        months = [round(100 + 7 * i + 3.5 * k + (k * i) % 5, 2) for k in range(12)]
        rows.append([f"Line {i}", *months, round(sum(months), 2)])
        formulas.append([None] * 14)
    rev = [1000 + 10 * k for k in range(12)]
    cost = [400 + 9 * k for k in range(12)]
    for label, v in (("Revenue", rev), ("Cost", cost), ("Profit", [a - b for a, b in zip(rev, cost)])):
        rows.append([label, *v, sum(v)])
        formulas.append([None] * 14)
    rows.append(["Margin", *[round((a - b) / a, 6) for a, b in zip(rev, cost)], round(sum(rev) - sum(cost), 6) / sum(rev)])
    formulas.append([None, *[RATIO] * 13])
    return rows, formulas, len(rows) - 1


def scan(rows, formulas):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5, "formulas": formulas})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def summed(out):
    return {i: r["reason"] for i, r in enumerate(out) if r.get("severity") in ("High", "Medium") and " does not add up" in r["reason"]}


def test_a_ratio_row_written_as_one_formula_across_the_total_too_is_never_a_sum():
    rows, formulas, margin = sheet()
    assert summed(scan(rows, formulas)) == {}


def test_a_ratio_row_whose_total_is_another_formula_is_still_judged_as_a_sum():
    rows, formulas, margin = sheet()
    formulas[margin][13] = "=IFERROR(R[-1]C/R[-2]C,0)"  # one formula across but the total's: no longer the row's own
    assert list(summed(scan(rows, formulas))) == [margin]


def test_a_typed_total_that_does_not_add_up_is_still_flagged():
    rows, formulas, margin = sheet()
    rows[5][13] += 10
    assert list(summed(scan(rows, formulas))) == [5]
