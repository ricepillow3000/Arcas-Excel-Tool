"""AH-198: a record split over lines (a journal entry, an order's items), each value of its column one run down the
sheet. A column the same on every line of every record (an entry's posting date) is wrong on the one line of a record
that differs from its other lines, which agree. And two amount columns whose sums agree in every record but one (an
entry's debits and credits) put that record off: where swapping two neighbouring digits of one of its cells, and only
one, makes it agree, that cell is the slip (a 7,647.67 revenue typed 6,747.67). Synthetic sheets only."""
import datetime

from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Entry", "Posted", "Account", "Debit", "Credit"]


def journal(entries=20):
    """Entries of 3 lines: a receivable debited, revenue and VAT credited, all posted on the entry's day."""
    rows = []
    for k in range(entries):
        day = (datetime.date(2026, 1, 2) + datetime.timedelta(days=k)).isoformat()
        revenue = round(1000 + k * 431.17 % 6000, 2)
        vat = round(revenue * 0.2, 2)
        rows += [[f"JE-{1001 + k}", day, "Receivable", round(revenue + vat, 2), None],
                 [f"JE-{1001 + k}", day, "Revenue", None, revenue], [f"JE-{1001 + k}", day, "VAT", None, vat]]
    return rows


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def flagged(out):
    return {i: (r["severity"], r["cells"]) for i, r in enumerate(out) if r["severity"] not in (None, "Noted")}


def test_the_one_line_of_an_entry_posted_on_another_day_is_flagged():
    rows = journal()
    rows[31][1] = "2026-01-02"  # the third line of JE-1011, posted on the 12th
    out = scan(rows)
    assert flagged(out) == {31: ("Medium", ["Posted"])}
    assert out[31]["reason"] == "Posted 2026-01-02 differs from the other lines of Entry JE-1011, which all have 2026-01-12"


def test_nineteen_entries_are_too_few_to_know_the_rule():
    rows = journal(19)
    rows[31][1] = "2026-01-02"
    assert flagged(scan(rows)) == {}


def test_in_an_entry_of_two_lines_which_one_differs_is_unknown():
    rows = [r for k, r in enumerate(journal()) if k != 32]  # JE-1011 without its VAT line
    rows[31][1] = "2026-01-02"
    assert "differs from the other lines" not in scan(rows)[31]["reason"]


def test_digits_swapped_in_one_line_put_its_entry_off_and_name_that_line():
    rows = journal()
    good = rows[31][4]
    rows[31][4] = float(str(good)[1] + str(good)[0] + str(good)[2:])  # 3,1xx.xx typed 1,3xx.xx
    out = scan(rows)
    assert flagged(out) == {31: ("Medium", ["Credit"])}
    assert "two digits swapped" in out[31]["reason"] and out[31]["likely"] == {"Credit": good}


def test_an_entry_off_by_an_amount_no_swap_explains_names_no_line():
    rows = journal()
    rows[31][4] = round(rows[31][4] + 1, 2)
    assert flagged(scan(rows)) == {}


def test_two_entries_off_are_how_the_sheet_is_never_one_slip():
    rows = journal()
    for i in (31, 46):
        rows[i][4] = float(str(rows[i][4])[1] + str(rows[i][4])[0] + str(rows[i][4])[2:])
    assert flagged(scan(rows)) == {}


def test_a_crafted_wide_sheet_cannot_make_the_ah198_checks_run_for_minutes():
    # pairs of date and number columns, records against every column, labels against every number column: each grows
    # with the width, so each is capped in sheet order (20 date columns, 3 record columns, 40 and 50 number columns)
    import time

    import numpy as np

    from anomaly_hunter.engine import pipeline
    from anomaly_hunter.engine.load import load_from_records
    n = 120
    cols = [f"R{k}" for k in range(8)] + [f"L{k}" for k in range(40)] + [f"D{k}" for k in range(150)] + [f"N{k}" for k in range(300)]
    rows = [[f"r{i // 3}" for _ in range(8)] + [f"x{(i + k) % 4}" for k in range(40)]
            + [(datetime.date(2026, 1, 1) + datetime.timedelta(days=(i * 7 + k) % 90)).isoformat() for k in range(150)]
            + [float((i * 31 + k * 17) % 97) * 10 ** (i % 4) for k in range(300)] for i in range(n)]
    df, types, _ = load_from_records(cols, rows)
    skip = np.zeros(len(df), bool)
    t = time.perf_counter()
    pipeline.date_order(df, types, skip, [[] for _ in range(n)])
    records = pipeline._records(df, types, skip)
    pipeline.same_in_record(df, types, skip, records)
    pipeline.balances(df, types, skip, records)
    pipeline.by_scale(df, types, skip, 6, voted=[set() for _ in range(n)])
    assert len(records) <= 3 and time.perf_counter() - t < 20
