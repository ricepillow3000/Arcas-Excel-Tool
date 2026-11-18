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
