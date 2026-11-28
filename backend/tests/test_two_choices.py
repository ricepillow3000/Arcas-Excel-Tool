"""AH-238: a row that breaks Qty x Unit Price = Total where exactly two cells could each be the slip carries both
answers as `choices`, worked out from the row's own arithmetic, for the user to pick from. Arcas never picks.
Made-up shop sheet."""
import numpy as np

from test_only_one_cell_fits import asked, shop


def test_a_row_where_two_cells_could_each_be_the_slip_carries_both_answers():
    # Qty 10 for 1: Qty 1 or Total 79.9 each make it add up
    _, out = shop({12: (10, 7.99, 7.99)})
    assert out[12]["choices"] == {"Qty": 1, "Total": 79.9}
    assert not out[12]["likely"]


def test_a_row_with_one_answer_gets_its_fix_and_no_choices():
    _, out = shop({30: (7, 2.99, 30.93)})
    assert out[30]["likely"] == {"Total": 20.93}
    assert not out[30]["choices"]


def test_a_row_that_adds_up_carries_no_choices():
    _, out = shop({})
    assert not any(o.get("choices") for o in out)


def test_a_cell_that_only_fits_within_the_sheets_rounding_is_no_choice_to_offer():
    # prices to the cent, small whole quantities, totals from the unrounded price: the sheet only adds up within that
    # rounding. A Total typed 10 too high has one exact answer (Qty x price) and a second only within the rounding (the
    # price 10 higher / Qty): no value of it can be written as the row's own arithmetic, so nothing is offered
    r = np.random.default_rng(3)
    rows = []
    for i in range(80):
        q, p = int(r.integers(1, 13)), float(r.uniform(0.5, 30))
        rows.append([f"SO-{i}", q, round(p, 2), round(q * p, 2)])
    rows[30][3] = round(rows[30][3] + 10, 2)
    out = asked(["Order", "Qty", "Unit Price", "Total"], rows)
    assert "does not add up" in out[30]["reason"]
    assert not out[30]["choices"] and not out[30]["likely"]
