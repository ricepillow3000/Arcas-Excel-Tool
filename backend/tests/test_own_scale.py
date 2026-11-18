"""AH-198 fix round 2: an entity's own scale. In a sheet of records split over lines (a subject's visits, a county's
years), a number steady inside each record (its values within 1.2x of each other in 90% of the records) holds one
entity's own size: a value off its record's others, which agree, and read back among them by a slip of the decimal
point or a minus sign, is that slip, though the column as a whole hides it. A unit (pounds for kilos) is never read
back: a county's honest populations of other years met one 1.6 or 2.2 times apart by chance. Synthetic sheets only."""
import datetime

from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Subject", "Visit", "VisitDate", "Weight"]


def visits(subjects=20, each=5):
    rows = []
    for s in range(subjects):
        start = datetime.date(2026, 1, 5) + datetime.timedelta(days=3 * s)
        rows += [[f"S-{100 + s}", f"Week {2 * v}", (start + datetime.timedelta(days=14 * v)).isoformat(),
                  round(45 + 4.1 * s + 0.2 * (v % 3), 1)] for v in range(each)]
    return rows


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def scaled(out):
    return {i for i, r in enumerate(out) if "times the other Weight values of Subject" in r["reason"] and r["severity"] == "Medium"}


def test_a_decimal_point_slipped_in_one_subjects_weight_is_found_among_its_own_visits():
    rows = visits()
    rows[22][3] = round(rows[22][3] / 10, 2)  # 6.17 for 61.7: inside the column's own range of 45 to 123
    out = scan(rows)
    assert scaled(out) == {22}
    assert out[22]["cells"] == ["Weight"] and not out[22].get("likely")


def test_pounds_among_a_subjects_kilos_are_never_read_back():
    rows = visits()
    rows[22][3] = round(rows[22][3] * 2.20462, 1)
    assert scaled(scan(rows)) == set()


def test_nineteen_subjects_are_too_few_to_know_their_weights_are_steady():
    rows = visits(subjects=19)
    rows[22][3] = round(rows[22][3] / 10, 2)
    assert scaled(scan(rows)) == set()


def test_records_that_vary_more_than_a_fifth_hold_no_size_of_their_own():
    rows = visits()
    for s in range(2):  # 2 subjects of 20 whose weight moves 25%, and the slip's: 85% of the records are steady
        rows[5 * s + 4][3] = round(rows[5 * s][3] * 1.25, 1)
    rows[22][3] = round(rows[22][3] / 10, 2)
    assert scaled(scan(rows)) == set()


def test_one_subject_that_varies_more_than_a_fifth_and_the_slips_leave_ninety_percent_steady():
    rows = visits()
    for s in range(1):
        rows[5 * s + 4][3] = round(rows[5 * s][3] * 1.25, 1)
    rows[22][3] = round(rows[22][3] / 10, 2)
    assert scaled(scan(rows)) == {22}


def test_three_subjects_that_vary_just_under_a_fifth_are_still_steady():
    rows = visits()
    for s in range(3):
        rows[5 * s + 4][3] = round(rows[5 * s][3] * 1.19, 1)
    rows[22][3] = round(rows[22][3] / 10, 2)
    assert scaled(scan(rows)) == {22}


def test_a_value_read_back_within_five_percent_of_its_subjects_others_is_a_slip_and_eight_percent_is_not():
    rows = visits()
    top = max(r[3] for k, r in enumerate(rows[20:25]) if k != 2)
    rows[22][3] = round(top * 1.04 / 10, 3)
    assert scaled(scan(rows)) == {22}
    rows[22][3] = round(top * 1.08 / 10, 3)
    assert scaled(scan(rows)) == set()
