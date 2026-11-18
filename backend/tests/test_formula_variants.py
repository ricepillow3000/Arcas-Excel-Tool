"""AH-198 fix round 2: Excel's "inconsistent formula" check read down a column flags a lone break, the way a spelling
written once is a slip. A second formula the column writes on 5+ rows is its own (an invoice in yen rounds its
surcharge to whole yen, =ROUND(..,0), on every yen row), and so is any formula on every row of one label, those rows
only (each assembly's roll-up over its own parts, never a part's). 61 yen surcharges and 26 roll-ups were each "uses a
different formula from the other rows of its column". A few breaks stay flagged. Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Item", "Kind", "Qty", "Price", "Total"]
USUAL, WHOLE = "=ROUND(RC[-2]*RC[-1],2)", "=ROUND(RC[-2]*RC[-1],0)"


def sheet(n=80):
    rows = [[f"Item {i}", "Part", 2 + i % 7, 5.25 + i % 4, round((2 + i % 7) * (5.25 + i % 4), 2)] for i in range(n)]
    return rows, [[None, None, None, None, USUAL] for _ in rows]


def scan(rows, formulas):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5, "formulas": formulas})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def broken(out):
    return {i for i, r in enumerate(out) if "uses a different formula" in r["reason"]}


def test_a_second_formula_the_column_writes_on_five_rows_is_its_own():
    rows, formulas = sheet()
    for i in (3, 19, 35, 51, 67):
        formulas[i][4] = WHOLE
    assert broken(scan(rows, formulas)) == set()


def test_a_second_formula_written_on_four_rows_is_four_breaks():
    rows, formulas = sheet()
    for i in (3, 19, 35, 51):
        formulas[i][4] = WHOLE
    assert broken(scan(rows, formulas)) == {3, 19, 35, 51}


def assemblies(rows, formulas, at):
    """Rows `at` are assemblies: each rolls up the rows below it, a formula of its own."""
    for k, i in enumerate(at):
        rows[i][1] = "Assembly"
        formulas[i][4] = f"=RC[-2]*RC[-1]+SUM(R[1]C:R[{k + 2}]C)"


def test_a_formula_on_every_row_of_a_label_is_that_labels_own():
    rows, formulas = sheet()
    assemblies(rows, formulas, (0, 16, 32, 48, 64))
    assert broken(scan(rows, formulas)) == set()


def test_a_label_on_four_rows_is_too_few_to_have_a_formula_of_its_own():
    rows, formulas = sheet()
    assemblies(rows, formulas, (0, 16, 32, 48))
    assert broken(scan(rows, formulas)) == {0, 16, 32, 48}


def test_a_label_whose_rows_mostly_keep_the_usual_formula_has_none_of_its_own():
    rows, formulas = sheet()
    assemblies(rows, formulas, (0, 16, 32, 48, 64))
    rows[70][1] = "Assembly"  # a sixth assembly with the usual formula: the roll-ups are no role of the label
    assert broken(scan(rows, formulas)) == {0, 16, 32, 48, 64}


def ledger(receivables=10):
    """A journal's Debit: typed on most lines, a formula on every Receivable line (the revenue and VAT below it)."""
    rows, formulas = [], []
    for k in range(40):
        kind = "Receivable" if k < receivables else "Expense"
        rows.append([f"JE-{k}", kind, 1, 1.0, round(500 + 37.5 * k, 2)])
        formulas.append([None, None, None, None, "=R[1]C[1]+R[2]C[1]" if kind == "Receivable" else None])
    return rows, formulas


def typed_over(out):
    return {i for i, r in enumerate(out) if "is typed where the other rows of Kind Receivable use a formula" in r["reason"]}


def test_a_value_typed_on_the_one_row_of_ten_of_a_label_whose_others_use_a_formula_is_that_formula_typed_over():
    rows, formulas = ledger(10)
    formulas[4][4] = None
    out = scan(rows, formulas)
    assert typed_over(out) == {4} and out[4]["severity"] == "Medium" and out[4]["cells"] == ["Total"]


def test_nine_rows_of_a_label_are_too_few_to_know_its_formula():
    rows, formulas = ledger(9)
    formulas[4][4] = None
    assert typed_over(scan(rows, formulas)) == set()


def test_two_typed_rows_of_a_label_are_how_it_is_written():
    rows, formulas = ledger(12)
    formulas[4][4] = formulas[7][4] = None
    assert typed_over(scan(rows, formulas)) == set()
