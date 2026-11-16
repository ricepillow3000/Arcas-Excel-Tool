"""AH-178: blind round 2's misses, each rebuilt as a small synthetic sheet shaped like the real table: subtotal rows, their
numbers blanked, matched each other and hid a real copied row; an election table's mode "TOTAL" on every row made 7,030
rows "Totals/summary row"; a misspelling in a list of over 200 labels was never guessed; a year column (a number) never
got the far-date rule, so 2084 among 1981-2022 passed; and a 10th percentile above its 90th was never named."""
import time

import numpy as np
import pytest

from anomaly_hunter.agents.scan_agent import scan
from anomaly_hunter.engine import pipeline
from anomaly_hunter.engine.load import load_from_records


def flagged(out, word):
    return [i for i, o in enumerate(out) if o["severity"] in ("Low", "Medium", "High") and word in o["reason"]]


# A: subtotal rows, their numbers left out, all read "Total" and nothing else: 150 of them were "many repeats"
def sales(groups=150, seed=1):
    r, rows = np.random.default_rng(seed), []
    for g in range(groups):
        block = [[str(r.choice(["North", "South", "East", "West"])), str(r.choice(["Tea", "Cake", "Soup", "Bread"])),
                  int(r.integers(1, 400)), round(float(r.uniform(1, 90)), 2)] for _ in range(10)]
        rows += block + [["Total", "", sum(b[2] for b in block), ""]]
    return rows


def test_a_copied_row_among_many_subtotal_rows_is_still_a_duplicate():
    rows = sales()
    rows[1500] = list(rows[200])
    out = scan(["Region", "Item", "Units", "Price"], rows, fair=False)[1]
    assert flagged(out, "Duplicate of row") == [1500], [out[i]["reason"] for i in flagged(out, "repeat")]
    assert "Duplicate of row 202" in out[1500]["reason"]
    assert out[10]["reason"] == "Totals/summary row - not checked"


def test_many_real_repeats_among_subtotal_rows_are_still_one_note_on_a_real_row():
    rows, r = sales(), np.random.default_rng(2)
    data = [i for i, row in enumerate(rows) if row[0] != "Total"]
    copies = sorted(r.choice(data[20:], 300, replace=False))
    for i in copies:
        rows[i] = list(rows[int(r.choice([j for j in data if j < i]))])
    out = scan(["Region", "Item", "Units", "Price"], rows, fair=False)[1]
    noted = flagged(out, "repeat an earlier row")
    assert not flagged(out, "Duplicate of row") and len(noted) == 1, [out[i]["reason"] for i in noted]
    assert rows[noted[0]][0] != "Total" and out[noted[0]]["reason"].startswith(f"{len(copies)} of ")


# B: an election table's mode is "TOTAL" on every row; a sparse row there is data, never a summary
def votes(n=600, seed=3):
    r = np.random.default_rng(seed)
    return [[f"County {i // 3}", str(r.choice(["A. Smith", "B. Jones", "C. Lee"])), "" if i % 4 == 0 else str(r.choice(["DEM", "REP"])),
             "TOTAL", int(r.integers(50, 9000))] for i in range(n)]


def test_a_column_that_says_total_on_most_rows_is_a_category_never_a_summary_label():
    out = scan(["county", "candidate", "party", "mode", "votes"], votes(), fair=False)[1]
    assert not any("Totals/summary row" in o["reason"] for o in out), sum("Totals/summary row" in o["reason"] for o in out)


def test_a_real_total_row_below_such_a_table_is_still_left_out():
    rows = votes()
    rows.append(["Total", "", "", "", sum(r[4] for r in rows)])
    out = scan(["county", "candidate", "party", "mode", "votes"], rows, fair=False)[1]
    assert [i for i, o in enumerate(out) if "Totals/summary row" in o["reason"]] == [len(rows) - 1]


def test_a_label_column_filled_only_on_its_total_row_still_marks_it():
    r = np.random.default_rng(4)
    rows = [["", int(r.integers(1, 90)), round(float(r.uniform(1, 9)), 2), int(r.integers(1, 5))] for _ in range(60)]
    rows.append(["Total", sum(x[1] for x in rows), "", ""])
    out = scan(["Label", "Units", "Price", "Boxes"], rows, fair=False)[1]
    assert out[-1]["reason"] == "Totals/summary row - not checked"


# E: a misspelling in a list of more than 200 labels, each written 10+ times on average
def genres(n_labels=260, slip="Hoorror", usual="Horror", seed=5):
    r = np.random.default_rng(seed)
    words = [f"{a}{b}" for a in ("Alpha", "Bravo", "Delta", "Gamma", "Sigma", "Omega", "Kappa", "Theta", "Zeta", "Lambda",
                                 "Tango", "Victor", "Oscar") for b in ("land", "ville", "ford", "burg", "ton", "mouth", "port",
                                                                       "field", "wick", "stead", "bury", "ham", "worth",
                                                                       "by", "dale", "ley", "more", "well", "side", "wood")]
    labels = [usual] * 40 + [w for w in words[:n_labels] for _ in range(int(r.integers(8, 14)))] + [slip]
    return [[f"t{i}", w, int(r.integers(1, 200))] for i, w in enumerate(labels)]


@pytest.mark.parametrize("slip, usual", [("Hoorror", "Horror"), ("Abgentina", "Argentina"), ("Bankign", "Banking"),
                                         ("WORKING FMILIES", "WORKING FAMILIES")])
def test_a_misspelling_in_a_list_of_more_than_200_labels_is_worth_a_check(slip, usual):
    out = scan(["Id", "Label", "Votes"], genres(slip=slip, usual=usual), fair=False)[1]
    assert f'Label "{slip}" looks like a misspelling of "{usual}"' in out[-1]["reason"], out[-1]["reason"]


def test_a_wide_list_that_repeats_each_label_under_10_times_gets_no_misspelling_guess():
    rows = [[f"t{i}", f"Label{k:05d}", 3] for i, k in enumerate(np.repeat(np.arange(400), 5))] + [["x", "Horror", 1]] * 6
    rows.append(["y", "Hoorror", 1])
    out = scan(["Id", "Label", "Votes"], rows, fair=False)[1]
    assert not flagged(out, "misspelling")


def test_a_crafted_column_of_thousands_of_labels_cannot_make_the_misspelling_guess_run_for_minutes():
    # 5,000 usual labels written 15 times and 5,000 rare ones written once, all one letter apart: each rare label is a
    # one-letter slip of a usual one, the worst case for comparing every rare label with every usual one
    usual = [f"lab{k:05d}x" for k in range(5000)]
    rare = [f"lab{k:05d}y" for k in range(5000)]
    rows = [[w, 1] for w in usual for _ in range(15)] + [[w, 1] for w in rare]
    df, types, _ = load_from_records(["Label", "N"], rows)
    t = time.perf_counter()
    pipeline.spellings(df, types, np.zeros(len(df), bool))
    assert time.perf_counter() - t < 10


# F: a whole-number column headed as a year, read by the far-date rule
def years(head, slip=None, lo=1981, hi=2022, n=300, seed=6):
    r = np.random.default_rng(seed)
    rows = [[f"film {i}", int(r.integers(lo, hi + 1)), round(float(r.uniform(1, 9)), 1)] for i in range(n)]
    if slip is not None:
        rows[150][1] = slip
    return scan(["title", head, "rating"], rows, fair=False)[1]


@pytest.mark.parametrize("head", ["year", "Year", "release_year", "year_built", "releaseYear", "Yr"])
def test_a_year_far_outside_a_year_column_is_flagged(head):
    out = years(head, 2084)
    assert f"{head} 2084 is far outside the column's years (" in out[150]["reason"], out[150]["reason"]
    assert out[150]["severity"] == "Medium" and out[150]["cells"] == [head]


def test_an_honest_column_of_years_over_a_century_is_quiet():
    out = years("year", lo=1901, hi=2021)
    assert not flagged(out, "far outside")


@pytest.mark.parametrize("head", ["years_of_service", "Yearly sales", "Plays"])
def test_a_column_not_headed_as_a_year_is_never_read_as_years(head):
    assert not flagged(years(head, 2084), "far outside the column's years")


# G: one column at most another on every other row
def bands(n=1200, swaps=(400,), seed=7):
    r = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        mid = float(r.uniform(20, 80))
        rows.append([f"site {i}", round(mid - float(r.uniform(1, 15)), 1), round(mid, 1), round(mid + float(r.uniform(1, 15)), 1)])
    for i in swaps:
        rows[i][1], rows[i][3] = rows[i][3], rows[i][1]
    return rows


def test_a_10th_percentile_above_its_90th_is_named():
    rows = bands()
    out = scan(["site", "p10", "p50", "p90"], rows, fair=False)[1]
    assert f"p10 {rows[400][1]} is above p90 {rows[400][3]}" in out[400]["reason"], out[400]["reason"]
    assert out[400]["severity"] == "Medium" and {"p10", "p90"} <= set(out[400]["cells"])
    assert not out[400]["likely"] and not out[400]["maybe"]
    assert flagged(out, " is above ") == [400]


def test_two_swapped_rows_are_each_named_and_three_break_the_order():
    out = scan(["site", "p10", "p50", "p90"], bands(swaps=(300, 900)), fair=False)[1]
    assert flagged(out, " is above ") == [300, 900]
    out = scan(["site", "p10", "p50", "p90"], bands(swaps=(300, 600, 900)), fair=False)[1]
    assert not flagged(out, " is above ")


def test_an_order_that_holds_on_fewer_than_1000_rows_is_never_judged():
    out = scan(["site", "p10", "p50", "p90"], bands(n=900), fair=False)[1]
    assert not flagged(out, " is above ")


def test_two_columns_on_different_scales_are_no_order():
    r = np.random.default_rng(8)
    rows = [[f"p{i}", int(r.integers(18, 90)), int(r.integers(20000, 150000))] for i in range(1200)]
    rows[300][2] = 25  # a slip in income, under the age: the scales never meet, so no order between them is shown
    out = scan(["person", "age", "income"], rows, fair=False)[1]
    assert not flagged(out, " is above ")


def test_two_columns_that_cross_on_many_rows_are_no_order():
    r = np.random.default_rng(9)
    rows = [[f"p{i}", round(float(r.uniform(0, 100)), 1), round(float(r.uniform(0, 100)), 1)] for i in range(1200)]
    out = scan(["id", "a", "b"], rows, fair=False)[1]
    assert not flagged(out, " is above ")


def test_a_crafted_sheet_of_160_number_columns_keeps_the_order_check_fast():
    r = np.random.default_rng(10)
    base = r.uniform(0, 1, (3000, 1))
    x = np.sort(base + r.uniform(0, 1, (3000, 160)), axis=1)  # every column at most the next: every pair an order
    df, types, _ = load_from_records([f"p{k}" for k in range(160)], x.round(4).tolist())  # every pair names an order
    t = time.perf_counter()
    pipeline.order(df, types, np.zeros(len(df), bool))
    assert time.perf_counter() - t < 2


# AH-178 fix round 1: blind rounds 2-3 paired unrelated neighbours that merely sat in order (UFC's b_draw under b_wins,
# hotels' booking_changes under agent, lng under lat): about 60 false Medium rows. Only headers that name an order
def ordered(lo, hi, n=2000, breaks=(500, 1500), seed=11):
    r = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        a = round(float(r.uniform(0, 50)), 1)
        rows.append([f"r{i}", a, round(float(r.uniform(0, 9)), 1), round(a + float(r.uniform(0, 50)), 1)])
    for i in breaks:
        rows[i][1], rows[i][3] = rows[i][3], rows[i][1]
    return scan(["id", lo, "other", hi], rows, fair=False)[1], rows


@pytest.mark.parametrize("lo,hi", [("b_draw", "b_wins"), ("years_code_pro", "comp_total"), ("booking_changes", "agent"),
                                   ("age", "height"), ("lng", "lat")])
def test_unrelated_columns_that_happen_to_be_in_order_are_never_judged(lo, hi):
    out, _ = ordered(lo, hi)
    assert not flagged(out, " is above ")


@pytest.mark.parametrize("lo,hi", [("min_temp", "max_temp"), ("Low", "High"), ("start_year", "end_year"),
                                   ("avg_ticket_price", "top_ticket_price"), ("minTemp", "maxTemp")])
def test_columns_whose_headers_name_an_order_are_judged(lo, hi):
    out, rows = ordered(lo, hi)
    assert flagged(out, " is above ") == [500, 1500]
    assert f"{lo} {rows[500][1]} is above {hi} {rows[500][3]}" in out[500]["reason"], out[500]["reason"]


def test_a_10th_percentile_is_judged_against_its_90th_with_the_50th_between():
    rows = bands(n=2000, swaps=(400,))
    heads = ["site", "Hourly 10th Percentile", "Hourly 50th Percentile", "Hourly 90th Percentile"]
    out = scan(heads, rows, fair=False)[1]
    assert f"Hourly 10th Percentile {rows[400][1]} is above Hourly 90th Percentile {rows[400][3]}" in out[400]["reason"]
    assert flagged(out, " is above ") == [400]


def test_a_stocks_close_above_its_high_and_low_above_its_open_are_named():
    r = np.random.default_rng(12)
    rows = []
    for i in range(2000):
        o, c = (round(float(v), 2) for v in r.uniform(90, 110, 2))
        rows.append([f"d{i}", o, round(max(o, c) + float(r.uniform(0, 3)), 2), round(min(o, c) - float(r.uniform(0, 3)), 2), c])
    rows[600][4] = round(rows[600][2] + 5, 2)
    rows[1600][3] = round(rows[1600][1] + 0.5, 2)
    rows[1600][4] = round(rows[1600][1] + 2, 2)  # its Close stays above its Low: only Low above Open is wrong
    out = scan(["date", "Open", "High", "Low", "Close"], rows, fair=False)[1]
    assert f"Close {rows[600][4]} is above High {rows[600][2]}" in out[600]["reason"], out[600]["reason"]
    assert f"Low {rows[1600][3]} is above Open {rows[1600][1]}" in out[1600]["reason"], out[1600]["reason"]
    assert flagged(out, " is above ") == [600, 1600]
