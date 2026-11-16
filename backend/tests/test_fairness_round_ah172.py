"""AH-172 (blind round 1): an outcome's labels are read the way a group's are. A Yes/No answer with "NA" 542 times was
three labels, so a real gap by gender (Female Yes 37% vs 59%) went unsaid; a winner of Red 3966, Blue 3203, Draw 5 and
No Contest 3 was four. A word that says no value is missing, and stray labels (AH-176: each under 20 rows, together under 5%) are left out
and named, never a reason to drop the outcome. Red/Blue (which side won) and Summer/Winter (when) are no result.
Synthetic sheets, planted by seed."""
import numpy as np

from anomaly_hunter.agents import scan_agent


def sheet(n, rates, seed, other=None, extra=None):
    """n people, Sex F/M alternating, Answer Yes/No with rates[sex]; other: (label, share) written instead of an answer."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        sex = "FM"[i % 2]
        answer = "Yes" if rng.random() < rates[sex] else "No"
        if other and rng.random() < other[1]:
            answer = other[0]
        rows.append([f"P{i:05d}", sex, int(rng.integers(20, 70)), answer] + (extra(i, rng) if extra else []))
    return ["Person ID", "Sex", "Age", "Answer"], rows


def outcomes(cols, rows, column):
    """The outcome tests of `column` by Sex."""
    return [t for t in scan_agent.scan(cols, rows)[-1]["tests"]
            if t["measure"] == "outcome" and t["column"] == "Sex" and t["test"].startswith(f"{column} ")]


def test_a_yes_no_answer_with_na_for_no_value_is_still_an_outcome_and_its_gap_is_said():
    cols, rows = sheet(400, {"F": 0.35, "M": 0.6}, 172, other=("NA", 0.15))
    found = outcomes(cols, rows, "Answer")
    assert len(found) == 1, [t["text"] for t in found]
    t = found[0]
    assert t["verdict"] == "gap" and set(t["groups"]) == {"F", "M"} and "NA" not in t["test"], t["text"]
    # ...and with no gap planted it is read, and even
    cols, rows = sheet(400, {"F": 0.45, "M": 0.45}, 173, other=("NA", 0.15))
    found = outcomes(cols, rows, "Answer")
    assert len(found) == 1 and found[0]["verdict"] == "even", [t["text"] for t in found]


def test_a_third_label_of_a_few_rows_is_left_out_and_named_never_the_end_of_the_outcome():
    cols, rows = sheet(400, {"F": 0.35, "M": 0.6}, 174)
    for i in (5, 77, 301):
        rows[i][3] = "Maybe"
    found = outcomes(cols, rows, "Answer")
    assert len(found) == 1 and found[0]["verdict"] == "gap", [t["text"] for t in found]
    assert found[0]["text"].endswith("; too few to compare: Answer Maybe (3 rows)"), found[0]["text"]
    assert sum(found[0]["groups"][g][0] for g in "FM") == 397  # compared on the Yes and No rows alone


def test_a_third_label_written_often_still_makes_the_column_no_yes_no_outcome():
    cols, rows = sheet(400, {"F": 0.35, "M": 0.6}, 175, other=("Maybe", 0.3))
    assert not outcomes(cols, rows, "Answer")


def strays(sizes, seed=176):
    """1,200 people (5% = 60 answers), Answer Yes/No with a gap by sex, and extra labels of these sizes."""
    cols, rows = sheet(1200, {"F": 0.35, "M": 0.6}, seed)
    i = 0
    for k, n in enumerate(sizes):
        for _ in range(n):
            rows[i][3] = f"Other {'ABCD'[k]}"  # never one slip from another label
            i += 7
    return cols, rows


def test_extra_labels_each_under_20_rows_and_under_5_percent_together_are_left_out():
    # AH-176: 3 x 19 = 57 of 1,200 (4.75%): each too small to be a group, together too few to be a third answer
    found = outcomes(*strays((19, 19, 19)), "Answer")
    assert len(found) == 1 and found[0]["verdict"] == "gap", [t["text"] for t in found]
    assert sum(found[0]["groups"][g][0] for g in "FM") == 1200 - 57


def test_an_extra_label_of_20_rows_or_extra_labels_of_5_percent_together_make_no_yes_no_outcome():
    assert not outcomes(*strays((19, 19, 20)), "Answer")  # 58 rows (4.8%), but one label is a group of its own
    assert not outcomes(*strays((19, 19, 19, 3)), "Answer")  # each under 20, together 60 of 1,200: exactly 5%


def test_which_side_won_or_a_season_is_never_an_outcome_but_won_or_lost_is():
    side = lambda i, rng: ["Red" if rng.random() < (0.3 if i % 2 else 0.7) else "Blue",
                           "Summer" if rng.random() < (0.3 if i % 2 else 0.7) else "Winter",
                           "Won" if rng.random() < (0.3 if i % 2 else 0.7) else "Lost"]
    cols, rows = sheet(400, {"F": 0.5, "M": 0.5}, 177, extra=side)
    cols = cols + ["Winner", "Season", "Result"]
    assert not outcomes(cols, rows, "Winner") and not outcomes(cols, rows, "Season")
    assert [t["verdict"] for t in outcomes(cols, rows, "Result")] == ["gap"]
