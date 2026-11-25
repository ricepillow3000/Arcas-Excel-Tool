"""AH-215 (the ML engineer's advice, John 2026-11-25: "judge normal within each group, not across the whole sheet"):
a small product line priced 3x the big one had its decimal slips (300 -> 30) caught 0 times in 20 and the big line's
18, because the slip landed inside the big line's prices. A label column now sets its groups' own limits when their
usual sizes differ 2x or more (it was 10x). Synthetic sheets only."""
import random

from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Order ID", "Product line", "Price", "Qty"]


def sheet(seed, mult, small=40):
    r = random.Random(seed)
    rows = [[f"O{i:04d}", "Widget", round(r.gauss(100, 12), 2), r.randint(1, 9)] for i in range(400)]
    rows += [[f"P{i:04d}", "Gadget", round(r.gauss(100 * mult, 12 * mult), 2), r.randint(1, 9)] for i in range(small)]
    r.shuffle(rows)
    return rows


def flagged(rows):
    out = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5}).get_json()["rows"]
    return {i for i, r in enumerate(out) if r["severity"] not in (None, "Noted")}


def caught(group, mult, seeds=range(10)):
    n = 0
    for seed in seeds:
        rows = sheet(seed, mult)
        i = next(i for i, x in enumerate(rows) if x[1] == group)
        rows[i][2] = round(rows[i][2] * 0.1, 2)
        n += i in flagged(rows)
    return n


def test_a_decimal_slip_in_a_small_group_priced_3x_the_big_one_is_caught_as_often_as_in_the_big_one():
    small, big = caught("Gadget", 3), caught("Widget", 3)
    assert small >= 9 and big >= 9, (small, big)  # was 0 of 10 for the small group


def test_two_groups_of_honest_prices_3x_apart_flag_nothing():
    assert all(not flagged(sheet(seed, 3)) for seed in range(10))


def test_two_groups_of_honest_prices_1_5x_apart_flag_nothing():
    assert all(not flagged(sheet(seed, 1.5)) for seed in range(10))


def flagged_in(group, mult, strength, seeds=range(10)):
    n = 0
    for seed in seeds:
        rows = sheet(seed, mult)
        out = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": strength}).get_json()["rows"]
        n += sum(r["severity"] not in (None, "Noted") for x, r in zip(rows, out) if x[1] == group)
    return n


def test_at_strength_8_a_small_groups_honest_prices_are_judged_by_its_own_normal():
    # AH-215: the column's limits and the cross-column score, both set by the big group, flagged 2.25% of the small
    # group's honest rows and 0.24% of the big group's (about 9 of the small group's 400 rows in 10 sheets)
    assert flagged_in("Gadget", 3, 8) <= 2


def test_at_strength_8_a_decimal_slip_in_the_small_group_is_still_caught():
    n = 0
    for seed in range(10):
        rows = sheet(seed, 3)
        i = next(i for i, x in enumerate(rows) if x[1] == "Gadget")
        rows[i][2] = round(rows[i][2] * 0.1, 2)
        out = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 8}).get_json()["rows"]
        n += out[i]["severity"] not in (None, "Noted")
    assert n >= 9
