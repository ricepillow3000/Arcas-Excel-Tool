"""AH-210: on fresh episodes of new subjects (a fleet's fuel log, a library's loans, support tickets) the blanks check
called 60 valid blank cells wrong where the sheet's own course explained them: a formula's own "", each vehicle's first
fill (no distance since a previous one), loans not returned yet, open tickets not yet given an agent. Each rule is true
of any subject, and each test keeps a deleted value flagged beside the blanks it leaves alone. Synthetic sheets only."""
import datetime

from anomaly_hunter.server import create_app

APP = create_app().test_client()


def scan(cols, rows, formulas=None):
    r = APP.post("/scan", json={"columns": cols, "rows": rows, "strength": 5, "formulas": formulas},
                 headers={"Origin": "https://127.0.0.1:5055"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def blank_slips(out, col):
    return [i for i, r in enumerate(out) if f"Blank cell in column {col}" in r["reason"] and r["severity"] in ("High", "Medium")]


# -- a formula's own blank ------------------------------------------------------------------------------------------
FUEL = ["Fill", "Vehicle", "Distance", "Litres", "L/100 km"]
PER_100 = '=IF(RC[-2]="","",ROUND(RC[-1]/RC[-2]*100,1))'


def fuel(vehicles=10, fills=12, first_blank=None):
    """fills per vehicle, interleaved; Distance blank on the first fill of `first_blank` vehicles (all by default)."""
    first_blank = vehicles if first_blank is None else first_blank
    rows, formulas = [], []
    for k in range(fills):
        for v in range(vehicles):
            i = len(rows)
            gone = k == 0 and v < first_blank
            dist = None if gone else 300 + (i * 37) % 400
            litres = round(20 + (i * 13) % 30 + 0.5, 1)
            rows.append([f"F{i:04d}", f"VH-{v:03d}", dist, litres, None if gone else round(litres / dist * 100, 1)])
            formulas.append([None, None, None, None, PER_100])
    return rows, formulas


def test_a_blank_a_formula_writes_is_never_a_value_left_out():
    rows, formulas = fuel()
    for i in (50, 80):
        rows[i][2] = rows[i][4] = None  # two distances deleted: their formula's "" follows
    out = scan(FUEL, rows, formulas)
    assert blank_slips(out, "Distance") == [50, 80] and blank_slips(out, "L/100 km") == [], [out[i]["reason"] for i in (0, 50)]


def test_a_blank_typed_over_a_formula_is_still_a_value_left_out():
    rows, formulas = fuel()
    rows[60][4], formulas[60][4] = None, None  # the formula itself deleted, its distance still there
    assert blank_slips(scan(FUEL, rows, formulas), "L/100 km") == [60]


# -- each entity's first row ----------------------------------------------------------------------------------------
def test_a_column_blank_on_each_vehicles_first_fill_is_the_layout_and_a_later_blank_a_slip():
    rows, formulas = fuel()
    rows[70][2] = rows[70][4] = None  # a later fill's distance deleted
    assert blank_slips(scan(FUEL, rows, formulas), "Distance") == [70]


def test_five_entities_first_rows_are_enough_and_four_are_not():
    rows, formulas = fuel(vehicles=5, fills=30)
    assert blank_slips(scan(FUEL, rows, formulas), "Distance") == []
    rows, formulas = fuel(vehicles=4, fills=40)
    assert blank_slips(scan(FUEL, rows, formulas), "Distance") == [0, 1, 2, 3]


def test_eight_of_ten_first_rows_blank_are_the_layout_and_seven_are_not():
    rows, formulas = fuel(first_blank=8)
    assert blank_slips(scan(FUEL, rows, formulas), "Distance") == []
    rows, formulas = fuel(first_blank=7)
    assert blank_slips(scan(FUEL, rows, formulas), "Distance") == list(range(7))


def test_values_deleted_at_the_top_of_a_sheet_are_still_slips_though_they_hold_every_first_row():
    rows, formulas = fuel(fills=20)
    for i in range(10, 30):  # 20 more distances deleted right below the first fills: most blanks are no first row
        rows[i][2] = rows[i][4] = None
    assert blank_slips(scan(FUEL, rows, formulas), "Distance") == list(range(30))


# -- an end not reached yet -----------------------------------------------------------------------------------------
LOANS = ["Loan", "Branch", "Checkout", "Return", "Renewals"]
DAY = datetime.date(2025, 9, 1)


def loans(n=300, out_at=(), breaks=0):
    """Loans in checkout order, each returned 2-30 days later; `out_at` rows not returned; `breaks` rows returned the day
    before their checkout (an order on all but those)."""
    rows = []
    for i in range(n):
        start = DAY + datetime.timedelta(days=i)
        end = start + datetime.timedelta(days=-1 if i % 37 == 5 and i // 37 < breaks else 2 + i * 7 % 29)
        rows.append([f"L{i:04d}", ["Central", "East", "West"][i % 3], start.isoformat(),
                     None if i in out_at else end.isoformat(), i % 3])
    return rows


LATEST = tuple(range(280, 300)) + (40, 150)  # the last 20 loans still out, and two long overdue


def test_loans_not_returned_yet_are_one_note_never_a_slip_each():
    out = scan(LOANS, loans(out_at=LATEST))
    assert blank_slips(out, "Return") == []
    assert out[40]["severity"] == "Low" and "Return is blank in 22 of 300 rows" in out[40]["reason"], out[40]
    assert "an end not reached yet" in out[40]["reason"]


def test_five_open_ends_are_enough_and_four_are_not():
    assert blank_slips(scan(LOANS, loans(out_at=range(295, 300))), "Return") == []
    assert blank_slips(scan(LOANS, loans(out_at=range(296, 300))), "Return") == [296, 297, 298, 299]


def test_blanks_spread_through_the_loans_are_still_each_a_slip():
    gone = tuple(range(10, 300, 30))
    assert blank_slips(scan(LOANS, loans(out_at=gone)), "Return") == list(gone)


def test_blanks_short_of_the_latest_quarter_are_still_each_a_slip():
    gone = tuple(range(180, 220, 4))  # around the 60th to 70th percentile of the checkouts: no end not reached
    assert blank_slips(scan(LOANS, loans(out_at=gone)), "Return") == list(gone)


def test_an_order_held_on_98_percent_of_rows_is_enough_and_less_is_not():
    assert blank_slips(scan(LOANS, loans(out_at=LATEST, breaks=5)), "Return") == []  # 273 of 278: 98.2%
    assert blank_slips(scan(LOANS, loans(out_at=LATEST, breaks=6)), "Return") == sorted(LATEST)  # 272 of 278: 97.8%


# -- a stage one label allows ----------------------------------------------------------------------------------------
TICKETS = ["Ticket", "Status", "Agent", "Minutes"]


def tickets(open_rows=30, open_blank=8, closed_blank=(), n=300):
    rows = []
    for i in range(n):
        status = "Open" if i % 10 == 0 and i // 10 < open_rows else "Closed"
        rows.append([f"T{i:04d}", status, ["Ana", "Ben", "Cai", "Dee"][i % 4], 5 + i * 7 % 40])
    opened = [i for i, r in enumerate(rows) if r[1] == "Open"]
    for i in opened[:open_blank] + list(closed_blank):
        rows[i][2] = None
    return rows, opened[:open_blank]


def test_open_tickets_not_given_an_agent_are_one_note_and_a_closed_one_with_none_a_slip():
    rows, gone = tickets(closed_blank=(55,))
    out = scan(TICKETS, rows)
    assert blank_slips(out, "Agent") == [55]
    assert out[gone[0]]["severity"] == "Low" and "Agent is blank on 8 of the 30 rows of Status Open" in out[gone[0]]["reason"]


def test_a_label_leaving_a_fifth_of_its_rows_blank_is_a_stage_and_less_is_not():
    rows, _ = tickets(open_blank=6)  # 6 of 30: 20%
    assert blank_slips(scan(TICKETS, rows), "Agent") == []
    rows, gone = tickets(open_blank=5)  # 5 of 30
    assert blank_slips(scan(TICKETS, rows), "Agent") == gone


def test_a_label_of_twenty_rows_can_have_a_stage_and_one_of_nineteen_cannot():
    rows, _ = tickets(open_rows=20, open_blank=5)
    assert blank_slips(scan(TICKETS, rows), "Agent") == []
    rows, gone = tickets(open_rows=19, open_blank=5)
    assert blank_slips(scan(TICKETS, rows), "Agent") == gone
    rows, gone = tickets(open_rows=20, open_blank=4)  # a fifth of 20, but under 5 blanks
    assert blank_slips(scan(TICKETS, rows), "Agent") == gone


def test_a_stage_needs_the_other_rows_filled_on_all_but_one_percent():
    rows, _ = tickets(closed_blank=(55, 101, 207))  # 3 of 270: 1.1%
    assert len(blank_slips(scan(TICKETS, rows), "Agent")) == 11
    rows, _ = tickets(closed_blank=(55, 101))  # 2 of 270: 0.7%
    assert blank_slips(scan(TICKETS, rows), "Agent") == [55, 101]
