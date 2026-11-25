"""AH-205 (John, 2026-11-19: "learn really fast so the tool can fully help the user in one session"): a Dismiss teaches
the sheet at once, and "Stop checking ..." mutes one kind of check in one column. The pane sends what the sheet learned
with each /scan (`learned`); the engine drops a reason it mutes before severity is decided, and says each reason's kind
(`kinds`) so the pane can name it."""
import pytest
from anomaly_hunter.engine.pipeline import KINDS, ONE_CELL
from anomaly_hunter.server import create_app

LEARNED, LEARNED_TEXT = 500, 200  # written out: a mutant of server.LEARNED must not move the test with it

GLASSES = ["Cocktail glass", "Highball glass", "Old-fashioned glass"]


def sheet(variants=(5, 40, 77, 120, 160)):
    """200 drinks: Highball Glass typed with a capital on `variants` rows, Units 7777 on row 30, a blank Units on row
    90, a Total that is not Qty x Price on row 100."""
    columns = ["Drink", "Glass", "Units", "Qty", "Price", "Total"]
    rows = []
    for i in range(200):
        q, p = 1 + (i * 5) % 7, 2.5 + (i % 4)
        rows.append([f"Drink {i % 40}", GLASSES[i % 3], 40 + (i * 7) % 23, q, p, round(q * p, 2)])
    for i in variants:
        rows[i][1] = "Highball Glass"
    rows[30][2], rows[90][2], rows[100][5] = 7777, "", 1234.5
    return columns, rows


def scan(learned=None, variants=(5, 40, 77, 120, 160)):
    columns, rows = sheet(variants)
    body = {"columns": columns, "rows": rows, **({"learned": learned} if learned is not None else {})}
    r = create_app().test_client().post("/scan", json=body)
    assert r.status_code == 200, r.get_json()
    return {i: row for i, row in enumerate(r.get_json()["rows"]) if row["severity"] in ("High", "Medium", "Low")}


def test_each_flagged_row_says_the_kind_of_check_behind_each_reason_and_its_column():
    flagged = scan()
    assert flagged[5]["kinds"] == [["spelling", "Glass"]]
    assert flagged[30]["kinds"] == [["limits", "Units"]]
    assert flagged[90]["kinds"] == [["blank", "Units"]]
    assert ["sum", "Total"] in flagged[100]["kinds"]
    assert {k for row in flagged.values() for k, _ in row["kinds"]} <= set(KINDS)


@pytest.mark.parametrize("variants", [(5, 40, 77, 120, 160), (5, 40)])  # one note for the column; each a slip
def test_a_value_dismissed_in_a_column_is_never_flagged_again_in_that_column_and_nothing_else_moves(variants):
    before = scan(variants=variants)
    assert any("Highball Glass" in before[i]["reason"] for i in variants if i in before)
    after = scan({"accept": [["Glass", "Highball Glass"]]}, variants)
    assert not any(i in after for i in variants), {i: after[i]["reason"] for i in variants if i in after}
    assert {i: r for i, r in before.items() if i not in variants} == after


def test_an_accepted_value_is_matched_as_the_pane_writes_a_number_and_only_in_its_own_column():
    assert 30 not in scan({"accept": [["Units", "7777"]]})
    assert 30 not in scan({"accept": [["Units", "7777.0"]]})  # one value however it is written
    assert 30 in scan({"accept": [["Qty", "7777"], ["Units", "7776"]]})  # another column, another value: still flagged


def test_a_stopped_check_mutes_that_kind_in_that_column_and_no_other():
    flagged = scan({"ignore": [["limits", "Units"]]})
    assert 30 not in flagged  # Units 7777 was its only reason: the row is clean
    assert flagged[90]["kinds"] == [["blank", "Units"]]  # another kind in Units still shows
    assert ["limits", "Total"] in flagged[100]["kinds"]  # the same kind in another column too
    assert scan({"ignore": [["spelling", "Units"]]}) == scan()  # a kind the column never had changes nothing


def test_accepting_a_value_never_silences_a_check_of_the_rows_arithmetic():
    flagged = scan({"accept": [["Total", "1234.5"]]})
    assert ["sum", "Total"] in flagged[100]["kinds"] and "does not add up" in flagged[100]["reason"]
    assert ["limits", "Total"] not in flagged[100]["kinds"]  # its value alone is accepted
    assert not {"sum", "order", "date_order", "record", "balance", "duplicate", "formula", "blank", "key"} & ONE_CELL
    assert scan({"ignore": [["sum", "Total"]]})[100]["kinds"] == [["limits", "Total"]]  # only stopping it does


def test_a_scan_with_nothing_learned_answers_as_before():
    assert scan({"accept": [], "ignore": []}) == scan() == scan({})


HOSTILE = [
    [], "Glass", {"accept": "Glass"}, {"accept": [["Glass"]]}, {"accept": [["Glass", "a", "b"]]},
    {"accept": [["Glass", 7]]}, {"accept": [[None, "x"]]}, {"accept": None}, {"ignore": [["limitz", "Units"]]},
    {"ignore": [["__proto__", "Units"]]}, {"ignore": [[["limits"], "Units"]]}, {"ignore": [["limits", 1]]},
    {"other": []}, {"accept": [["Glass", "x" * (LEARNED_TEXT + 1)]]}, {"ignore": [["limits", "U" * (LEARNED_TEXT + 1)]]},
    {"accept": [["Glass", "x"]] * (LEARNED + 1)}, {"ignore": [["limits", "Units"]] * (LEARNED + 1)},
]


@pytest.mark.parametrize("learned", HOSTILE)
def test_a_learned_list_of_the_wrong_shape_or_too_long_is_a_clear_400(learned):
    columns, rows = sheet()
    r = create_app().test_client().post("/scan", json={"columns": columns, "rows": rows, "learned": learned})
    assert r.status_code == 400 and "learned" in r.get_json()["error"], r.get_json()


def test_a_learned_list_at_its_very_limits_is_allowed():
    learned = {"accept": [["Glass", "x" * LEARNED_TEXT]] * (LEARNED - 1) + [["Glass", "Highball Glass"]],
               "ignore": [["limits", "U" * LEARNED_TEXT]] * (LEARNED - 1) + [["limits", "Units"]]}
    assert len(learned["accept"]) == len(learned["ignore"]) == LEARNED
    flagged = scan(learned)
    assert 30 not in flagged and 5 not in flagged and 90 in flagged


def test_every_kind_the_engine_names_may_be_stopped():
    flagged = scan({"ignore": [[k, "Units"] for k in KINDS]})
    assert 30 not in flagged and 90 not in flagged and 100 in flagged


def test_a_row_the_user_dismissed_keeps_its_own_reasons_and_what_it_taught_is_for_the_other_rows():
    """It is listed as the user left it (Dismissed, its card still opens, Power BI's Status Dismissed)."""
    columns, rows = sheet()
    decisions = [None] * len(rows)
    decisions[5] = decisions[30] = "dismissed"
    r = create_app().test_client().post("/scan", json={"columns": columns, "rows": rows, "decisions": decisions, "learned": {
        "accept": [["Glass", "Highball Glass"], ["Units", "7777"]], "ignore": [["spelling", "Glass"]]}})
    flagged = {i for i, row in enumerate(r.get_json()["rows"]) if row["severity"] in ("High", "Medium", "Low")}
    assert {5, 30} <= flagged and not {40, 77, 120, 160} & flagged



def test_a_user_who_dismisses_every_flag_still_has_new_mistakes_caught():
    # AH-215 (the ML engineer, John 2026-11-25: "if people dismiss flags they don't want to deal with, the tool learns to
    # stop flagging real errors"): a Dismiss teaches only the exact value in its column, and never a sum, an order, a
    # record, a formula, a duplicate or a blank (ONE_CELL), so a user who dismisses every flag on the sheet still sees
    # the next slip of each kind
    columns, rows = sheet()
    app = create_app().test_client()
    first = app.post("/scan", json={"columns": columns, "rows": rows}).get_json()["rows"]
    lazy = [[c, str(rows[i][columns.index(c)])] for i, r in enumerate(first) if r["severity"] in ("High", "Medium", "Low")
            for c in r["cells"]]
    assert len(lazy) >= 4
    rows[50][2], rows[150][5], rows[170][1], rows[180][2] = 6100, 999.0, "Higball glass", ""  # the next day's slips
    out = app.post("/scan", json={"columns": columns, "rows": rows, "learned": {"accept": lazy}}).get_json()["rows"]
    assert all(out[i]["severity"] in ("High", "Medium", "Low") for i in (50, 150, 170, 180)), \
        {i: out[i]["reason"] for i in (50, 150, 170, 180)}
    # ...and the very values dismissed are quiet, as AH-205 promised
    assert all(out[i]["severity"] not in ("High", "Medium") for i in (30, 100) if [columns[2], str(rows[i][2])] in lazy)
