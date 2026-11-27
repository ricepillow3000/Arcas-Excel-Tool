"""AH-48 (blind round 36): a hotel bookings table with no ID column has 4,324 rows that repeat an earlier row exactly -
two bookings with the same hotel, dates, guests and rate - and each was a Medium "Duplicate of row N". Like blanks spread
through a sheet (AH-28), max(20, 1% of the rows) repeats found in every fifth of the sheet are one note: how many, and
where the first is. A few, or a block of them (a range pasted twice), are still each a slip. Synthetic sheets only."""
import numpy as np
import pytest

from anomaly_hunter.agents.scan_agent import scan

COLS = ["hotel", "arrival_month", "adults", "children", "meal", "adr"]


def bookings(n=3000, seed=6):
    rng = np.random.default_rng(seed)
    return [[["City Hotel", "Resort Hotel"][int(rng.integers(0, 2))], int(rng.integers(1, 13)), int(rng.integers(1, 4)),
             int(rng.integers(0, 3)), ["BB", "HB", "SC"][int(rng.integers(0, 3))], round(float(rng.uniform(40, 260)), 3)]
            for _ in range(n)]


def flagged(out, word):
    return [i for i, o in enumerate(out) if o["severity"] in ("Low", "Medium", "High") and word in o["reason"]]


def test_many_repeated_rows_through_a_sheet_with_no_id_are_one_note():
    rows, rng = bookings(), np.random.default_rng(7)
    copies = sorted(rng.choice(np.arange(10, 3000), 600, replace=False))
    for i in copies:
        rows[i] = list(rows[int(rng.integers(0, i))])
    out = scan(COLS, rows, fair=False)[1]
    assert not flagged(out, "Duplicate of row"), len(flagged(out, "Duplicate of row"))
    noted = flagged(out, "repeat an earlier row")
    assert len(noted) == 1 and out[noted[0]]["severity"] == "Low", [out[i]["reason"] for i in noted[:3]]
    first = noted[0]
    assert out[first]["reason"].startswith(f"{len(copies)} of 3000 rows repeat an earlier row exactly, all through the sheet: "
                                           f"the first is this one, a copy of row "), out[first]["reason"]


def test_a_few_repeated_rows_are_still_each_a_slip():
    rows = bookings()
    for i in (400, 1200, 2100, 2800, 2950):
        rows[i] = list(rows[i - 300])
    out = scan(COLS, rows, fair=False)[1]
    assert flagged(out, "Duplicate of row") == [400, 1200, 2100, 2800, 2950]
    assert all(out[i]["severity"] == "Medium" for i in (400, 1200, 2100, 2800, 2950))


def test_a_block_pasted_twice_is_still_each_a_slip():
    rows = bookings()
    rows[1000:1100] = [list(r) for r in rows[900:1000]]  # a range pasted again below itself
    out = scan(COLS, rows, fair=False)[1]
    assert flagged(out, "Duplicate of row") == list(range(1000, 1100))


def test_the_note_colours_its_whole_row():
    rows, rng = bookings(), np.random.default_rng(7)
    for i in sorted(rng.choice(np.arange(10, 3000), 600, replace=False)):
        rows[i] = list(rows[int(rng.integers(0, i))])
    out = scan(COLS, rows, fair=False)[1]
    noted = [o for o in out if "repeat an earlier row" in o["reason"]]
    assert len(noted) == 1 and noted[0]["cells"] == COLS, noted


def orders(text_id):
    rng = np.random.default_rng(5)
    rows = [[f"INV-{50001 + i}" if text_id else 50001 + i, f"2025-{1 + i // 250:02d}-{1 + i // 10 % 25:02d}", f"C{int(rng.integers(1, 400))}",
             round(float(rng.uniform(5, 900)), 2)] for i in range(3000)]
    again = [list(r) for k, r in enumerate(rows) if k // 10 % 25 == 3]  # 12 days' orders imported twice
    return sorted(rows + again, key=lambda r: (r[1], str(r[0]))), len(again)


@pytest.mark.parametrize("text_id", [False, True])
def test_orders_imported_twice_are_each_a_slip_when_an_id_tells_records_apart(text_id):
    # AH-48 review: 120 orders imported twice, sorted by date, so the copies sat all through the sheet, were one note
    # saying "nothing like an ID tells them apart" - beside an Order ID column no two different orders share
    rows, copies = orders(text_id)
    out = scan(["Order ID", "Order date", "Customer", "Amount"], rows, fair=False)[1]
    assert len(flagged(out, "Duplicate of row")) == copies and not flagged(out, "repeat an earlier row")


def test_ranges_pasted_again_in_every_fifth_of_the_sheet_are_each_a_slip():
    # AH-48 review: 5 ranges of 12 rows, each pasted below itself, one in each fifth: 60 copies, one note
    rows = bookings()
    for k in range(5):
        s = 300 + 600 * k
        rows[s + 12:s + 24] = [list(r) for r in rows[s:s + 12]]
    out = scan(COLS, rows, fair=False)[1]
    assert set(range(312, 324)) <= set(flagged(out, "Duplicate of row")) and not flagged(out, "repeat an earlier row")


def test_real_bookings_repeated_in_pairs_stay_in_the_note():
    # round 36's hotel table repeats real bookings in pairs (A B A B: 65 runs of 2), never in runs of 5
    rows, rng = bookings(), np.random.default_rng(8)
    for i in sorted(rng.choice(np.arange(10, 2990, 6), 300, replace=False)):
        rows[i + 2], rows[i + 3] = list(rows[i]), list(rows[i + 1])
    out = scan(COLS, rows, fair=False)[1]
    assert not flagged(out, "Duplicate of row") and len(flagged(out, "repeat an earlier row")) == 1


def results(seed=9):
    # a contest's results: the same entrant may come back another year, so names repeat, but most are written once
    rng = np.random.default_rng(seed)
    return [[2000 + i // 40, f"Entrant {i % 150}" if i % 3 == 0 else f"Entrant {i}", ["Peru", "Chad", "Fiji"][i % 3],
             int(rng.integers(0, 8)), int(rng.integers(0, 8))] for i in range(400)]


@pytest.mark.parametrize("unknown", ["?", "*", "Unknown"])
def test_two_unknown_entrants_whose_scores_tie_are_not_one_record(unknown):
    # AH-173 (blind round 1): contestant "?" or "*" with the same year, country and scores was "Duplicate of row N" 41
    # times: two people whose names were not kept are not the same person
    cols, rows = ["year", "contestant", "country", "p1", "p2"], results()
    for i in (101, 102, 250, 251):
        rows[i][1] = unknown
    rows[102][2:], rows[251][2:] = rows[101][2:], rows[250][2:]
    out = scan(cols, rows, fair=False)[1]
    assert not flagged(out, "Duplicate of row"), [out[i]["reason"] for i in flagged(out, "Duplicate of row")]


def test_a_named_entrant_repeated_exactly_is_still_a_duplicate():
    cols, rows = ["year", "contestant", "country", "p1", "p2"], results()
    rows[102] = list(rows[101])
    out = scan(cols, rows, fair=False)[1]
    assert flagged(out, "Duplicate of row") == [102]


def test_a_row_repeated_with_unknown_in_a_category_column_is_still_a_duplicate():
    # "Unknown" in a column of a few labels (a meal plan) says nothing about who the row is: the copy is still the same
    # booking twice. Only a column whose labels mostly differ row to row (at least half of them, AH-173) names the row
    rows = bookings()
    rows[700][4] = "Unknown"
    rows[1500] = list(rows[700])
    out = scan(COLS, rows, fair=False)[1]
    assert 1500 in flagged(out, "Duplicate of row")


@pytest.mark.parametrize("times, duplicate", [(2, False), (3, True)])
def test_a_name_column_names_rows_when_its_labels_are_at_least_half_its_cells(times, duplicate):
    # each entrant written twice: as many labels as half the cells, a name; three times, a third: a label like a meal
    cols, rows = ["year", "contestant", "country", "p1", "p2"], results()
    for i, r in enumerate(rows):
        r[1] = f"Entrant {i // times}"
    rows[101][1] = rows[250][1] = "?"
    rows[250][2:] = rows[101][2:]
    rows[250][0] = rows[101][0]
    out = scan(cols, rows, fair=False)[1]
    assert (250 in flagged(out, "Duplicate of row")) == duplicate


def test_a_row_with_its_own_id_and_name_repeated_exactly_is_a_duplicate_whatever_na_sits_in_another_column():
    # AH-173 fix round 1 (blind round 1, Pokemon): lunala's row copied exactly, its url_icon "NA" like 229 of 950 rows, was
    # no longer "Duplicate of row N": an id and a name tell the row apart, so the "NA" beside them is no unknown entrant
    rng = np.random.default_rng(7)
    rows = [[i + 1, f"mon{i}", "NA" if i % 4 == 0 else f"https://img.example/{i}.png", round(float(rng.uniform(1, 9)), 2)]
            for i in range(60)]
    rows.insert(21, list(rows[20]))
    out = scan(["id", "name", "url", "size"], rows, fair=False)[1]
    assert flagged(out, "Duplicate of row") == [21], [out[i]["reason"] for i in flagged(out, "Duplicate of row")]


def test_two_unknown_entrants_whose_decimal_scores_tie_are_not_one_record():
    # AH-173 fix round 2: a score written to the hundredth is nearly unique row to row, but a measure never names the
    # row; two "?" entrants with the same year, country and score are still two people whose names were not kept
    rng = np.random.default_rng(11)
    cols, rows = ["year", "contestant", "country", "score"], [r[:3] + [round(float(rng.uniform(10, 90)), 2)] for r in results()]
    rows[101][1] = rows[102][1] = "?"
    rows[102][0], rows[102][2:] = rows[101][0], rows[101][2:]
    out = scan(cols, rows, fair=False)[1]
    assert not flagged(out, "Duplicate of row"), [out[i]["reason"] for i in flagged(out, "Duplicate of row")]
