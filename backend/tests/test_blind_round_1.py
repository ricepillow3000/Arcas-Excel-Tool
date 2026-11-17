"""AH-174: blind round 1's misses and its one harmful card, each rebuilt as a synthetic sheet shaped like the real table:
labels with punctuation ("East Aisa & Pacific", "ulrta_low_sulfur", "Irish Poundd (Punt)") never had their spelling
judged; a total beside a part blank on 99.9% of rows was never tried without it; a rubella rate's honest 1008.51 was
offered "likely 1.00851"; 19-22 digit identifiers got limits and were quoted as 7.27614899769986e+21; and a code
column's honest 0s (7 of 1,173) were Medium past a weird low limit of 0.4."""
import numpy as np
import pytest

from anomaly_hunter.agents.scan_agent import scan
from anomaly_hunter.engine.detectors import say


def column(usual, odd, others, n=40):
    labels = [usual] * n + [o for o in others for _ in range(25)] + [odd]
    return [[f"r{i}", w, 10 + i % 7] for i, w in enumerate(labels)]


@pytest.mark.parametrize("col, usual, odd, others", [
    ("region", "East Asia & Pacific", "East Aisa & Pacific", ["Europe & Central Asia", "South Asia", "Sub-Saharan Africa"]),
    ("grade", "ultra_low_sulfur", "ulrta_low_sulfur", ["low_sulfur", "high_sulfur", "regular"]),
    ("currency", "Irish Pound (Punt)", "Irish Poundd (Punt)", ["Euro", "US Dollar", "Swiss Franc"]),
    ("remote_work", "Hybrid (some remote, some in-person)", "Hybrid (some rremote, some in-person)", ["Fully remote", "Fully in-person"]),
])
def test_a_slip_in_one_word_of_a_label_with_punctuation_is_worth_a_check(col, usual, odd, others):
    out = scan(["Id", col, "Units"], column(usual, odd, others), fair=False)[1]
    assert f'{col} "{odd}" looks like a misspelling of "{usual}"' in out[-1]["reason"], out[-1]
    assert out[-1]["maybe"] == {col: usual} and not any("misspelling" in o["reason"] for o in out[:-1])


@pytest.mark.parametrize("rare, usual", [
    ("Room 1", "Room 11"), ("Q1-2024", "Q1-2025"), ("Unit (2B)", "Unit (2C)"),   # a digit or a letter of a code is no slip
    ("Russia-SW", "Russia-SE"), ("Form (A)", "Form (B)"),
    ("Plan (Gild)", "Plan (Gold)"),         # a wrong letter in a 4-letter word, as on its own (Iran/Iraq)
    ("Size (Wayy)", "Size (Way)"),          # a letter typed twice in a 3-letter word
    ("East Asia, Pacific", "East Asia & Pacific"),   # the words agree, only the separators differ: no misspelling
    ("Nord & Paciffic", "East & Pacific"),  # two words differ
])
def test_a_label_with_punctuation_whose_differing_part_is_no_slip_is_left_alone(rare, usual):
    out = scan(["Id", "Label", "Units"], column(usual, rare, ["Other label", "Something else"]), fair=False)[1]
    assert not any("misspelling" in o["reason"] for o in out), (rare, usual, out[-1]["reason"])


def parts_sheet(part7_in_total, slip=None, n=2000):
    """p1..p6 add up to total; p7 is blank on all but 2 rows (0.1%), where it is, or is not, part of the total."""
    rng = np.random.default_rng(7)
    rows = []
    for i in range(n):
        p = [int(v) for v in rng.integers(0, 6, 6)]
        p7 = int(rng.integers(1, 9)) if i in (100, 1500) else None
        total = sum(p) + (p7 if part7_in_total and p7 else 0)
        rows.append([f"r{i}", *p, "" if p7 is None else p7, total])
    if slip is not None:
        rows[slip][-1] = 51 if rows[slip][-1] == 15 else rows[slip][-1] + 36
    return ["Id", "p1", "p2", "p3", "p4", "p5", "p6", "p7", "total"], rows


@pytest.mark.parametrize("part7_in_total", [True, False])
def test_a_total_beside_a_part_blank_on_almost_every_row_is_still_judged(part7_in_total):
    cols, rows = parts_sheet(part7_in_total, slip=700)
    out = scan(cols, rows, fair=False)[1]
    assert "total" in out[700]["reason"] and "does not add up" in out[700]["reason"], out[700]
    assert [i for i, o in enumerate(out) if "does not add up" in o["reason"]] == [700]


@pytest.mark.parametrize("part7_in_total", [True, False])
def test_an_honest_total_beside_a_mostly_blank_part_stays_quiet(part7_in_total):
    out = scan(*parts_sheet(part7_in_total), fair=False)[1]
    assert not any("does not add up" in o["reason"] for o in out)


def rate_column(top):
    """A disease rate per million, written to 2 decimals: half the country-years 0, the rest log-normal around 1, a few
    epidemic years up to ~210, and one more value."""
    rng = np.random.default_rng(11)
    v = np.where(rng.random(2400) < 0.53, 0.0, np.round(np.exp(rng.normal(0, 1.4, 2400)), 2))
    v = np.minimum(v, 75)
    v[[50, 400, 900, 1300, 1800, 2200]] = [94.69, 141.34, 154.16, 174.37, 203.03, 211.85]
    v[1659] = top
    return [[f"c{i % 190}", 2000 + i // 190, float(x)] for i, x in enumerate(v)]


def test_an_honest_epidemic_rate_written_like_its_column_is_never_a_likely_typo():
    # Poland's rubella rate in 2013, 1008.51 per million: "likely 1.00851", a value written to 5 decimals in a column
    # written to 2, a card that would have rewritten an honest epidemic
    out = scan(["country", "year", "rubella_rate"], rate_column(1008.51), fair=False)[1]
    assert "rubella_rate" not in (out[1659].get("likely") or {}), out[1659]
    assert "likely" not in out[1659]["reason"], out[1659]["reason"]


def test_a_real_x1000_slip_in_the_same_column_is_still_likely():
    out = scan(["country", "year", "rubella_rate"], rate_column(1250.0), fair=False)[1]
    assert out[1659]["likely"] == {"rubella_rate": 1.25}, out[1659]


def ids_sheet(digits):
    """A prize list: each laureate's VIAF number (8-9 digits, and longer for newer records), repeated once per prize."""
    rng = np.random.default_rng(5)
    long = lambda: str(int(rng.integers(1, 10))) + "".join(str(d) for d in rng.integers(0, 10, digits - 2)) + str(int(rng.integers(1, 10)))
    people = [str(int(rng.integers(10 ** 7, 10 ** 9))) for _ in range(600)] + [long() for _ in range(40)]
    who = [people[int(rng.integers(0, len(people)))] for _ in range(950)]
    return [[f"p{i}", 1990 + i % 30, w] for i, w in enumerate(who)]


@pytest.mark.parametrize("digits", [16, 22])
def test_a_column_of_identifiers_too_long_for_a_number_is_an_id_and_gets_no_limits(digits):
    _, out, suggested, *_ = scan(["prize_id", "prize_year", "viaf"], ids_sheet(digits), fair=False)
    assert "viaf" not in suggested
    assert not any("viaf" in o["reason"] or "e+" in o["reason"] for o in out)


def test_a_column_of_big_amounts_still_gets_its_limits():
    # 16 digits of which 15 are significant (an amount in a small currency) is a number, not an identifier
    rng = np.random.default_rng(6)
    rows = [[f"c{i}", 2000 + i % 20, f"{int(rng.integers(10 ** 13, 10 ** 14))}10"] for i in range(300)]
    rows[40][2] = str(10 ** 18 * 3)
    _, out, suggested, *_ = scan(["country", "year", "gdp_lcu"], rows, fair=False)
    assert "gdp_lcu" in suggested and "gdp_lcu" in out[40]["reason"], out[40]
    assert "this is 3000000000000000000" in out[40]["reason"], out[40]["reason"]   # the cell as typed, never 3e+18


@pytest.mark.parametrize("v, said", [(20892375800000000.0, "20892375800000000"), (1e-07, "0.0000001"), (1234567.89, "1234567.89"),
                                     (-0.013338153250515461, "-0.0133381532505155"), (3.0, "3")])
def test_a_number_is_quoted_without_e_notation(v, said):
    assert say(v) == said


def code_rows(zeros):
    labels = [1] * 1081 + [2] * 84 + [0] * zeros + [3]
    return [[f"s{i}", f"Song {i}", v] for i, v in enumerate(labels)]


def test_a_code_the_column_writes_5_times_or_more_is_never_past_its_limits():
    # producer_male: 1 x1081, 2 x84, 0 x7, 3 x1. The 0s were "weird limit is 0.4; this is 0", 7 Medium rows
    for zeros in (5, 7):
        out = scan(["song_id", "title", "producer_male"], code_rows(zeros), fair=False)[1]
        assert not any("producer_male" in o["reason"] and "limit" in o["reason"] for o in out[1165:-1]), [o["reason"] for o in out[1165:-1]]


def test_a_value_a_code_column_writes_4_times_or_fewer_is_still_past_its_limits():
    out = scan(["song_id", "title", "producer_male"], code_rows(4), fair=False)[1]
    assert all("producer_male weird limit" in o["reason"] for o in out[1165:-1]), [o["reason"] for o in out[1165:-1]]
