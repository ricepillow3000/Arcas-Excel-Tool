"""AH-177: blind round 2's three false alarms, each rebuilt as a synthetic sheet shaped like the real table: a weather
table's honest temperatures below zero were each Medium past a weird low limit of 0; a column's words for no value
("N/A", "NA", "-", "None") were counted apart, so none reached the one-note bar and each was Medium; and a column of
mixed-case codes was read as lowercase style, so "Misc" 38 times beside "misc" 207 was a card a row, auto-applied, and
"mm" was offered as a short form of "mm_prediction_random_forest"."""
import numpy as np
import pytest

from anomaly_hunter.agents.scan_agent import scan

FLAG = ("Medium", "High")


def temps(header, lone=None, n=18000):
    """Hourly readings in Fahrenheit: about 0.6% below zero, spread -1 to -39."""
    rng = np.random.default_rng(21)
    t = np.round(rng.normal(55, 22, n)).astype(int)
    rows = [[f"st{i % 12}", int(v)] for i, v in enumerate(t)]
    if lone is not None:
        rows[9000][1] = lone
    return ["station", header], rows, t


@pytest.mark.parametrize("header", ["observed_temp", "Temperature (F)", "TMIN"])
def test_honest_temperatures_below_zero_are_never_past_a_limit(header):
    cols, rows, t = temps(header)
    assert 80 <= (t < 0).sum() <= 140 and t.min() <= -30
    out = scan(cols, rows, fair=False)[1]
    bad = [(i, o["reason"]) for i, o in enumerate(out) if o["severity"] in FLAG and header in o["reason"]]
    assert not bad, bad[:3]


def test_a_lone_slip_far_below_honest_temperatures_is_still_flagged():
    cols, rows, _ = temps("observed_temp", lone=-400)
    out = scan(cols, rows, fair=False)[1]
    assert out[9000]["severity"] in FLAG and "observed_temp" in out[9000]["reason"], out[9000]
    assert [i for i, o in enumerate(out) if o["severity"] in FLAG and "observed_temp" in o["reason"]] == [9000]


def test_the_same_negatives_under_a_count_header_are_still_each_a_stray_minus():
    cols, rows, t = temps("Units sold")
    out = scan(cols, rows, fair=False)[1]
    neg = [i for i, v in enumerate(t) if v < 0]
    assert all(out[i]["severity"] in FLAG and "Units sold" in out[i]["reason"] for i in neg), [out[i] for i in neg[:2]]


@pytest.mark.parametrize("minus", [1, 4])
def test_a_few_minus_signs_under_a_header_that_can_go_below_zero_still_stand_alone(minus):
    # the 0 floor goes only where the column writes 5+ negatives: a flipped Balance among honest positive ones is a slip
    rng = np.random.default_rng(3)
    rows = [[f"a{i}", round(float(rng.uniform(500, 9000)), 2)] for i in range(600)]
    for k in range(minus):
        rows[100 + 50 * k][1] = -rows[100 + 50 * k][1]
    out = scan(["account", "Balance"], rows, fair=False)[1]
    assert all(out[100 + 50 * k]["severity"] in FLAG for k in range(minus)), [out[100 + 50 * k] for k in range(minus)]


def no_values(kind, words, n=16000, blank=0.0, seed=177):
    """A column of numbers or labels with words for no value scattered through it, and a share of its cells blank."""
    rng = np.random.default_rng(seed)
    vals = [str(round(float(x), 1)) for x in rng.normal(50, 10, n)] if kind == "number" else \
        [["Red", "Blue", "Green", "Yellow"][int(k)] for k in rng.integers(0, 4, n)]
    pos = iter(rng.permutation(n))
    for w, c in words:
        for _ in range(c):
            vals[next(pos)] = w
    for _ in range(int(blank * n)):
        vals[next(pos)] = ""
    return ["Id", "value"], [[f"r{i}", v] for i, v in enumerate(vals)]


SPELLINGS = [("N/A", 47), ("NA", 26), ("-", 6), ("None", 3)]  # 82 of 16,000: each under the bar of 80, together over it


@pytest.mark.parametrize("kind", ["number", "text"])
def test_words_for_no_value_spelt_four_ways_are_counted_together_as_one_note(kind):
    out = scan(*no_values(kind, SPELLINGS), fair=False)[1]
    assert not [o["reason"] for o in out if o["severity"] in FLAG], [o["reason"] for o in out if o["severity"] in FLAG][:3]
    note = [o["reason"] for o in out if '"N/A"' in o["reason"]]
    assert len(note) == 1 and '"N/A" or "-" (no value) in 53 of 16000 rows' in note[0], note


@pytest.mark.parametrize("kind", ["number", "text"])
def test_a_few_words_for_no_value_spelt_two_ways_are_still_each_a_slip(kind):
    out = scan(*no_values(kind, [("N/A", 4), ("-", 3)]), fair=False)[1]
    said = [o for o in out if "Placeholder" in o["reason"]]
    assert len(said) == 7 and all(o["severity"] == "Medium" for o in said), [o["reason"] for o in said]


@pytest.mark.parametrize("kind", ["number", "text"])
def test_another_spelling_of_no_value_in_a_column_already_a_fifth_empty_is_part_of_its_note(kind):
    out = scan(*no_values(kind, [("N/A", 1)], n=4000, blank=0.25), fair=False)[1]
    assert not [o["reason"] for o in out if o["severity"] in FLAG and "N/A" in o["reason"]]
    out = scan(*no_values(kind, [("NA", 3960), ("N/A", 1)], n=4000), fair=False)[1]
    assert not [o["reason"] for o in out if o["severity"] in FLAG and "N/A" in o["reason"]]


def test_a_stray_word_for_no_value_in_a_column_that_is_otherwise_filled_is_still_a_slip():
    out = scan(*no_values("text", [("N/A", 1)], n=4000, blank=0.1), fair=False)[1]
    said = [o for o in out if "N/A" in o["reason"]]
    assert len(said) == 1 and said[0]["severity"] == "Medium", [o["reason"] for o in said]


def codes(labels, seed=2):
    rng = np.random.default_rng(seed)
    cells = [w for w, c in labels for _ in range(c)]
    rng.shuffle(cells)
    return ["Id", "genus", "count"], [[f"s{i}", w, int(rng.integers(1, 50))] for i, w in enumerate(cells)]


def test_a_second_spelling_in_a_column_of_mixed_case_codes_is_one_note_never_a_card_a_row():
    # 6 labels of 10 start lowercase: no style, so "Misc" 38 times is the source's own second spelling of "misc"
    labels = [("misc", 207), ("Misc", 38), ("domus", 90), ("aim82NM", 60), ("alpha", 70), ("gamma", 80), ("zeta", 50),
              ("New", 75), ("MusCal", 65), ("Beta", 55)]
    cols, rows = codes(labels)
    out = scan(cols, rows, fair=False)[1]
    said = [o for o in out if '"Misc"' in o["reason"]]
    assert len(said) == 1 and said[0]["severity"] == "Low" and '"Misc" 38 times' in said[0]["reason"], [o["reason"] for o in said[:2]]
    assert not any(o.get("likely") or o.get("exact") for o in out)


def test_a_capitalised_slip_in_a_lowercase_column_still_gets_its_card():
    labels = [("paris", 300), ("london", 250), ("berlin", 200), ("madrid", 150), ("rome", 100), ("Paris", 6)]
    cols, rows = codes(labels)
    out = scan(cols, rows, fair=False)[1]
    hit = [i for i, r in enumerate(rows) if r[1] == "Paris"]
    assert all(out[i]["severity"] == "Medium" and out[i]["likely"] == {"genus": "paris"} for i in hit), [out[i] for i in hit[:2]]


def test_a_whole_word_of_a_label_joined_by_underscores_is_no_short_form():
    labels = [("mm_prediction_random_forest", 100), ("mm", 39), ("baseline", 120), ("ensemble_mean", 90)]
    out = scan(*codes(labels), fair=False)[1]
    assert not any("short form" in o["reason"] for o in out), [o["reason"] for o in out if "short form" in o["reason"]][:2]


def test_a_contraction_is_still_a_short_form():
    labels = [("Management", 100), ("Sales", 120), ("Finance", 90), ("Mgmt", 2)]
    cols, rows = codes(labels)
    out = scan(cols, rows, fair=False)[1]
    hit = [i for i, r in enumerate(rows) if r[1] == "Mgmt"]
    assert all('"Mgmt" looks like a short form of "Management"' in out[i]["reason"] for i in hit), [out[i] for i in hit]
