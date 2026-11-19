"""AH-208 (John, 2026-11-19: "the tool adapts to whatever the subject of the user's Excel file is"): on fresh synthetic
episodes of new subjects (payroll, inventory, grades, sensor logs, claims) the scan called valid cells wrong where an
honest pattern of the sheet explained them. Each rule here is true of any subject, and each test keeps a planted slip
flagged beside the honest pattern it leaves alone. Synthetic sheets only."""
from anomaly_hunter.engine.detectors import ecod_detector
from anomaly_hunter.engine.limits import suggest_limits_dict
from anomaly_hunter.engine.load import load_from_records, numbers
from anomaly_hunter.server import create_app

APP = create_app().test_client()


def scan(cols, rows, formulas=None):
    r = APP.post("/scan", json={"columns": cols, "rows": rows, "strength": 5, "formulas": formulas},
                 headers={"Origin": "https://127.0.0.1:5055"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


SURE = ("High", "Medium")

# -- a sum's sparse part left out (pipeline._left_out) --------------------------------------------------------------
# 90 rows and 5 number columns, under least squares' 100, and a text column between Gross Pay and Bonus, so only the
# pair rule Gross Pay = Regular Pay + Overtime Pay can judge them: it holds on 95% of rows
PAY = ["Employee", "Hours", "Regular Pay", "Overtime Pay", "Gross Pay", "Department", "Bonus"]


def payroll(n=90, bonus=(10, 40, 70), extra="Bonus"):
    rows = []
    for i in range(n):
        reg, ot = round(1000 + i * 37 % 500 + 0.25 * (i % 4), 2), round(50 + i * 13 % 200 + 0.5 * (i % 2), 2)
        b = (50.0 + 25 * bonus.index(i) if i in bonus else 0.0) if extra == "Bonus" else float(30 + i % 30)
        rows.append([f"E{i:03d}", 70 + i % 11, reg, ot, round(reg + ot + (b if extra == "Bonus" else 0), 2), "ABC"[i % 3], b])
    return rows


def test_a_total_that_misses_by_exactly_a_mostly_zero_columns_value_is_that_part_left_out():
    out = scan(PAY, payroll())
    for i in (10, 40, 70):  # these three add their Bonus
        assert "does not add up" not in out[i]["reason"] and "Gross Pay" not in out[i]["cells"], out[i]


def test_a_total_that_misses_by_a_dollar_more_than_that_part_is_still_a_slip():
    rows = payroll()
    rows[40][4] = round(rows[40][4] + 0.9, 2)  # the Bonus explains all but 90 cents
    rows[55][4] = round(rows[55][4] + 100, 2)  # and a row with no Bonus at all
    out = scan(PAY, rows)
    assert "Gross Pay" in out[40]["cells"] and out[40]["severity"] in SURE, out[40]
    assert "Gross Pay" in out[55]["cells"] and out[55]["severity"] in SURE, out[55]


def test_a_column_filled_on_most_rows_is_no_part_a_rule_could_leave_out():
    # a reference number on every row happens to equal the miss: no rule holding on 95% of rows can leave it out
    cols = PAY[:-1] + ["Ref"]
    rows = payroll(bonus=(), extra="Ref")
    rows[55][4] = round(rows[55][4] + rows[55][6], 2)
    out = scan(cols, rows)
    assert "Gross Pay" in out[55]["cells"] and out[55]["severity"] in SURE, out[55]


# -- a value that keeps its row's proportion (pipeline.in_step) -------------------------------------------------------
TAX = ["Employee", "Gross Pay", "Federal Tax", "Hours"]


def taxes(rates=(0.10, 0.15, 0.20, 0.25), n=240):
    rows = []
    for i in range(n):
        g = round(2400 + i * 53 % 1600 + 0.37 * (i % 3), 2)
        rows.append([f"E{i % 40:03d}", g, round(g * rates[i % 40 % len(rates)], 2), 80])
    return rows


def test_a_tax_that_keeps_its_share_of_a_big_gross_is_a_big_row_never_a_slip():
    rows = taxes()
    i = 123  # an executive's annual bonus period: Gross 10x, and Federal Tax the same 25% of it as every other period
    rows[i][1] = 52000.0
    rows[i][2] = round(52000.0 * [0.10, 0.15, 0.20, 0.25][i % 40 % 4], 2)
    out = scan(TAX, rows)
    assert out[i]["severity"] not in SURE, out[i]
    assert "keeps its usual share of Gross Pay" in out[i]["reason"], out[i]


def test_a_tax_typed_ten_times_over_on_an_ordinary_row_is_still_a_slip():
    rows = taxes()
    rows[77][2] = round(rows[77][2] * 10, 2)
    out = scan(TAX, rows)
    assert "Federal Tax" in out[77]["cells"] and out[77]["severity"] in SURE, out[77]


def test_a_share_that_varies_more_than_fivefold_corroborates_nothing():
    rates = (0.02, 0.06, 0.12, 0.25)  # 12.5x apart: a x10 slip could hide inside it
    rows = taxes(rates)
    i = 123
    rows[i][1] = 52000.0
    rows[i][2] = round(52000.0 * rates[i % 40 % 4], 2)
    out = scan(TAX, rows)
    assert "keeps its usual share" not in out[i]["reason"], out[i]
    assert out[i]["severity"] in SURE, out[i]


def test_a_value_worked_out_from_a_slip_is_never_its_witness():
    # Pay = Hours x Rate is a formula: an 800 typed for 80 makes Pay 10x too, in step, and is still the slip
    cols = ["Employee", "Hours", "Rate", "Pay"]
    rows = [[f"E{i:03d}", 80, 20 + i % 9, 80 * (20 + i % 9)] for i in range(200)]
    rows[64][1], rows[64][3] = 800, 800 * rows[64][2]
    formulas = [[None, None, None, "=RC[-2]*RC[-1]"] for _ in rows]
    out = scan(cols, rows, formulas)
    assert "Hours" in out[64]["cells"] and out[64]["severity"] in SURE, out[64]


def test_a_formula_that_never_reads_the_value_is_its_witness():
    # Gross Pay = Regular Pay + Bonus is a formula, but of other cells: it witnesses Federal Tax, which it never reads
    cols = ["Employee", "Regular Pay", "Bonus", "Gross Pay", "Federal Tax"]
    rates = (0.10, 0.15, 0.20, 0.25)
    rows = [[f"E{i % 40:03d}", round(2400 + i * 53 % 1600 + 0.37 * (i % 3), 2), 0] for i in range(240)]
    rows[123][2] = 40000
    for i, r in enumerate(rows):
        r += [round(r[1] + r[2], 2), round((r[1] + r[2]) * rates[i % 40 % 4], 2)]
    formulas = [[None, None, None, "=RC[-2]+RC[-1]", None] for _ in rows]
    out = scan(cols, rows, formulas)
    assert "Federal Tax keeps its usual share of Gross Pay" in out[123]["reason"], out[123]  # (the lone Bonus is its own matter)
    assert "Federal Tax weird limit" not in out[123]["reason"], out[123]


def test_a_witness_inside_its_own_limits_corroborates_nothing():
    # a weight typed in pounds (x2.2) keeps a ratio to its dose inside the dose-per-kilo band, but the dose is ordinary:
    # only one cell of the row is big, and one cell is what a slip changes
    cols = ["Patient", "Weight (kg)", "Dose (mg)"]
    per_kg = (1.0, 1.5, 2.0, 2.5, 3.0)
    rows = [[f"P{i:03d}", round(62 + i * 7 % 160 / 10, 1), round((62 + i * 7 % 160 / 10) * per_kg[i % 5], 1)] for i in range(200)]
    i = 74  # 3 mg a kilo; 165.3 "kg" is 75 kg in pounds, and the dose of 225 is the dose of 75 kg
    rows[i][1], rows[i][2] = 165.3, 225.0
    rows[120][1], rows[120][2] = 160.0, 480.0  # a real heavy patient at 3 mg a kilo: both cells big, in step
    out = scan(cols, rows)
    assert "Weight (kg)" in out[i]["cells"] and out[i]["severity"] in SURE, out[i]
    assert "keeps its usual share" in out[120]["reason"], out[120]


# -- a unit read back lands among the column's ordinary values (detectors.unexplained) -------------------------------
def test_a_short_period_among_full_ones_is_worth_a_check_never_a_unit_slip():
    # 40 hours among 64-80: no decimal point or sign reads it back, and 40 x 2.20462 = 88.2 "pounds for kilos" lands
    # past every ordinary period (64-80), so it was never a reading in another unit
    cols = ["Employee", "Department", "Hours", "Rate", "Overtime"]
    rows = [[f"E{i:03d}", "ABC"[i % 3], [80, 80, 80, 80, 80, 76, 72, 64][i % 8], 17 + i * 29 % 30, [0, 0, 0, 2, 4, 6][i % 6]]
            for i in range(240)]
    rows[100][2] = 40
    out = scan(cols, rows)
    assert out[100]["severity"] == "Low", out[100]


def test_a_unit_that_reads_back_near_the_columns_edge_is_still_a_slip():
    # a height typed in inches among 170-190 cm: 72 in is 182.9 cm, among the column's ordinary values (its 10th to
    # 90th percentile, 172-188) though far from their middle
    cols = ["Person", "Height (cm)", "Weight (kg)", "Pulse"]
    rows = [[f"P{i:03d}", round(170 + (i * 37 % 200) / 10, 1), round(60 + (i * 13 % 300) / 10, 1), 55 + i * 17 % 40] for i in range(200)]
    rows[60][1] = 72.0
    out = scan(cols, rows)
    assert out[60]["severity"] in SURE, out[60]


# -- a group's layout with one cell filled against it (pipeline._all_blank) -------------------------------------------
BANK = ["Txn", "Status", "Book Amount", "Bank Date", "Bank Amount"]


def bank(outstanding=51, cleared=400):
    rows = [[f"T{i:04d}", "Cleared", -100.0 - i, f"2026-09-{1 + i % 28:02d}", -100.0 - i] for i in range(cleared)]
    rows += [[f"T{cleared + i:04d}", "Outstanding", -200.0 - i, None, None] for i in range(outstanding)]
    return rows


def test_a_group_blank_on_all_but_one_of_its_rows_is_the_layout():
    rows = bank()
    rows[420][3], rows[420][4] = "2026-09-30", rows[420][2]  # one outstanding cheque that did clear: that row's slip
    out = scan(BANK, rows)
    blanks = [i for i in range(400, 451) if i != 420 and out[i]["severity"] in SURE]
    assert not blanks, out[blanks[0]]
    # ...and a layout says nothing, not even AH-210's note of a stage the label allows (a label merely often blank)
    assert not [i for i in range(400, 451) if "is blank on" in out[i]["reason"]]


def test_a_small_group_blank_on_all_but_one_row_is_no_layout_to_tell():
    rows = bank(outstanding=12)
    rows[405][3], rows[405][4] = "2026-09-30", rows[405][2]
    out = scan(BANK, rows)
    assert all(out[i]["severity"] in SURE and "Bank Date" in out[i]["cells"] for i in range(400, 412) if i != 405), out[400]


def test_a_blank_in_the_group_that_fills_the_column_is_still_a_slip():
    rows = bank()
    rows[200][3] = None
    out = scan(BANK, rows)
    assert "Bank Date" in out[200]["cells"] and out[200]["severity"] in SURE, out[200]


# -- the cell an unusual combination names (detectors.ecod_detector) --------------------------------------------------
def storm(pressure=101.2):
    # two stations (a valley near 1012 hPa, a ridge near 850), dry but for a storm: rain's spread is a fraction of a
    # millimetre, so the storm's honest 9.8 mm is 40 spreads out, further than a pressure typed in kPa
    cols = ["Hour", "Temperature", "Humidity", "Pressure", "Wind", "Rainfall"]
    rows = [[f"H{i:03d}", round(15 + 8 * ((i % 24) / 24), 1), 50 + i * 7 % 30, round(850 + 162 * (i % 2) + (i * 13 % 40) / 10, 1),
             round(1 + i * 11 % 50 / 10, 1), round(3 + i % 9, 1) if 140 <= i < 156 else 0.0 if i % 25 else round(0.2 + i % 13 / 10, 1)]
            for i in range(300)]
    rows[151][3] = pressure  # the valley's pressure, in the storm
    df, types, _ = load_from_records(cols, rows)
    return ecod_detector(df, types, 0.5, suggest_limits_dict(df, numbers(types)))


def test_an_unusual_combination_names_the_cell_past_its_limits_never_a_sparse_columns_reading():
    d = storm(101.2)  # written in kPa
    assert d["votes"][151] and d["reasons"][151][0].cols == ("Pressure",), d["reasons"][151]


def test_an_unusual_combination_with_no_cell_past_its_limits_names_the_cell_most_off():
    d = storm(1012.4)  # an ordinary pressure: the storm's rain is what is unusual
    assert d["votes"][151] and d["reasons"][151][0].cols == ("Rainfall",), d["reasons"][151]


# -- one cell filled where its group leaves the column empty (pipeline.group_gaps) -----------------------------------
CLAIMS = ["Claim", "Status", "Line", "Close Date", "Deductible", "Claimed"]


def claims(open_rows=25, closed_blank=3, n=100):  # 72 of 75 closed claims (96%) carry their close date
    rows = []
    for i in range(n):
        status = "Open" if i % 4 == 0 and i // 4 < open_rows else "Closed"
        line = "Health" if i % 3 == 0 else "Auto"
        rows.append([f"C{i:04d}", status, line, None if status == "Open" else f"2026-0{1 + i % 9}-1{i % 10}",
                     0 if line == "Health" else [500, 1000][i % 2], round(800 + i * 37 % 900 + 0.5, 2)])
    closed = [i for i, r in enumerate(rows) if r[1] == "Closed"]
    for i in closed[5:5 + closed_blank]:  # a few closed claims whose close date was never typed
        rows[i][3] = None
    return rows


def test_a_date_filled_on_one_open_claim_among_open_claims_without_one_is_flagged():
    rows = claims()
    rows[40][3] = "2026-05-02"  # Open (40 % 4 == 0), every other open claim has no close date
    rows[42][4] = 1000  # a deductible on one Health claim (42 % 3 == 0), every other Health claim 0
    out = scan(CLAIMS, rows)
    assert "Close Date" in out[40]["cells"] and out[40]["severity"] in SURE, out[40]
    assert "filled where Status Open leaves it blank on 24 of 25 rows" in out[40]["reason"], out[40]
    assert "Deductible" in out[42]["cells"] and out[42]["severity"] in SURE, out[42]


def test_a_column_no_label_decides_says_nothing_of_its_few_filled_cells():
    # a few closed claims miss their close date (10%): the label no longer decides the column, and an open claim's date
    # is one more of the sheet's own mix
    rows = claims(closed_blank=8)
    rows[40][3] = "2026-05-02"
    out = scan(CLAIMS, rows)
    assert "filled where" not in out[40]["reason"], out[40]


def test_a_group_of_nineteen_rows_is_too_small_to_have_a_layout():
    rows = claims(open_rows=19)
    rows[40][3] = "2026-05-02"
    out = scan(CLAIMS, rows)
    assert "filled where" not in out[40]["reason"], out[40]


def test_two_filled_cells_in_a_group_of_twenty_five_are_how_the_group_is():
    rows = claims()
    rows[40][3], rows[44][3] = "2026-05-02", "2026-05-03"
    out = scan(CLAIMS, rows)
    assert "filled where" not in out[40]["reason"] and "filled where" not in out[44]["reason"], out[40]


def test_a_cell_is_never_judged_by_a_protected_group():
    cols = ["Patient", "Sex", "Pregnancy Weeks", "Weight"]
    rows = [[f"P{i:03d}", "F" if i % 2 else "M", 10 + i % 30 if i % 2 else None, 60 + i % 30] for i in range(120)]
    rows[40][2] = 12  # a man (40 is even) with a pregnancy week: never judged by his sex
    out = scan(cols, rows)
    assert "filled where" not in out[40]["reason"], out[40]


def sparse_tax(rows_with_tax):
    # Federal Tax withheld on only some rows (the others 0): the band is read from those rows alone
    rows = taxes()
    at = [i for i in range(len(rows)) if i % 12 == 3][:rows_with_tax]
    for i, r in enumerate(rows):
        if i not in at:
            r[2] = 0
    i = at[-1]
    rows[i][1] = 52000.0
    rows[i][2] = round(52000.0 * [0.10, 0.15, 0.20, 0.25][i % 40 % 4], 2)
    return scan(TAX, rows)[i]


def test_a_share_read_from_twenty_rows_corroborates():
    assert "keeps its usual share" in sparse_tax(20)["reason"]


def test_a_share_read_from_nineteen_rows_corroborates_nothing():
    assert "keeps its usual share" not in sparse_tax(19)["reason"]


# AH-210: one slip changes one cell. A row that fills two or more columns its label leaves empty has the wrong label (a
# house listed as Land), and the label is named alone: its bathrooms, living area and year built were each coloured
LISTING = ["Listing", "Type", "Bedrooms", "Living Area", "Year Built", "Price"]


def listings(n=120):
    rows = []
    for i in range(n):
        land = i % 4 == 0
        rows.append([f"L{i:04d}", "Land" if land else ["House", "Condo"][i % 2], None if land else 2 + i % 4,
                     None if land else 900 + i * 37 % 1500, None if land else 1950 + i % 60, 150000 + i * 7919 % 400000])
    return rows


def test_a_row_that_fills_two_columns_its_label_leaves_empty_names_the_label_alone():
    rows = listings()
    rows[40][3], rows[40][4] = 1730, 2005  # a house typed as Land: its area and year are filled
    out = scan(LISTING, rows)
    assert out[40]["cells"] == ["Type"] and out[40]["severity"] in SURE, out[40]
    assert "Type Land does not fit this row, which fills Living Area and Year Built" in out[40]["reason"], out[40]


def test_a_row_that_fills_one_column_its_label_leaves_empty_names_that_cell():
    rows = listings()
    rows[40][4] = 2005  # a year built typed on one Land listing: the year is the slip
    out = scan(LISTING, rows)
    assert out[40]["cells"] == ["Year Built"] and out[40]["severity"] in SURE, out[40]


# AH-211: the same slip seen from both sides. A salaried employee typed Hourly fills Annual Salary, which Hourly leaves
# empty, and leaves Hourly Rate blank, which Hourly fills: the row looks like Salaried in both, so Pay Type is named
# alone (Annual Salary was coloured, valid, and the Pay Type slip missed, adversarial episode 17)
PAY_TYPES = ["Employee", "Pay Type", "Hourly Rate", "Annual Salary", "Hours", "Shift"]


def pay_types(n=120):
    rows = []
    for i in range(n):
        salaried = i % 3 == 0
        rows.append([f"E{i:04d}", "Salaried" if salaried else "Hourly", None if salaried else 15 + i % 20,
                     1000 * (40 + i % 50) if salaried else None, 80, ["Day", "Night"][i % 2]])
    return rows


def test_a_row_that_fills_a_column_its_label_leaves_empty_and_leaves_blank_one_it_fills_names_the_label_alone():
    rows = pay_types()
    rows[40][2], rows[40][3] = None, 75400  # an Hourly row that looks Salaried: a salary and no hourly rate
    out = scan(PAY_TYPES, rows)
    assert out[40]["cells"] == ["Pay Type"] and out[40]["severity"] in SURE, out[40]
    assert "Pay Type Hourly does not fit this row, which fills Annual Salary and leaves Hourly Rate blank" in out[40]["reason"], out[40]


def test_a_row_that_fills_a_column_its_label_leaves_empty_and_keeps_the_rest_names_that_cell():
    rows = pay_types()
    rows[40][3] = 75400  # an hourly row with its rate kept and a salary typed too: the salary is the slip
    out = scan(PAY_TYPES, rows)
    assert out[40]["cells"] == ["Annual Salary"] and out[40]["severity"] in SURE, out[40]


def test_a_blank_no_other_label_leaves_empty_never_names_the_label():
    rows = pay_types()
    rows[40][3], rows[40][5] = 75400, None  # a salary typed, and a Shift deleted: every label fills Shift
    out = scan(PAY_TYPES, rows)
    assert "Pay Type" not in out[40]["cells"] and "Annual Salary" in out[40]["cells"], out[40]


def test_a_row_that_looks_like_two_different_labels_never_names_its_own():
    # Hourly fills Rate and Hours, Salaried Salary and Hours, Contractor Fee alone. An Hourly row with a salary (as
    # Salaried) and no hours (as Contractor) looks like no one label: its salary is named, never its Pay Type
    cols = ["Employee", "Pay Type", "Hourly Rate", "Annual Salary", "Fee", "Hours"]
    rows = []
    for i in range(150):
        kind = ["Hourly", "Salaried", "Contractor"][i % 3]
        rows.append([f"E{i:04d}", kind, 15 + i % 20 if kind == "Hourly" else None,
                     1000 * (40 + i % 50) if kind == "Salaried" else None, 500 + i % 90 if kind == "Contractor" else None,
                     None if kind == "Contractor" else 80])
    rows[42][3], rows[42][5] = 75400, None  # an Hourly row (42 % 3 == 0), its rate kept
    out = scan(cols, rows)
    assert "Pay Type" not in out[42]["cells"] and "Annual Salary" in out[42]["cells"], out[42]
