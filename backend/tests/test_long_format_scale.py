"""AH-198: a long sheet keeps many quantities in one column, a text column saying which (a lab's Result by Test). Judged
as a whole, potassium 44 (for 4.4) sat among sodium near 140 and said nothing. Where the text column sets the scale,
each label's 20+ values get their own limits, and a value past them votes only with a slip of zeros or the decimal
point behind it: a real critical potassium of 9.5 has none. Never a fix. Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Subject", "Test", "Result"]


def lab(potassium=30):
    rows = []
    for k in range(30):
        rows.append([f"S{k:02}", "Sodium", 136 + k * 7 % 10])
        rows.append([f"S{k:02}", "CRP", round(1.5 + (k * 13 % 17) * 2.3, 1)])
    rows += [[f"S{k:02}", "Potassium", round(3.6 + (k * 7 % 15) / 10, 1)] for k in range(potassium)]
    return rows


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def flagged(out):
    return {i: (r["severity"], r["cells"]) for i, r in enumerate(out) if r["severity"] not in (None, "Noted")}


def test_a_decimal_point_lost_in_one_test_of_a_long_sheet_is_found_among_its_own_test():
    rows = lab()
    rows[70][2] = 44.0  # potassium 4.4
    out = scan(rows)
    assert flagged(out) == {70: ("Medium", ["Result"])}
    assert out[70]["reason"] == ("Result 44 is far outside the other Result values for Test Potassium (weird limit 7.9), "
                                 "10 times a usual one: a slip of zeros or the decimal point")
    assert not out[70]["likely"] and not out[70]["maybe"], "a gram for a kilo looks like 100 or 1000 the same: never a fix"


def test_a_real_critical_value_with_no_slip_behind_it_is_left_alone():
    rows = lab()
    rows[70][2] = 9.5  # past its limits, but 0.95 or 95 is no potassium either
    assert flagged(scan(rows)) == {}


def test_twenty_values_of_a_label_are_enough_and_nineteen_are_not():
    rows = lab(20)
    rows[70][2] = 44.0
    assert 70 in flagged(scan(rows))
    rows = lab(19)
    rows[70][2] = 44.0
    assert flagged(scan(rows)) == {}
