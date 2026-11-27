"""AH-236: the engine solves with code first. The blind bench had a wrong "likely" card: a CTR typed 4.4 for 0.044 got /1000
though Clicks / Impressions says 0.044. Synthetic sheets in that shape."""
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


def test_a_total_is_never_solved_from_rounded_factors():
    # Impressions x CTR = 4554.748 from a CTR rounded to 4 places: the real clicks are not 4555, so a lost 99999 gets no card
    rows = ad_sheet(0, 4, 0.044)
    rows[30][1:3] = [103517, 99999]
    out = card(rows, ["Campaign", "Impressions", "Clicks", "CTR"], 30)
    assert not out["likely"] and not out["maybe"], out
