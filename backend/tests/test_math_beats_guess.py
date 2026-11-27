"""AH-236: the engine solves with code first. The blind bench had two wrong "likely" cards: a CTR typed 4.4 for 0.044 got
/1000 though Clicks / Impressions says 0.044, and a revenue 100x too big got /10 though /100 was as usual as /10.
Synthetic sheets in those shapes."""
import numpy as np

from anomaly_hunter.agents.scan_agent import scan


def ad_sheet(seed, places, typed):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(80):
        imp = int(rng.integers(50000, 400000))
        clicks = int(imp * np.exp(rng.normal(np.log(0.012), 0.8)))
        rows.append([f"C{i}", imp, clicks, round(clicks / imp, places)])
    rows[30][1:] = [103500, 4558, typed]
    return rows


def card(rows, cols, i):
    return scan(cols, rows, fair=False)[1][i]


def test_a_ctr_typed_as_a_whole_percent_is_solved_from_its_clicks_and_impressions():
    # 4558 / 103500 = 0.044039: the column's 4 places hold 0.044 within their rounding, not the /1000 the typo
    # pattern guessed from a median of 0.012
    for seed in range(3):
        rows = ad_sheet(seed, 4, 0.044)
        rows[30][3] = 4.4
        out = card(rows, ["Campaign", "Impressions", "Clicks", "CTR"], 30)
        assert out["likely"] == {"CTR": 0.044}, out


def test_a_ctr_the_rounding_cannot_pin_gets_no_arithmetic_card():
    # a CTR written to 1 place says 0.0 for every row: its rounding is wider than the answer, the sheet is no witness
    rows = ad_sheet(0, 1, 0.0)
    rows[30][3] = 4.4
    out = card(rows, ["Campaign", "Impressions", "Clicks", "CTR"], 30)
    assert out["likely"].get("CTR") != 0.044, out


def test_honest_ctr_rows_are_not_flagged_or_changed():
    rows = ad_sheet(0, 4, 0.044)
    out = scan(["Campaign", "Impressions", "Clicks", "CTR"], rows, fair=False)[1]
    assert not any((o.get("likely") or o.get("maybe")) for o in out)


def revenue_sheet(seed, typed):
    # an even spread on the log scale: 29% of the values lie within a factor 2 of 1024, 1000 to 12000 in all
    rev = np.round(np.geomspace(1000, 12000, 100) * (1 + 0.01 * seed), 2)
    rows = [[f"2024-01-{i % 28 + 1:02d}", f"p{i}", float(v)] for i, v in enumerate(rev)]
    rows[24][2] = typed
    return rows


def test_a_value_that_two_steps_back_would_both_make_usual_is_a_guess_not_likely():
    # 102445 may be 1024.45 x100 or 10244.5 x10: both are inside the column's band, nothing says which
    for seed in range(3):
        out = card(revenue_sheet(seed, 102445.0), ["day", "page", "Revenue"], 24)
        assert not out["likely"] and out["maybe"].get("Revenue") == 10244.5, out
        assert "(likely" not in out["reason"], out


def test_a_slip_only_one_step_can_undo_stays_likely():
    # a narrow band 90-130: 1100 can only be 110 x10, /100 is 11, nowhere near
    rng = np.random.default_rng(1)
    rows = [[f"p{i}", round(float(rng.uniform(90, 130)), 1)] for i in range(60)]
    rows[24][1] = 1100.0
    out = card(rows, ["page", "Price"], 24)
    assert out["likely"] == {"Price": 110.0}, out


def test_a_rival_step_no_value_lives_near_is_no_rival():
    # 430 may be 4.3 x100 or 43 x10, but 43 sits in the band only as the far end of a 6-value tail (5% of the column
    # within a factor 2 of it): the usual step stays likely
    v = np.round(np.concatenate([np.geomspace(1, 9, 100), [25, 30, 35, 40, 45, 50]]), 2)
    rows = [[f"p{i}", float(x)] for i, x in enumerate(v)] + [["z", 430.0]]
    out = card(rows, ["p", "Dose"], len(rows) - 1)
    assert out["likely"] == {"Dose": 4.3}, out


def test_a_total_is_never_solved_from_rounded_factors():
    # Impressions x CTR = 4554.748 from a CTR rounded to 4 places: the real clicks are not 4555, so a lost 99999 gets no card
    rows = ad_sheet(0, 4, 0.044)
    rows[30][1:3] = [103517, 99999]
    out = card(rows, ["Campaign", "Impressions", "Clicks", "CTR"], 30)
    assert not out["likely"] and not out["maybe"], out
