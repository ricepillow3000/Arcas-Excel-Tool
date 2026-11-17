"""AH-182: a number column pasted twice. A neuroscience student pasted one data series into two columns; retractions came
from copied blocks of numbers (Pruitt's spider papers, a 2016 Cell paper's motor values duplicated across two groups).
Two number columns equal row for row (blank on the same rows), each with 10+ numbers and 5+ distinct values, neither
in order (a time axis or an ID is no measurement) nor mostly formulas (=B2 is a copy by design), are one note (Low) on
the first row both fill. Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Sample", "Series 1", "Series 2", "Series 3"]


def sheet(n=40):
    """Three measurements that wander (never in order), Series 3 a paste of Series 2."""
    rows = [[f"S{i}", round(10 + (i * 37 % 23) / 4, 2), round(5 + (i * 53 % 29) / 10, 2), None] for i in range(n)]
    for r in rows:
        r[3] = r[2]
    return rows


def scan(rows, columns=COLS, formulas=None):
    body = {"columns": columns, "rows": rows, "strength": 5}
    if formulas is not None:
        body["formulas"] = formulas
    r = APP.post("/scan", json=body)
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def notes(out):
    return {i: r["reason"] for i, r in enumerate(out) if "row for row: was one column pasted twice?" in r["reason"]}


def test_a_number_column_pasted_twice_is_one_note_on_the_first_row_naming_both():
    out = scan(sheet())
    assert {i: r["reason"] for i, r in enumerate(out) if r["severity"]} == \
        {0: "Series 3 is the same 40 numbers as Series 2, row for row: was one column pasted twice?"}
    assert out[0]["severity"] == "Low" and out[0]["cells"] == ["Series 2", "Series 3"]
    assert not out[0]["likely"] and not out[0]["maybe"], "which copy is wrong is unknown: never a fix"


def test_the_note_sits_on_the_first_row_both_fill_and_blanks_on_the_same_rows_are_the_same():
    rows = sheet()
    for i in (0, 1, 7):
        rows[i][2] = rows[i][3] = None
    assert notes(scan(rows)) == {2: "Series 3 is the same 37 numbers as Series 2, row for row: was one column pasted twice?"}


def test_a_blank_on_another_row_or_one_other_value_is_no_copy():
    rows = sheet()
    rows[5][3] = None
    assert notes(scan(rows)) == {}
    rows = sheet()
    rows[5][3] += 1
    assert notes(scan(rows)) == {}


def test_ten_numbers_are_enough_and_nine_are_not():
    for filled, said in ((10, True), (9, False)):
        rows = sheet()
        for r in rows[filled:]:
            r[2] = r[3] = None
        assert bool(notes(scan(rows))) is said, filled


def test_five_distinct_values_are_enough_and_four_are_not():
    for distinct, said in ((5, True), (4, False)):
        rows = sheet()
        for i, r in enumerate(rows):
            r[2] = r[3] = [3.5, 1.25, 4.75, 2.0, 0.5][(i * 3) % distinct]
        assert bool(notes(scan(rows))) is said, distinct


def test_a_column_in_order_is_a_time_axis_or_an_id_never_a_pasted_measurement():
    for step in (1, -1):
        rows = sheet()
        for i, r in enumerate(rows):
            r[2] = r[3] = 2000 + step * (i // 2)  # in order, with repeats: a year per two rows
        assert notes(scan(rows)) == {}, step
    rows = sheet()
    rows[0][2] = rows[0][3] = 2100  # one step out of order: a measurement again
    for i, r in enumerate(rows[1:]):
        r[2] = r[3] = 2000 + i // 2
    assert notes(scan(rows))


def test_a_column_mostly_built_by_formulas_is_a_copy_by_design():
    for made, said in ((21, False), (20, True)):
        grid = [[None, None, None, "=RC[-1]" if i < made else None] for i in range(40)]
        assert bool(notes(scan(sheet(), formulas=grid))) is said, made


def test_the_pairs_are_looked_for_among_the_first_300_number_columns_only():
    rows = sheet()
    for at, said in ((299, True), (300, False)):
        columns = ["Sample"] + [f"M{j}" for j in range(at)] + ["Copy"]
        grid = [[r[0]] + [j + (i * 37 % 23) / 4 for j in range(at)] for i, r in enumerate(rows)]
        for g in grid:
            g.append(g[-1])  # Copy repeats the last measurement: the 300th number column, or the 301st
        assert any("Copy is the same 40 numbers as" in r["reason"] for r in scan(grid, columns)) is said, at
