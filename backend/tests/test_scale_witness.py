"""AH-224: AH-223 let a row's own arithmetic confirm a value by_scale would call a slip of zeros (a real entry 100x its
account's usual size, its debits equal to its credits). But a value worked out from the slip repeats it: a bill of
quantities' Amount =Qty*Rate agreed with a Qty typed 7000 for 700 m2, so the complex bench's planted slip (granite BOQ)
went quiet. A formula reading the cell is no witness for it (as `_reads` in in_step, AH-208); a typed Amount still is.
Synthetic sheets only."""
import random

from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Item", "Unit", "Qty", "Rate", "Amount"]
# usual quantities and rates per unit: kg of steel keeps the whole column wide, so a m2 typed 10x is no breach of it
UNITS = {"m2": (700, 120, 45), "m3": (90, 15, 150), "nr": (12, 3, 300), "kg": (8000, 1200, 2)}


def boq(seed=0):
    r = random.Random(seed)
    rows = []
    for unit, (mean, sd, rate) in UNITS.items():
        for _ in range(30):
            q, p = max(1, round(r.gauss(mean, sd))), round(r.gauss(rate, rate / 10), 2)
            rows.append([None, unit, q, p, round(q * p, 2)])
    r.shuffle(rows)
    for i, row in enumerate(rows):
        row[0] = f"{i + 1}.{i % 7 + 1}"
    return rows


def planted(seed=0):
    """The sheet with one m2 Qty typed 10x and its Amount worked out from it, as Excel would -> (rows, row)."""
    rows = boq(seed)
    i = next(i for i, x in enumerate(rows) if x[1] == "m2")
    rows[i][2] *= 10
    rows[i][4] = round(rows[i][2] * rows[i][3], 2)
    return rows, i


def scan(rows, formulas=None):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5, "formulas": formulas})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def test_a_qty_typed_10x_is_a_slip_though_its_amount_formula_repeats_it():
    for seed in range(5):
        rows, i = planted(seed)
        out = scan(rows, [[None, None, None, None, "=RC[-2]*RC[-1]"] for _ in rows])
        assert out[i]["severity"] == "Medium" and ["scale", "Qty"] in out[i]["kinds"], (seed, out[i])
        assert out[i]["cells"] == ["Qty"], (seed, out[i])


def test_a_big_qty_its_typed_amount_agrees_with_is_still_a_big_row_never_a_slip():
    # AH-223's intent: a typed Amount is a witness (someone wrote what the line cost), so the row's arithmetic confirms
    for seed in range(5):
        rows, i = planted(seed)
        out = scan(rows)
        assert ["scale", "Qty"] not in out[i]["kinds"], (seed, out[i])
        assert out[i]["severity"] not in ("High", "Medium"), (seed, out[i])


def test_a_rate_looked_up_from_its_unit_is_no_copy_of_the_qty_so_a_typed_amount_still_confirms_it():
    # the guard at its limit: a formula in the rule that never reads Qty (a rate from a rates table) leaves the typed
    # Amount a witness
    for seed in range(5):
        rows, i = planted(seed)
        out = scan(rows, [[None, None, None, "=VLOOKUP(RC[-2],Rates!R1C1:R4C2,2,0)", None] for _ in rows])
        assert ["scale", "Qty"] not in out[i]["kinds"], (seed, out[i])
        assert out[i]["severity"] not in ("High", "Medium"), (seed, out[i])
