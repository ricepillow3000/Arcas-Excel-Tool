"""AH-198 fix round 2: weak evidence. One cell past its column's weird limit, with nothing else on its row and no slip
that reads it back inside the column's usual limits (a decimal point or zeros, a minus sign, a unit typed for another:
Celsius for Fahrenheit, pounds for kilos...), is worth a check (Low), never "probably wrong": a trial's fever of 39.2 C
among 35.8-37.6 was Medium. A slip that reads back, a minus sign in a column that never goes below 0, or a value further out than 2 widths
of the weird limits, still votes.
On both benches no planted mistake and no clean row moved. Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Visit", "Pulse", "Systolic", "Diastolic", "Weight", "Temp"]


def sheet(n=200):
    return [[f"V{i}", 55 + i * 13 % 40, 105 + i * 17 % 45, 62 + i * 11 % 30, 52 + i * 29 % 60, round(36.2 + (i * 7 % 15) / 10, 1)]
            for i in range(n)]  # Temp 36.2 to 37.6


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def test_a_lone_breach_nothing_reads_back_is_worth_a_check():
    rows = sheet()
    rows[60][5] = 42.1
    out = scan(rows)
    assert out[60]["severity"] == "Low" and "Temp weird limit" in out[60]["reason"]


def test_a_breach_a_decimal_point_reads_back_is_still_probably_wrong():
    rows = sheet()
    rows[60][5] = 369.0
    assert scan(rows)[60]["severity"] == "Medium"


def test_a_breach_a_unit_reads_back_is_still_probably_wrong():
    rows = sheet()
    rows[60][5] = 98.4  # Fahrenheit typed in a Celsius column: 36.9 C
    assert scan(rows)[60]["severity"] == "Medium"


def test_a_minus_sign_in_a_column_that_never_goes_below_zero_is_still_probably_wrong():
    rows = [r[:4] + [450 + (i * 37 % 100) + (i * 13 % 50)] for i, r in enumerate(sheet())]  # rainfall 450 to 598 mm
    rows[60][4] = -260  # inside the weird limits' reach, and 260 is below the usual 270 too: only the sign tells
    r = APP.post("/scan", json={"columns": COLS[:4] + ["Rainfall"], "rows": rows, "strength": 5})
    assert r.get_json()["rows"][60]["severity"] == "Medium"


def test_a_breach_twice_the_width_of_the_weird_limits_from_their_middle_is_the_columns_own_extreme():
    rows = sheet()
    rows[60][5] = 51.3  # limits 33.3 to 40.5: 2 widths (14.4) from their middle (36.9)
    assert scan(rows)[60]["severity"] == "Low"


def test_a_breach_further_out_is_no_extreme_of_the_column_and_still_a_vote():
    rows = sheet()
    rows[60][5] = 51.5
    assert scan(rows)[60]["severity"] == "Medium"


def test_a_weight_in_pounds_among_kilos_is_read_back_and_still_probably_wrong():
    rows = sheet()
    rows[60][4] = 230.0  # past the weird limit of 220, inside its reach: 104 kg, inside the usual limits
    assert scan(rows)[60]["severity"] == "Medium"
