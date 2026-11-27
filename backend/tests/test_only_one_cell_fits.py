"""AH-237: a row that breaks Qty x Unit Price = Total, with every cell inside its usual range, has no odd cell to solve.
The row's own arithmetic still names the fix when exactly one cell has an answer written like its column (a whole
Qty, a price to the cent, a total to the cent) that makes the row add up. Made-up shop sheet."""
import numpy as np

from anomaly_hunter.agents.scan_agent import scan

PRICES = [3.49, 5.99, 7.99, 8.75, 12.5, 24.0, 6.25, 2.99]


def asked(cols, rows):  # as the pane does: the suggested limits first, then the scan under them
    return scan(cols, rows, limits=scan(cols, rows, fair=False)[2], fair=False)[1]


def shop(slips):
    r = np.random.default_rng(5)
    rows = []
    for i in range(80):
        q, p = int(r.integers(1, 13)), float(r.choice(PRICES))
        rows.append([f"SO-{i}", q, p, round(q * p, 2)])
    for i, (q, p, t) in slips.items():
        rows[i][1:] = [q, p, t]
    return rows, asked(["Order", "Qty", "Unit Price", "Total"], rows)


def test_a_total_that_only_the_total_can_explain_gets_its_fix():
    # 7 x 2.99 = 20.93: no whole Qty (10.34) and no price to the cent (4.42 makes 30.94) fits 30.93
    _, out = shop({30: (7, 2.99, 30.93)})
    assert "does not add up" in out[30]["reason"]
    assert out[30]["likely"] == {"Total": 20.93}


def test_a_row_where_two_cells_could_each_be_the_slip_gets_no_fix():
    # Qty 10 for 1: Qty 1 or Total 79.9 would each add up, and the numbers can't say which
    _, out = shop({12: (10, 7.99, 7.99)})
    assert "does not add up" in out[12]["reason"]
    assert not out[12].get("likely")


def test_a_row_that_adds_up_is_left_alone():
    rows, out = shop({})
    assert all("does not add up" not in o["reason"] and not o.get("likely") for o in out)


def test_an_answer_outside_the_columns_usual_values_is_no_second_choice():
    # Qty 200 would add up too, but no order in this sheet is near 200: only the Total can be the slip
    _, out = shop({30: (7, 2.99, 598.0)})
    assert "does not add up" in out[30]["reason"]
    assert out[30]["likely"] == {"Total": 20.93}


def test_a_sheet_that_only_adds_up_within_its_rounding_keeps_a_rounded_cell_as_a_second_choice():
    # Spend is Clicks x a CPC written to the cent, so Spend only follows the rule within that rounding. A CPC typed 2.9
    # for 1.88 makes Spend 2.9 x Clicks usual, but the CPC 1.88 (8626.52 / 4588 = 1.8801) is just as good an answer
    r = np.random.default_rng(9)
    rows = []
    for i in range(80):
        clicks, cpc = int(r.integers(1000, 9000)), float(r.uniform(0.5, 3.0))
        rows.append([f"AD-{i}", clicks, round(cpc, 2), round(clicks * cpc, 2)])
    clicks, spend = rows[30][1], rows[30][3]
    rows[30][2] = round(spend / clicks + 1, 2)
    out = asked(["Ad", "Clicks", "CPC", "Spend"], rows)
    assert "does not add up" in out[30]["reason"]
    assert not out[30].get("likely")
