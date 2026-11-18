"""AH-198 fix round 2: a record's own arithmetic. Where two amount columns agree in every record but a few (a journal's
debits and credits; at most max(1, 2%) off), an amount inside a record that agrees is no lone slip, which would break
the balance: worth a check at most, never a vote or a "likely" (a 1,184,000 machine bought, "likely 11840"). A record
off is one slip: named where one swap of two neighbouring digits mends it, and where two could, the one whose amount
the sheet writes again outside the record (the invoice behind a receipt) is the real one. Synthetic sheets only."""
import datetime

from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Entry", "Posted", "Account", "Debit", "Credit"]


def journal(entries=100):
    """Entries of 3 lines: a receivable debited, revenue and VAT credited."""
    rows = []
    for k in range(entries):
        day = (datetime.date(2026, 1, 2) + datetime.timedelta(days=k % 90)).isoformat()
        revenue = round(1000 + k * 431.17 % 6000, 2)
        vat = round(revenue * 0.2, 2)
        rows += [[f"JE-{1001 + k}", day, "Receivable", round(revenue + vat, 2), None],
                 [f"JE-{1001 + k}", day, "Revenue", None, revenue], [f"JE-{1001 + k}", day, "VAT", None, vat]]
    return rows


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def sure(out):
    return {i: r["cells"] for i, r in enumerate(out) if r["severity"] in ("High", "Medium")}


def test_a_huge_amount_in_an_entry_that_balances_is_worth_a_check_never_a_slip():
    rows = journal()
    rows[30:33] = [["JE-1011", rows[30][1], "Receivable", 1420800.0, None], ["JE-1011", rows[30][1], "Revenue", None, 1184000.0],
                   ["JE-1011", rows[30][1], "VAT", None, 236800.0]]
    out = scan(rows)
    assert sure(out) == {}
    assert out[31]["severity"] == "Low" and "Credit" in out[31]["cells"] and not out[31].get("likely")


def swap(rows, i, col=4):
    t = f"{rows[i][col]:.2f}"
    rows[i][col] = float(t[1] + t[0] + t[2:])


def test_two_entries_off_in_a_hundred_are_each_named_by_their_swap():
    rows = journal()
    for i in (31, 151):
        swap(rows, i)
    assert sure(scan(rows)) == {31: ["Credit"], 151: ["Credit"]}


def test_three_entries_off_in_a_hundred_are_how_the_sheet_is():
    rows = journal()
    for i in (31, 151, 241):
        swap(rows, i)
    assert sure(scan(rows)) == {}


def receipt(rows, received, invoiced):
    """A receipt entry of 2 lines whose debit and credit are each other's swap, appended after the invoices."""
    rows += [["JE-2001", "2026-04-02", "Cash", received, None], ["JE-2001", "2026-04-02", "Customer", None, invoiced]]
    return rows


def test_of_two_cells_a_swap_could_mend_the_one_the_sheet_writes_again_elsewhere_is_the_real_one():
    rows = journal()
    invoiced = rows[30][3]  # the receivable JE-1011 debited, received later with two digits swapped
    t = f"{invoiced:.2f}"
    out = scan(receipt(rows, float(t[1] + t[0] + t[2:]), invoiced))
    assert sure(out) == {300: ["Debit"]}


def test_of_two_cells_a_swap_could_mend_neither_is_named_when_neither_is_written_elsewhere():
    rows = receipt(journal(), 6185.38, 6815.38)
    assert sure(scan(rows)) == {}


def test_a_huge_amount_in_an_entry_that_does_not_balance_is_still_a_slip():
    rows = journal()
    rows[31][4] = round(rows[31][4] * 100, 2)  # the revenue typed 100x: the entry is off by it
    out = scan(rows)
    assert out[31]["severity"] == "Medium" and "Credit" in out[31]["cells"]
