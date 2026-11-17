"""AH-176 (blind round 2): a still_alive of deceased 166, alive 32 and Pending 2 was three labels, and a real gap by sex
(male alive 26% vs female 6%) went unsaid; "gender Female: 57% missing yearOfDeath vs 33% for Male - a real gap" was
said of artists still alive; "participant_age under 30: 1.6% rows flagged for a value vs 0.5%" counted the impossible
ages that put those rows in the youngest band; "Transnational youth meetings" against national ones was read as a result.
Synthetic sheets, exact or planted by seed."""
import numpy as np
import pytest

from anomaly_hunter.agents import scan_agent
from anomaly_hunter.engine import fairness
from anomaly_hunter.engine.load import load_from_records


def report_of(cols, rows, group="Sex"):
    return [t for t in scan_agent.scan(cols, rows)[-1]["tests"] if t["column"] == group]


def test_two_pending_answers_beside_deceased_and_alive_are_left_out_and_the_gap_is_said():
    rows = []
    for i in range(200):
        sex, k = "MF"[i % 2], i // 2  # 100 of each
        alive = k < (26 if sex == "M" else 6)
        rows.append([f"A{i:04d}", sex, 20 + i % 50, "Pending" if k == 99 else "alive" if alive else "deceased"])
    found = [t for t in report_of(["Person ID", "Sex", "Age", "still_alive"], rows) if t["measure"] == "outcome"]
    assert len(found) == 1 and found[0]["verdict"] == "gap", [t["text"] for t in found]
    assert found[0]["text"].endswith("; too few to compare: still_alive Pending (2 rows)"), found[0]["text"]


def artists(col, seed=1):
    """400 artists, gender Female/Male alternating, `col` blank for 57% of women and 33% of men."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(400):
        g = ("Female", "Male")[i % 2]
        blank = rng.random() < (0.57 if g == "Female" else 0.33)
        rows.append([f"Artist {i}", g, int(rng.integers(1850, 1990)), None if blank else int(rng.integers(1900, 2020))])
    return ["artist", "gender", "yearOfBirth", col], rows


@pytest.mark.parametrize("col", ["yearOfDeath", "date_of_death", "Died", "deathYear", "DOD", "Deceased date"])
def test_a_blank_death_date_is_a_person_alive_never_a_missing_value(col):
    found = [t for t in report_of(*artists(col), group="gender") if t["test"] == f"missing {col}"]
    assert not found, [t["text"] for t in found]


@pytest.mark.parametrize("col", ["Income", "Height"])
def test_the_same_blanks_in_a_column_that_names_no_death_are_still_measured(col):
    found = [t for t in report_of(*artists(col), group="gender") if t["test"] == f"missing {col}"]
    assert [t["verdict"] for t in found] == ["gap"], [t["text"] for t in found]


def flag_rate(group_cells, other_cells):
    """600 people aged 18-77 (under 30: 120 rows): rows flagged on the cells given, the Age comparison's flag rate."""
    cols = ["ID", "Sex", "Age", "Score"]
    rows = [[f"P{i:04d}", "FM"[i % 2], 18 + i % 60, 500 + i % 97] for i in range(600)]
    df, types, _ = load_from_records(cols, rows)
    flags = [{"severity": None} for _ in rows]
    for i in group_cells:
        flags[i] = {"severity": "Medium", "cells": ["Age"]}
    for i in other_cells:
        flags[i] = {"severity": "Medium", "cells": ["Score"]}
    tests = fairness.report(df, types, flags)["tests"]
    return [t for t in tests if t["column"] == "Age" and t["measure"] == "flag"], [t for t in tests if t["column"] == "Sex" and t["measure"] == "flag"]


YOUNG = [i for i in range(600) if 18 + i % 60 < 30][:24]  # 24 of the 120 under 30
SPREAD = list(range(3, 600, 7))  # 86 rows through every age alike


def test_a_flag_on_the_group_column_itself_is_never_that_groups_flag_rate():
    by_age, by_sex = flag_rate(YOUNG, SPREAD)
    assert [t["verdict"] for t in by_age] == ["even"], [t["text"] for t in by_age]
    # ...but by sex those rows are flagged for a value as any other
    assert round(sum(t["groups"][g][0] * t["groups"][g][1] for t in by_sex for g in t["groups"])) == len(set(YOUNG) | set(SPREAD))


def test_flags_on_another_column_in_one_group_are_still_its_gap():
    by_age, _ = flag_rate([], YOUNG + SPREAD)
    assert [t["verdict"] for t in by_age] == ["gap"] and "under 30" in by_age[0]["text"], [t["text"] for t in by_age]


@pytest.mark.parametrize("labels", [("National", "Transnational"), ("National", "International")])
def test_national_against_transnational_or_international_is_where_never_a_result(labels):
    rng = np.random.default_rng(5)
    rows = [[f"P{i:04d}", "FM"[i % 2], 20 + i % 40,
             labels[1] if rng.random() < (0.35 if i % 2 else 0.1) else labels[0],
             "Won" if rng.random() < (0.35 if i % 2 else 0.1) else "Lost"] for i in range(600)]
    found = [t["test"] for t in report_of(["ID", "Sex", "Age", "activity_mob", "Result"], rows) if t["measure"] == "outcome"]
    assert found == ["Result Won rate"], found


def climbers(pending, n=20_000, seed=176):
    """n climbers, sex F/M alternating, success TRUE for 30% of women and 45% of men, "Pending" on `pending` rows."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        sex = "FM"[i % 2]
        success = "TRUE" if rng.random() < (0.30 if sex == "F" else 0.45) else "FALSE"
        rows.append([f"C{i:05d}", sex, int(rng.integers(20, 70)), "Pending" if i % 100 == 3 and i // 100 < pending else success])
    return ["Climber ID", "Sex", "Age", "success"], rows


def test_a_third_label_on_under_1_percent_of_the_answers_is_left_out_however_many_rows_it_has():
    # blind round 3: Pending on 198 of ~19,000 climbers (1.0%), each label past MIN_GROUP, so AH-176's rule alone made the
    # column no outcome and a real gap by sex went unsaid (AH-176 fix round 1: AH-172's 1% rule kept beside it)
    found = [t for t in report_of(*climbers(190)) if t["measure"] == "outcome"]
    assert len(found) == 1 and found[0]["verdict"] == "gap", [t["text"] for t in found]
    assert found[0]["text"].endswith("; too few to compare: success Pending (190 rows)"), found[0]["text"]


def test_a_third_label_on_exactly_1_percent_of_the_answers_and_a_group_of_its_own_makes_no_outcome():
    assert not [t for t in report_of(*climbers(200)) if t["measure"] == "outcome"]
