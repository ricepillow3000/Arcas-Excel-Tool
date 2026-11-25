"""AH-222: a typed row every other row's formula reads by its fixed row number (=ROUND(RC2*R5C,0), =RC3*R5C3+...,
">="&R4C) is the table's parameters, not a record: each column's checks judged a weight among amounts, so a cash flow's
S-curve weights were 66 Medium cells, a marks book's assessment weights 7 and a trap, a summary's From/To dates 2
(complex bench, tuning episodes 1 and 3, B episode 10). The row is left out of the column checks ("Parameter row") and
read across instead: a weight 10 times both its neighbours is still a slip (a weight 0.184 among 0.0172 and 0.0195).
Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
START = 3  # the header on sheet row 4 (0-based 3): data row 0 is sheet row 5, so its cells are R5C...


def marks(readers=40, weights=(0.2, 0.2, 0.6)):
    """A marks book: the weights row first, then 40 students; the first `readers` students' Weighted reads the weights
    by their fixed row (R5C3...), the rest are typed. -> columns, rows, formulas."""
    cols = ["ID", "Name", "CW1", "CW2", "Exam", "Weighted"]
    rows, formulas = [["", "", *weights, ""]], [[None] * 6]
    for i in range(40):
        m = [40 + (7 * i) % 50, 45 + (11 * i) % 45, 35 + (13 * i) % 60]
        rows.append([f"S{1000 + i}", f"Student {i}", *m, round(sum(a * w for a, w in zip(m, weights)))])
        formulas.append([None] * 5 + ["=ROUND(RC3*R5C3+RC4*R5C4+RC5*R5C5,0)" if i < readers else None])
    return cols, rows, formulas


def cash_flow(slip=None, w=(0.01, 0.03, 0.06, 0.09, 0.12, 0.14, 0.14, 0.12, 0.1, 0.09, 0.06, 0.04)):
    """A cash flow: the S-curve weights row first (12 weeks), then 30 cost lines, each week =ROUND(RC2*R5C,0) of the
    line's budget. slip: (week, factor) typed into the weights row."""
    cols = ["Division", "Budget", *[f"W{k}" for k in range(1, 13)]]
    weights = list(w)
    if slip:
        weights[slip[0]] = round(weights[slip[0]] * slip[1], 6)
    rows, formulas = [["S-curve weight", "", *weights]], [[None] * 14]
    for i in range(30):
        b = 100000 + 37000 * i
        rows.append([f"{i:02d} Trade {i}", b, *[round(b * x) for x in weights]])
        formulas.append([None, None, *["=ROUND(RC2*R5C,0)"] * 12])
    return cols, rows, formulas


def scan(cols, rows, formulas, start_row=START):
    r = APP.post("/scan", json={"columns": cols, "rows": rows, "strength": 5, "formulas": formulas, "start_row": start_row})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def flagged(out):
    return {i: r["reason"] for i, r in enumerate(out) if r.get("severity") in ("High", "Medium")}


def test_a_weights_row_every_rows_formula_reads_is_no_record():
    out = scan(*marks())
    assert 0 not in flagged(out)
    assert out[0]["reason"] == "Parameter row (the table's formulas read it) - not checked"


def test_a_row_only_two_formulas_read_is_still_a_record_and_three_make_it_parameters():
    assert 0 in flagged(scan(*marks(readers=2)))
    assert 0 not in flagged(scan(*marks(readers=3)))


def test_a_reference_to_another_sheet_or_a_range_never_makes_a_parameter_row():
    cols, rows, formulas = marks()
    for f in formulas[1:]:
        f[5] = "=ROUND(RC3*'Other'!R5C3+RC4*R5C4:R6C4+RC5,0)"
    assert 0 in flagged(scan(cols, rows, formulas))


def test_without_where_the_table_sits_the_row_is_judged_as_before():
    assert 0 in flagged(scan(*marks(), start_row=None))


def test_a_cash_flows_s_curve_weights_say_nothing():
    out = scan(*cash_flow())
    assert flagged(out) == {}


def test_a_weight_ten_times_both_its_neighbours_is_flagged_on_its_cell_alone():
    out = scan(*cash_flow(slip=(6, 10)))
    assert list(flagged(out)) == [0]
    assert out[0]["cells"] == ["W7"]
    assert out[0]["reason"] == "W7 1.4 is 10 times the values beside it in this row the table's formulas read (W6 0.14, W8 0.12)"
    assert out[0]["kinds"] == [["series", "W7"]]


def test_a_weight_twice_its_neighbours_is_left_alone():
    assert flagged(scan(*cash_flow(slip=(6, 2)))) == {}


def test_a_jump_is_read_only_between_neighbours_that_agree_within_twice():
    w = [0.01, 0.03, 0.06, 0.09, 0.05, 0.7, 0.1, 0.12, 0.1, 0.09, 0.06, 0.04]  # 0.7 between 0.05 and 0.1: twice
    assert list(flagged(scan(*cash_flow(w=w)))) == [0]
    w[6] = 0.11  # 0.05 and 0.11 no longer agree: no jump to read
    assert flagged(scan(*cash_flow(w=w))) == {}
