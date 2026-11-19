"""AH-198: two date columns where one is on or after the other on every row but one (a sample resulted on or after it
was drawn, a parcel delivered on or after it shipped): the row where it comes before is a contradiction. A shipment
delivered 3 days before it shipped was found only through its Transit Days formula, and a lab result dated 4 days
before its sample was not found at all. Which date is wrong is unknown, unless one column is the sheet's own order and
the row keeps it. Synthetic sheets only."""
import datetime

from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Shipment", "Shipped", "Delivered", "Kg"]
DAY = datetime.date(2026, 1, 5)


def sheet(n=50, wrong=(30,), shuffled=False):
    rows = []
    for k in range(n):
        shipped = DAY + datetime.timedelta(days=k // 2)
        delivered = shipped + datetime.timedelta(days=1 + k % 9)
        rows.append([f"S{k:03}", shipped.isoformat(), delivered.isoformat(), 100 + k * 7 % 40])
    for k in wrong:  # delivered three days before it shipped
        rows[k][2] = (datetime.date.fromisoformat(rows[k][1]) - datetime.timedelta(days=3)).isoformat()
    if shuffled:
        rows = rows[::-1]  # newest first: no column runs up the sheet
    return rows


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def said(out):
    return {i: (r["severity"], r["cells"]) for i, r in enumerate(out) if "is before" in r["reason"]}


def test_a_delivery_before_its_shipment_names_the_delivery_when_the_sheet_runs_in_shipping_order():
    out = scan(sheet())
    assert said(out) == {30: ("Medium", ["Delivered"])}
    assert out[30]["reason"] == "Delivered 2026-01-17 is before Shipped 2026-01-20, where Delivered is on or after Shipped on 49 of 50 rows"


def test_when_neither_date_is_the_sheets_order_both_are_named():
    rows = sheet(shuffled=True)
    i = next(k for k, r in enumerate(rows) if r[2] < r[1])
    assert said(scan(rows)) == {i: ("Medium", ["Shipped", "Delivered"])}


def test_fifty_rows_are_enough_and_forty_nine_are_not():
    assert said(scan(sheet(49))) == {}


def test_two_rows_against_the_order_are_how_the_dates_are_never_a_slip():
    assert said(scan(sheet(wrong=(20, 30)))) == {}


# AH-210: what the tuning episodes found. A date already far outside its column (a year typed 2125) is that date's slip:
# it was counted as a second row against the order, so a real "returned before checked out" two rows on went unsaid
def test_a_date_far_outside_its_column_never_hides_another_row_against_the_order():
    rows = sheet(51)
    rows[10][1] = "2126-01-10"  # shipped a century out: its own slip, and also "delivered before it shipped"
    out = scan(rows)
    assert said(out) == {30: ("Medium", ["Delivered"])}
    assert "far outside" in out[10]["reason"]


def test_a_far_date_in_a_third_column_never_excuses_two_rows_against_the_order():
    rows = [r + [(datetime.date.fromisoformat(r[2]) + datetime.timedelta(days=4)).isoformat()] for r in sheet(51, wrong=(20, 30))]
    rows[20][4] = "2126-02-01"  # invoiced a century out: it says nothing of Shipped and Delivered
    r = APP.post("/scan", json={"columns": COLS + ["Invoiced"], "rows": rows, "strength": 5})
    assert {i for i, x in enumerate(r.get_json()["rows"]) if "Delivered" in x["reason"] and "is before Shipped" in x["reason"]} == set()


# ...and one slip changes one date: a ticket closed a month before it was opened and first answered breaks two orders,
# its other dates none between them, so Closed alone is named (First Response was coloured too)
TICKET = ["Ticket", "Opened", "First Response", "Closed", "Minutes"]


def tickets(n=60, wrong=None):
    rows = []
    for k in range(n):
        opened = datetime.date(2026, 3, 1) + datetime.timedelta(days=(k * 7) % 40)  # no column runs up the sheet
        first = opened + datetime.timedelta(days=k % 2)
        rows.append([f"T{k:03}", opened.isoformat(), first.isoformat(),
                     (first + datetime.timedelta(days=1 + k % 5)).isoformat(), 5 + k % 30])
    if wrong is not None:
        i, col, days = wrong
        rows[i][col] = (datetime.date.fromisoformat(rows[i][1]) + datetime.timedelta(days=days)).isoformat()
    return rows


def ticket_said(rows):
    r = APP.post("/scan", json={"columns": TICKET, "rows": rows, "strength": 5})
    return {i: (x["severity"], x["cells"]) for i, x in enumerate(r.get_json()["rows"]) if "is before" in x["reason"]}


def test_the_date_that_breaks_its_order_with_two_other_dates_of_the_row_is_named_alone():
    assert ticket_said(tickets(wrong=(25, 3, -30))) == {25: ("Medium", ["Closed"])}


def test_a_date_that_breaks_one_order_only_names_both_when_neither_is_the_sheets_order():
    rows = tickets()
    rows[25][3] = rows[25][1]  # closed the day it opened, but a day before its first response (opened the day before)
    rows[25][2] = (datetime.date.fromisoformat(rows[25][1]) + datetime.timedelta(days=1)).isoformat()
    assert ticket_said(rows) == {25: ("Medium", ["First Response", "Closed"])}


# AH-211: a report's lines share its Submitted date; one line submitted before its expense, its other line a month later:
# the line's Submitted date also differs from its own report's, so it is the slip, named alone (adversarial episode 19)
REPORT = ["Report", "Expense date", "Submitted", "Amount"]


def reports(n=40, lines=2):
    rows = []
    for r in range(n):
        spent = DAY + datetime.timedelta(days=(r * 37) % 300)  # reports in no date order
        sent = spent + datetime.timedelta(days=5 + r % 20 + lines)
        for k in range(lines):
            rows.append([f"ER-{r:03}", (spent + datetime.timedelta(days=k)).isoformat(), sent.isoformat(), 20 + (r * 7 + k) % 90])
    return rows


def scan_report(rows):
    r = APP.post("/scan", json={"columns": REPORT, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def test_a_date_that_breaks_the_order_and_differs_from_its_own_records_lines_is_named_alone():
    rows = reports()
    rows[31][2] = (datetime.date.fromisoformat(rows[31][1]) - datetime.timedelta(days=5)).isoformat()
    assert said(scan_report(rows)) == {31: ("Medium", ["Submitted"])}


def test_a_date_its_record_does_not_share_never_singles_out_either_date():
    rows = reports()
    for k, r in enumerate(rows):  # each line submitted on its own day: Submitted is no record's date
        r[2] = (datetime.date.fromisoformat(r[2]) + datetime.timedelta(days=k % 2)).isoformat()
    rows[31][2] = (datetime.date.fromisoformat(rows[31][1]) - datetime.timedelta(days=5)).isoformat()
    assert said(scan_report(rows)) == {31: ("Medium", ["Expense date", "Submitted"])}


def test_one_other_record_whose_lines_differ_still_lets_the_slip_be_named_and_two_do_not():
    for others, want in ((1, ["Submitted"]), (2, ["Expense date", "Submitted"])):
        rows = reports()
        rows[31][2] = (datetime.date.fromisoformat(rows[31][1]) - datetime.timedelta(days=5)).isoformat()
        for k in range(others):  # another report's second line submitted a day after its first: no order broken
            r = rows[2 * (3 + 7 * k) + 1]  # reports 3 and 10
            r[2] = (datetime.date.fromisoformat(r[2]) + datetime.timedelta(days=1)).isoformat()
        assert said(scan_report(rows)) == {31: ("Medium", want)}, others
