"""AH-198: what a scan does with a cell that holds a formula. Its value is worked out from its inputs, so its odd value is
theirs: a journal's Net (=Debit-Credit) repeated every big debit as a second "weird" cell, a bill of materials'
Extended Qty every slip in Qty Per. The limits never judge or name a formula's cell; where the formula check pins the
broken cell, a sum about that cell names it alone; and a formula that names its own cell is Excel's circular reference.
Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Item", "Qty", "Price", "Gross"]
TAX = "=RC[-2]*RC[-1]*1.2"  # Gross = Qty x Price with 20% tax, the same text on every row


def sheet(n=60):
    rows = [[f"Item {i}", 2 + i % 7, 5 + i % 4, round((2 + i % 7) * (5 + i % 4) * 1.2, 2)] for i in range(n)]
    return rows, [[None, None, None, TAX] for _ in rows]


def scan(rows, formulas, columns=COLS):
    r = APP.post("/scan", json={"columns": columns, "rows": rows, "strength": 5, "formulas": formulas})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def flagged(out):
    return {i: (r["severity"], r["cells"]) for i, r in enumerate(out) if r["severity"] not in (None, "Noted")}


def test_a_slip_in_an_input_is_named_on_the_input_never_on_the_formula_it_feeds():
    rows, formulas = sheet()
    rows[29][1] = 400  # Qty 4 typed as 400: Gross =Qty*Price*1.2 follows it, a formula doing its job
    rows[29][3] = round(400 * rows[29][2] * 1.2, 2)
    out = scan(rows, formulas)
    assert flagged(out) == {29: ("Medium", ["Qty"])}
    assert "Gross" not in out[29]["reason"]


def test_a_typed_cell_in_a_column_of_formulas_is_still_judged_by_its_limits():
    rows, formulas = sheet()
    formulas[29][3] = None  # typed over the formula, and 100x too big: the limits judge a typed number
    rows[29][3] = rows[29][3] * 100
    out = scan(rows, formulas)
    assert "Gross weird limit" in out[29]["reason"] and "Gross" in out[29]["cells"]


def test_a_sum_about_the_cell_the_formula_check_pins_names_that_cell_alone():
    cols = ["Item", "Qty", "Price", "Total"]
    rows = [[f"Item {i}", 2 + i % 7, 5 + i % 4, (2 + i % 7) * (5 + i % 4)] for i in range(40)]
    formulas = [[None, None, None, "=RC[-2]*RC[-1]"] for _ in rows]
    formulas[29][3], rows[29][3] = None, rows[28][3] + 1  # typed over, and wrong: the previous row's total and one
    out = scan(rows, formulas, cols)
    assert "does not add up" in out[29]["reason"] and "typed number" in out[29]["reason"]
    assert out[29]["cells"] == ["Total"], "Qty and Price are fine: the formula check says Total is the broken cell"


def test_a_sum_about_a_part_the_formula_check_pins_names_that_part_alone():
    # AH-211 episodes 17 and 20: Net typed over =Gross-Tax-Fees made "Gross does not add up: Tax + Fees + Net" name Gross,
    # Tax and Fees too, each right
    cols = ["Item", "Gross", "Tax", "Fees", "Net"]
    rows = [[f"Item {i}", 1000 + 37 * i, 100 + 3 * i, 20 + i % 9, 0] for i in range(60)]
    for r in rows:
        r[4] = r[1] - r[2] - r[3]
    formulas = [[None, None, None, None, "=RC[-3]-RC[-2]-RC[-1]"] for _ in rows]
    formulas[29][4], rows[29][4] = None, rows[29][4] - 200  # typed over, and wrong
    out = scan(rows, formulas, cols)
    assert "does not add up" in out[29]["reason"] and "typed number" in out[29]["reason"], out[29]
    assert out[29]["cells"] == ["Net"], "Gross, Tax and Fees are fine: the formula check says Net is the broken cell"


def test_a_sum_with_no_formula_to_pin_it_still_names_every_cell_it_reads():
    cols = ["Item", "Qty", "Price", "Total"]
    rows = [[f"Item {i}", 2 + i % 7, 5 + i % 4, (2 + i % 7) * (5 + i % 4)] for i in range(40)]
    rows[29][3] += 1
    out = scan(rows, None, cols)
    assert "does not add up" in out[29]["reason"] and out[29]["cells"] == ["Qty", "Price", "Total"]


def test_a_formula_that_names_its_own_cell_is_a_circular_reference():
    rows, formulas = sheet()
    formulas[29][3], rows[29][3] = "=RC", 0  # Excel shows 0 (or the last value) for =RC
    formulas[40][3] = "=R[0]C[0]+1"
    out = scan(rows, formulas)
    assert "Gross refers to its own cell (a circular reference)" in out[29]["reason"]
    assert "Gross refers to its own cell (a circular reference)" in out[40]["reason"]
    assert out[29]["severity"] == "Medium" and out[29]["cells"] == ["Gross"]
    assert out[29]["formula"] == {"Gross": TAX}, "the column's own formula is the fix, as for any other formula"


def test_a_reference_to_another_row_or_column_or_text_reading_rc_is_no_circular_reference():
    rows, formulas = sheet()
    formulas[29][3] = '=RC[-2]*R[-1]C[-1]*1.2&"RC"'  # one row off, and the letters RC in a string
    out = scan(rows, formulas)
    assert "circular" not in out[29]["reason"] and "different formula" in out[29]["reason"]
