"""AH-198: a typo changes one cell. A journal's storno (-18,400 debit, -18,400 credit) and a real 486,500 purchase with
its 486,500 payable were each "weird" and "likely 4865": the same number typed in another column a few rows away is
the entry's other side, a real record twice over. And three payrolls near 55,000 past a limit of 30,000 are the
column's own amount, not three slips: a breach with no typo behind it and 2+ others as far out, near it, gets no vote.
Synthetic sheets only."""
import numpy as np
from anomaly_hunter.server import create_app

APP = create_app().test_client()


def scan(columns, rows):
    r = APP.post("/scan", json={"columns": columns, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def ledger(n=120):
    """Lines of a ledger: a debit line, then its credit line, amounts 1,040 to 8,960."""
    rows = []
    for k in range(n // 2):
        amount = 1000 + (k * 37 % 50) * 160 + 40
        rows += [[f"L{2 * k:03}", amount, None], [f"L{2 * k + 1:03}", None, amount]]
    return ["Line", "Debit", "Credit"], rows


def sure(out, i, col):
    return out[i]["severity"] in ("Medium", "High") and col in out[i]["cells"]


def test_a_value_mirrored_by_the_other_column_a_few_rows_away_is_no_slip():
    cols, rows = ledger()
    rows[40][1], rows[43][2] = 486500, 486500  # the purchase and its payable, three rows apart
    rows[60][1], rows[61][2] = -18400, -18400  # a storno: a negative debit and its negative credit
    out = scan(cols, rows)
    for i, col in ((40, "Debit"), (43, "Credit"), (60, "Debit"), (61, "Credit")):
        assert not sure(out, i, col), out[i]
        assert not out[i].get("likely"), "never 'likely 4865': the other column proves the number"


def test_a_twin_four_rows_away_or_one_of_two_significant_digits_proves_nothing():
    cols, rows = ledger()
    rows[40][1], rows[44][2] = 486500, 486500  # four rows apart: past the entry's siblings
    rows[80][1], rows[81][2] = 48000, 48000  # 48,000: two significant digits, a round number met by chance
    out = scan(cols, rows)
    assert sure(out, 40, "Debit") and sure(out, 44, "Credit")
    assert sure(out, 80, "Debit") and sure(out, 81, "Credit")


def test_a_twin_of_three_significant_digits_three_rows_away_is_the_limit():
    cols, rows = ledger()
    rows[40][1], rows[43][2] = 48400, 48400
    out = scan(cols, rows)
    assert not sure(out, 40, "Debit") and not sure(out, 43, "Credit")


def test_an_ordinary_value_in_the_other_column_is_no_twin():
    cols, rows = ledger()
    rows[40][1] = 4840 * 100  # a x100 slip; 4,840 is an ordinary credit nearby, 484,000 is not anywhere
    rows[41][2] = 4840
    out = scan(cols, rows)
    assert sure(out, 40, "Debit")


def test_a_twin_that_is_ordinary_in_its_own_column_was_met_by_chance():
    rows = [[f"B{k:03}", 1 + k % 4, 100 + k * 37 % 300] for k in range(120)]
    rows[40][1], rows[41][2] = 253, 253  # 253 adults in one booking; a price of 253 on the next is ordinary there
    out = scan(["Booking", "Adults", "Price"], rows)
    assert sure(out, 40, "Adults")


def amounts(big, n=99):
    """Amounts 3,040 to 6,960 (median 5,000) and the big ones."""
    rows = [[f"P{k:03}", 3040 + 40 * k] for k in range(n)] + [[f"P{n + k:03}", v] for k, v in enumerate(big)]
    return ["Payee", "Amount"], rows


def near(a, share, others=2):
    med = float(np.median([3040 + 40 * k for k in range(99)] + [a] * (1 + others)))
    return [a] + [a + s * share * (a - med) for s in (1, -1)[:others]]


def test_a_value_past_its_limit_with_two_others_near_it_is_the_columns_own_amount():
    out = scan(*amounts(near(55000, 0.099)))
    assert not sure(out, 99, "Amount"), out[99]


def test_one_near_value_is_not_a_crowd_and_two_just_too_far_are_not_either():
    out = scan(*amounts(near(55000, 0.099, others=1)))
    assert sure(out, 99, "Amount")
    out = scan(*amounts(near(55000, 0.101)))
    assert sure(out, 99, "Amount")


def test_a_cluster_far_off_a_column_that_barely_varies_is_never_a_crowd():
    rows = [[f"T{k:03}", round(37.70 + (k * 7 % 11) / 100, 4)] for k in range(99)]
    rows += [["T099", 47.27], ["T100", 47.25], ["T101", 47.28]]  # 14 street trees at one bad default latitude
    out = scan(["Tree", "Latitude"], rows)
    assert all(sure(out, i, "Latitude") for i in (99, 100, 101))
