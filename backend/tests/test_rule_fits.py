"""AH-54 (blind round 37): an arithmetic rule is believed only where its numbers can show it. Tornado records' sn (0/1)
"= ns + f3" held in 97% of rows only because f3 (a third county's code) is 0 there: 648 Medium rows. College admissions'
rates under 0.06 all "agreed to the cent", so stderr x stderr "= attend" was a rule (474 Medium rows and 10 wrong "likely"
values). Broadway's weekly gross, a whole dollar amount, missed avg ticket price x seats by 1.0004-1.009 times the half
cent the price's rounding allows (62 Medium rows). And a 17-row column's real 364 got "likely 3.64". Synthetic sheets
only, shaped like those tables."""
import numpy as np
import pytest

from anomaly_hunter.agents.scan_agent import scan
from anomaly_hunter.server import create_app


def adds(out):
    return [i for i, o in enumerate(out) if "does not add up" in o["reason"]]


def test_a_sum_whose_term_is_almost_always_zero_is_no_rule():
    rng = np.random.default_rng(1)
    rows = []
    for i in range(3000):
        ns = 1 if rng.random() < 0.97 else int(rng.integers(2, 4))
        sn = 1 if ns == 1 else int(rng.random() < 0.3)
        f3 = 0 if rng.random() < 0.975 else int(rng.integers(1, 500))
        f4 = 0 if rng.random() < 0.99 else int(rng.integers(1, 500))
        rows.append([f"T{i}", 1950 + i % 70, ns, sn, int(rng.integers(1, 500)), int(rng.integers(0, 500)), f3, f4])
    out = scan(["om", "yr", "ns", "sn", "f1", "f2", "f3", "f4"], rows, fair=False)[1]
    assert not adds(out), [out[i]["reason"][:120] for i in adds(out)[:3]]


def test_a_real_sum_with_a_term_that_is_often_zero_still_catches_its_slip():
    # Net = New + Churned, churn 0 in a third of the months: still a rule, and a typo in it is still found
    rng = np.random.default_rng(2)
    rows = []
    for i in range(300):
        new, churned = int(rng.integers(50, 400)), 0 if rng.random() < 0.33 else -int(rng.integers(1, 40))
        rows.append([f"M{i}", new, churned, new + churned, int(rng.integers(1, 9))])
    rows[120][3] = rows[120][3] + 90
    out = scan(["Month", "New", "Churned", "Net", "Region"], rows, fair=False)[1]
    assert adds(out) == [120], [out[i]["reason"][:120] for i in adds(out)[:3]]


def test_rates_too_small_for_cents_never_make_a_product_rule():
    rng = np.random.default_rng(3)
    # most rates under 0.01, as in the real table: within a cent of any product of two of them; a few larger
    big = lambda: rng.random() < 0.03
    rows = [[f"C{i}"] + [float(f"{rng.uniform(0.02, 0.06) if big() else rng.uniform(0.0001, 0.009):.10f}") for _ in range(6)]
            + [round(float(rng.uniform(0.5, 2)), 6)] for i in range(1500)]
    cols = ["college", "attend", "attend_sat", "attend_level", "stderr_attend", "stderr_rel_apply", "stderr_rel_apply_sat", "rel_attend"]
    out = scan(cols, rows, fair=False)[1]
    assert not adds(out), [out[i]["reason"][:140] for i in adds(out)[:3]]
    assert not any(o.get("likely") for o in out), [o.get("likely") for o in out if o.get("likely")][:3]


def test_a_product_of_small_decimals_written_to_their_own_precision_still_catches_its_slip():
    # share = rate x weight, all written to 6 decimals: a rule at their own precision, and a slip in it is found
    rng = np.random.default_rng(4)
    rows = []
    for i in range(400):
        rate, weight = round(float(rng.uniform(0.001, 0.05)), 6), round(float(rng.uniform(0.5, 2)), 6)
        rows.append([f"S{i}", rate, weight, round(rate * weight, 6), int(rng.integers(1, 9))])
    rows[77][3] = round(rows[77][3] * 1.5, 6)
    out = scan(["site", "rate", "weight", "share", "group"], rows, fair=False)[1]
    assert 77 in adds(out) and len(adds(out)) == 1, [out[i]["reason"][:140] for i in adds(out)[:3]]


def test_a_whole_dollar_total_by_a_price_rounded_to_the_cent_is_within_its_rounding():
    # the gross is rounded to the dollar, the average price to the cent: the product misses the gross by up to half a
    # cent per seat plus the gross's own half dollar. One real mismatch (a gross typed with an extra 0) is still found
    rng = np.random.default_rng(5)
    rows = []
    for i in range(2000):
        seats = int(rng.integers(800, 9000))
        exact = seats * float(rng.uniform(20, 150))
        rows.append([f"W{i}", f"Show {i % 40}", int(round(exact)), round(exact / seats, 2), seats, int(rng.integers(6, 9))])
    rows[500][2] = rows[500][2] * 10
    out = scan(["week", "show", "weekly_gross", "avg_ticket_price", "seats_sold", "performances"], rows, fair=False)[1]
    assert adds(out) == [500], (len(adds(out)), [out[i]["reason"][:140] for i in adds(out)[:3]])


def test_a_short_column_never_says_likely():
    # drug use by age: 17 age groups, the oldest's real median of 364 days among 2-24 (round 37) read "likely 3.64"
    vals = [2, 4, 12, 6, 9.5, 9, 8, 6, 12, 10, 10, 10, 7, 12, 24, 24, 364]
    rows = [[f"{12 + k}", 2000 + k * 100, v, round(1 + k * 0.3, 1)] for k, v in enumerate(vals)]
    out = scan(["age", "n", "stimulant_frequency", "alcohol_use"], rows, fair=False)[1]
    assert not out[16].get("likely"), out[16]


def test_a_long_column_still_says_likely_for_its_lone_x100():
    rng = np.random.default_rng(6)
    rows = [[f"R{i}", round(float(rng.uniform(1, 6)), 2), int(rng.integers(1, 9))] for i in range(60)]
    rows[30][1], want = 364.0, 3.64
    out = scan(["id", "frequency", "group"], rows, fair=False)[1]
    assert out[30].get("likely") == {"frequency": want}, out[30]


@pytest.mark.parametrize("n, zero", [(60, 0.8), (60, 0.9), (200, 0.9)])
@pytest.mark.parametrize("on_zero", [True, False])
def test_a_sum_whose_term_is_often_zero_on_a_short_sheet_still_catches_its_slip(n, zero, on_zero):
    # AH-54 review (Council A): New + Reactivated = Net adds, Reactivated 0 in 80-90% of 60 months; 29975ea found a +7
    # slip in Net adds, try 1 lost the rule (it asked 20 rows where no term is 0)
    rng = np.random.default_rng(3)
    rows = []
    for i in range(n):
        a = int(rng.integers(10, 500))
        b = 0 if rng.random() < zero else int(rng.integers(1, 80))
        rows.append([f"Month {i}", a, b, a + b, int(rng.integers(1, 9))])
    cand = [i for i, r in enumerate(rows) if (r[2] == 0) == on_zero]
    s = cand[len(cand) // 2]
    rows[s][3] += 7
    out = scan(["Month", "New", "Reactivated", "Net adds", "Reps"], rows, fair=False)[1]
    assert adds(out) == [s], [out[i]["reason"][:120] for i in adds(out)[:3]]


def shooting(n=600, seed=11):
    """Made = Attempts x Rate, the rate rounded to 3 decimals: exact to the cent on most rows, a rounding step off on the
    rows with many attempts (a box score's FGM, FGA and FG%)."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        att = int(rng.integers(4, 30))
        made = int(rng.integers(0, att + 1))
        rows.append([f"P{i}", att, made, round(made / att, 3), int(rng.integers(0, 12))])
    return rows


def rounding_misses(rows):
    return [i for i, r in enumerate(rows) if 0.011 < abs(r[2] - r[1] * r[3]) <= 0.5 + 0.0005 * r[1]]


SHOTS = ["Player", "Attempts", "Made", "Rate", "Assists"]


def test_a_held_product_missed_by_a_rounding_step_on_many_rows_is_rounding_and_a_real_slip_still_is_not():
    # AH-211 episode 18: FGM = FGA x FG% held to the cent on 96% of rows; the 17 rows a rounding step off were 51 cells
    rows = shooting()
    assert len(rounding_misses(rows)) >= 3
    rows[300][2] += 2  # two made shots more than the rate says
    out = scan(SHOTS, rows, fair=False)[1]
    assert adds(out) == [300], [out[i]["reason"][:120] for i in adds(out)[:3]]


@pytest.mark.parametrize("kept", [2, 3])
def test_three_rows_a_rounding_step_off_a_held_product_are_rounding_and_two_are_each_a_slip(kept):
    rows = shooting()
    off = rounding_misses(rows)
    for i in off[kept:]:  # all but `kept` of them made exact: a rate written to more decimals there
        rows[i][3] = rows[i][2] / rows[i][1]
    out = scan(SHOTS, rows, fair=False)[1]
    assert adds(out) == (off[:2] if kept == 2 else []), (off[:kept], adds(out))


def scan_grid(cols, rows, grid):
    r = create_app().test_client().post("/scan", json={"columns": cols, "rows": rows, "strength": 5, "formulas": grid},
                                        headers={"Origin": "https://127.0.0.1:5055"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def test_a_rule_that_restates_a_formula_of_its_own_columns_never_judges_that_formulas_rows():
    # AH-211 episode 19: Days = ROUND(Qty / (Units x Per day), 0) on every row made "Qty = Per day x Days", and a liquid's
    # 5 units a dose broke it on its valid cells. The formula is the rule: its rows can never break it by a slip
    rows, grid = [], []
    for i in range(300):
        per, days, units = 1 + i % 3, [30, 60, 90][i % 3], 1
        rows.append([f"RX{i}", per * days * units, units, per, days, 5 + i % 7])
        grid.append([None, None, None, None, "=ROUND(RC[-3]/(RC[-2]*RC[-1]),0)", None])
    rows[150][1], rows[150][2] = 150, 5  # 150 units, 5 a dose, 1 a day: 30 days, valid
    rows[150][3], rows[150][4] = 1, 30
    rows[200][4], grid[200][4] = 45, None  # typed over the formula, and wrong: still found
    out = scan_grid(["Rx", "Qty", "Units", "Per day", "Days", "Refills"], rows, grid)
    assert "does not add up" not in out[150]["reason"], out[150]
    assert "does not add up" in out[200]["reason"] and out[200]["cells"] == ["Days"], out[200]


def test_a_formula_that_reads_other_columns_than_the_rule_never_excuses_its_rows():
    # Price =Cents/100 is a formula, but no restatement of Total = Qty x Price: a Total typed wrong is still found
    rows, grid = [], []
    for i in range(300):
        qty, cents = 1 + i % 9, 199 + (i * 37) % 800
        rows.append([f"L{i}", qty, cents, cents / 100, round(qty * cents / 100, 2)])
        grid.append([None, None, None, "=RC[-1]/100", None])
    rows[150][4] = round(rows[150][4] + 7, 2)
    out = scan_grid(["Line", "Qty", "Cents", "Price", "Total"], rows, grid)
    assert "does not add up" in out[150]["reason"], out[150]


def test_a_rule_that_is_exactly_its_formula_said_again_never_judges_its_rounding():
    # Days =ROUND(Qty/Per day,0), and Qty = Per day x Days held: two rows whose Qty the day count rounds (100 at 3 a day is
    # 33 days) are the formula's own rounding, never a slip in Qty or Per day
    rows, grid = [], []
    for i in range(300):
        per, days = 1 + i % 3, [30, 60, 90][i % 3]
        rows.append([f"RX{i}", per * days, per, days, 5 + i % 7])
        grid.append([None, None, None, "=ROUND(RC[-2]/RC[-1],0)", None])
    for i in (150, 153):
        rows[i][1], rows[i][2], rows[i][3] = 100, 3, 33
    out = scan_grid(["Rx", "Qty", "Per day", "Days", "Refills"], rows, grid)
    assert not any("does not add up" in r["reason"] for r in out), [r["reason"] for r in out if "does not add up" in r["reason"]]
