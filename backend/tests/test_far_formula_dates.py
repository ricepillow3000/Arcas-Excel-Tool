"""AH-222: a date a formula works out (a Period =DATE(YEAR(RC1),MONTH(RC1),1)) is its inputs': a Date typed 2035 among
2025's made its Period "far outside the column's dates" too, a second cell coloured for one slip, on 3 ledgers of the
complex bench. As the limits never judge a formula's cell, a far date names the typed one alone; a date typed over the
column's formula is still judged. Synthetic sheets only."""
import datetime

from anomaly_hunter.server import create_app

APP = create_app().test_client()
PERIOD = "=DATE(YEAR(RC1),MONTH(RC1),1)"


def ledger():
    """60 postings through 2025: Date typed, Period its month's first day by formula, Amount typed."""
    rows, formulas = [], []
    for i in range(60):
        d = datetime.date(2025, 1, 4) + datetime.timedelta(days=6 * i)
        rows.append([d.isoformat(), d.replace(day=1).isoformat(), round(100 + 13.5 * (i % 17), 2)])
        formulas.append([None, PERIOD, None])
    return rows, formulas


def far(rows, formulas):
    r = APP.post("/scan", json={"columns": ["Date", "Period", "Amount"], "rows": rows, "strength": 5, "formulas": formulas})
    assert r.status_code == 200, r.get_json()
    return {i: o["cells"] for i, o in enumerate(r.get_json()["rows"]) if "far outside" in o.get("reason", "")}


def test_a_far_date_names_the_typed_cell_never_the_formula_worked_out_from_it():
    rows, formulas = ledger()
    rows[30][0], rows[30][1] = "2035-08-02", "2035-08-01"
    assert far(rows, formulas) == {30: ["Date"]}


def test_a_far_date_typed_over_the_columns_formula_is_still_named():
    rows, formulas = ledger()
    rows[30][1], formulas[30][1] = "2035-08-01", None
    assert far(rows, formulas) == {30: ["Period"]}
