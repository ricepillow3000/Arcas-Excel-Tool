"""AH-213: a subtotal is checked against its own group. The layout reader sends subtotal rows blank (AH-212), so a
subtotal that left out a row of its group, a grand total that added the subtotals and the rows they already add, and a
subtotal typed over all went unseen (9 planted on the complex bench's tuning episodes). Read from the pane's R1C1
formulas, on a plain sheet (the subtotal rows as typed) and as the layout reader sends them (blank, formulas kept).
Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Group", "Item", "Qty", "Value"]
GROUPS = ("Fasteners", "Hand tools", "Paint")


def sheet(size=6, groups=GROUPS, value=None):
    """A stock list: each group's items, then its subtotal row (=SUBTOTAL(9,..) of its whole group), then a grand total
    (=SUBTOTAL(9,..) over the whole column, which skips the SUBTOTALs inside it, as Excel does). value(i): an item's
    formula in Value, or None for a typed number. -> rows, formulas, the subtotal rows, the grand total row."""
    rows, formulas, subs = [], [], []
    for g in groups:
        first = len(rows)
        for k in range(size):
            rows.append([g if k == 0 else "", f"{g[:3].upper()}-{k}", 2 + k, round(10.5 + 7 * k + len(g), 2)])
            formulas.append([None, None, None, value(k) if value else None])
        subs.append(len(rows))
        rows.append(["", f"Subtotal {g}", "", round(sum(r[3] for r in rows[first:]), 2)])
        formulas.append([None, None, None, f"=SUBTOTAL(9,R[-{size}]C:R[-1]C)"])
    rows.append(["", "Grand total", "", round(sum(rows[s][3] for s in subs), 2)])
    formulas.append([None, None, None, f"=SUBTOTAL(9,R[-{len(rows) - 1}]C:R[-1]C)"])
    return rows, formulas, subs, len(rows) - 1


def scan(rows, formulas, blank=()):
    """blank: the rows sent as the layout reader sends a subtotal (its values blank, its formulas kept)."""
    sent = [["" if i in blank else v for v in r] for i, r in enumerate(rows)]
    r = APP.post("/scan", json={"columns": COLS, "rows": sent, "strength": 5, "formulas": formulas})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def said(out):
    return {i: r["reason"] for i, r in enumerate(out) if r.get("severity") and "subtotal" in [k for k, _ in r.get("kinds", [])]}


def both_ways(rows, formulas, subs, total):
    """The sheet as typed, and as the layout reader sends it: the same rows said."""
    plain, layout = said(scan(rows, formulas)), said(scan(rows, formulas, blank={*subs, total}))
    assert plain.keys() == layout.keys()
    return plain, scan(rows, formulas)


def test_honest_subtotals_and_a_grand_total_of_subtotal_say_nothing():
    rows, formulas, subs, total = sheet()
    assert both_ways(rows, formulas, subs, total)[0] == {}


def test_a_subtotal_that_leaves_out_the_row_right_above_it_is_flagged_on_its_cell():
    rows, formulas, subs, total = sheet()
    formulas[subs[1]][3] = "=SUBTOTAL(9,R[-6]C:R[-2]C)"
    flagged, out = both_ways(rows, formulas, subs, total)
    assert list(flagged) == [subs[1]]
    assert flagged[subs[1]] == "The subtotal in Value adds 5 of the 6 rows of its group and leaves out the row right above it"
    assert out[subs[1]]["severity"] == "Medium" and out[subs[1]]["cells"] == ["Value"]


def test_a_subtotal_that_leaves_out_the_first_row_of_its_group_is_flagged():
    rows, formulas, subs, total = sheet(value=lambda k: "=RC[-1]*2.5")
    formulas[subs[0]][3] = "=SUBTOTAL(9,R[-5]C:R[-1]C)"
    flagged, _ = both_ways(rows, formulas, subs, total)
    assert flagged == {subs[0]: "The subtotal in Value adds 5 of the 6 rows of its group and leaves out its first row"}


def test_an_average_that_leaves_out_a_row_of_its_group_is_flagged_as_an_average():
    rows, formulas, subs, total = sheet()
    for s in subs:
        formulas[s][3] = "=AVERAGE(R[-6]C:R[-1]C)"
    formulas[subs[2]][3] = "=AVERAGE(R[-6]C:R[-2]C)"
    formulas[total][3] = None
    flagged, _ = both_ways(rows, formulas, subs, total)
    assert flagged == {subs[2]: "The average in Value adds 5 of the 6 rows of its group and leaves out the row right above it"}


def test_a_subtotal_leaving_out_a_row_is_judged_only_where_two_other_subtotals_add_their_whole_group():
    # at the limit: two others add all of theirs, so this one's way is the odd one
    rows, formulas, subs, total = sheet()
    formulas[subs[2]][3] = "=SUBTOTAL(9,R[-6]C:R[-2]C)"
    assert list(both_ways(rows, formulas, subs, total)[0]) == [subs[2]]
    # one other only: an opening balance a "Total movements" leaves out is the sheet's own layout
    rows, formulas, subs, total = sheet(groups=GROUPS[:2])
    formulas[subs[1]][3] = "=SUBTOTAL(9,R[-6]C:R[-2]C)"
    assert both_ways(rows, formulas, subs, total)[0] == {}


def test_a_grand_total_that_adds_the_subtotals_and_their_rows_counts_them_twice():
    rows, formulas, subs, total = sheet()
    formulas[total][3] = f"=SUM(R[-{total}]C:R[-1]C)"
    flagged, out = both_ways(rows, formulas, subs, total)
    assert flagged == {total: "The total in Value adds 3 subtotals and the 18 rows they already add, so those rows count twice"}
    assert out[total]["severity"] == "Medium" and out[total]["cells"] == ["Value"]


def test_a_subtotal_of_the_whole_column_counts_a_sum_inside_it_twice():
    rows, formulas, subs, total = sheet()
    formulas[subs[0]][3] = "=SUM(R[-6]C:R[-1]C)"  # SUBTOTAL skips only the SUBTOTALs inside its range
    flagged, _ = both_ways(rows, formulas, subs, total)
    assert flagged == {total: "The total in Value adds 1 subtotal and the 6 rows it already adds, so those rows count twice"}


def test_a_grand_total_of_the_subtotals_alone_says_nothing():
    rows, formulas, subs, total = sheet()
    formulas[total][3] = "=" + "+".join(f"R[-{total - s}]C" for s in subs)
    assert both_ways(rows, formulas, subs, total)[0] == {}


def test_a_typed_subtotal_that_is_not_its_groups_sum_is_flagged_and_one_that_is_says_nothing():
    rows, formulas, subs, total = sheet()
    formulas[subs[1]][3] = None  # typed over, still right
    assert said(scan(rows, formulas)) == {}
    rows[subs[1]][3] = round(rows[subs[1]][3] + 10, 2)  # typed over, and wrong
    out = scan(rows, formulas)
    assert said(out) == {subs[1]: f"Value {rows[subs[1]][3]:g} is typed where its other subtotals are formulas, and the rows "
                                  f"of its group add up to {rows[subs[1]][3] - 10:g}"}
    assert out[subs[1]]["severity"] == "Medium"


def test_a_running_balance_and_a_rolling_sum_are_never_a_subtotal():
    rows = [[f"d{k}", "", 5 + k % 3, 100 + 5 * k] for k in range(30)]
    running = [[None, None, None, "=R[-1]C+RC[-1]" if k else None] for k in range(30)]
    assert said(scan(rows, running)) == {}
    rolling = [[None, None, None, f"=SUM(R[-{min(k, 3)}]C:R[-1]C)" if k else None] for k in range(30)]
    assert said(scan(rows, rolling)) == {}


def test_a_subtotal_filled_right_across_its_row_is_said_once_on_its_first_column():
    rows, formulas, subs, total = sheet()
    for r, f in zip(rows, formulas, strict=True):
        r.append(r[3] * 2 if isinstance(r[3], float) else "")
        f.append(f[3])
    cols = [*COLS, "Value 2"]
    formulas[subs[1]][3] = formulas[subs[1]][4] = "=SUBTOTAL(9,R[-6]C:R[-2]C)"
    r = APP.post("/scan", json={"columns": cols, "rows": rows, "strength": 5, "formulas": formulas}).get_json()["rows"]
    assert r[subs[1]]["reason"] == ("The subtotal in Value adds 5 of the 6 rows of its group and leaves out the row right "
                                    "above it, as does 1 other column of this row")
    assert r[subs[1]]["cells"] == ["Value"]


def test_a_row_written_another_way_above_a_group_is_no_row_of_it():
    # a row of typed numbers over a group of formulas (a header's second row of dates read as data) is never "left out"
    rows, formulas, subs, total = sheet(value=lambda k: "=RC[-1]*2.5")
    rows.insert(0, ["", "", "", 46023])
    formulas.insert(0, [None, None, None, None])
    subs, total = [s + 1 for s in subs], total + 1
    formulas[total][3] = f"=SUBTOTAL(9,R[-{total - 1}]C:R[-1]C)"
    assert both_ways(rows, formulas, subs, total)[0] == {}


def test_a_row_worked_out_from_the_rows_above_ends_the_group_above_it():
    # a P&L: lines, then Gross profit =R[-6]C-R[-1]C (no subtotal of its own above), then costs and their total, which
    # adds the costs alone: the lines above Gross profit are another group, never left out
    rows, formulas, subs, total = sheet(groups=(*GROUPS, "Glue"))
    gross = subs[0]
    rows[gross][1], formulas[gross][3] = "Gross profit", "=R[-6]C-R[-1]C"
    assert both_ways(rows, formulas, [s for s in subs if s != gross], total)[0] == {}


def test_a_typed_subtotal_rounded_to_its_own_last_digit_still_adds_up():
    rows, formulas, subs, total = sheet()
    formulas[subs[1]][3] = None
    rows[subs[1] - 1][3] += 0.3  # the group adds up to x.3...
    rows[subs[1]][3] = round(sum(r[3] for r in rows[subs[1] - 6:subs[1]]))  # ...typed to the whole number: its own rounding
    assert said(scan(rows, formulas)) == {}
