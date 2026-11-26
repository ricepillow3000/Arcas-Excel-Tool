"""AH-231: Ask AI's fix is checked by the engine before it is shown. The proposed value goes into the row and the
engine's own checks judge it again (no AI); a value they still flag is not offered, and the card says to fix it by hand."""
import random

from anomaly_hunter.ai import client
from anomaly_hunter.server import create_app

COLS = ["Item", "Qty", "Rate", "Amount"]


def sheet():
    random.seed(1)
    rows = []
    for i in range(40):
        q, r = random.randint(5, 900), random.choice([2, 3, 5, 7.5, 10])
        rows.append([f"P{i}", q, r, round(q * r, 2)])
    rows[10] = ["P10", 7000, 5, 3500]  # Qty typed 7000 for 700: Amount = Qty x Rate says so
    return rows


def regions():
    rows = [r + [["East", "West", "North", "South"][i % 4]] for i, r in enumerate(sheet())]
    rows[20][4] = "Esat"  # a misspelling, on a row also flagged (Low) for its Amount 5902.5 among whole numbers
    rows[21][4] = "Wset"
    return rows


def ask(monkeypatch, changes, rows=None, formulas=None, row=10):
    monkeypatch.setattr(client, "api_key_configured", lambda: True)
    fake = {"explanation": "Qty should be smaller.", "changes": changes}
    monkeypatch.setattr(client, "suggest_fix", lambda *a, **k: fake)
    rows = rows or sheet()
    body = {"columns": COLS + ["Region"] * (len(rows[0]) > 4), "rows": rows, "row_index": row, "start_row": 0, "start_col": 0,
            "reason": "Amount 3500 does not add up: Qty x Rate = 35000", "formulas": formulas}
    r = create_app().test_client().post("/fix", json=body)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_an_ai_value_that_still_breaks_the_rows_arithmetic_is_not_offered(monkeypatch):
    out = ask(monkeypatch, [{"cell": "B12", "new": "6000"}])
    assert out["changes"] == []
    assert "Left out B12" in out["explanation"] and "fix it by hand" in out["explanation"]


def test_an_ai_value_that_fixes_the_row_still_goes_through(monkeypatch):
    out = ask(monkeypatch, [{"cell": "B12", "new": "700"}])
    assert out == {"explanation": "Qty should be smaller.", "changes": [{"cell": "B12", "new": "700"}]}


def test_an_ai_value_no_check_can_judge_goes_through_as_today(monkeypatch):
    # an Item label and a formula: no check of the engine's reads them, so they are offered as before
    for change in ({"cell": "A12", "new": "P10b"}, {"cell": "B12", "new": "=D12/C12"}):
        out = ask(monkeypatch, [change])
        assert out["changes"] == [change], change


def test_a_row_with_a_formula_is_not_judged_on_its_old_values(monkeypatch):
    # Amount =B12*C12 still holds 35000 in what the pane sent: Excel works it out again after the write, the engine
    # can't, so a right Qty would look wrong beside the stale total. Not judged, offered as today
    rows = sheet()
    rows[10] = ["P10", 7000, 5, 35000]
    out = ask(monkeypatch, [{"cell": "B12", "new": "700"}], rows, ["P10", 7000, 5, "=B12*C12"])
    assert out["changes"] == [{"cell": "B12", "new": "700"}]


def test_a_text_value_the_spelling_check_still_flags_is_not_offered(monkeypatch):
    out = ask(monkeypatch, [{"cell": "E23", "new": "Eats"}], regions(), row=21)
    assert out["changes"] == [] and "Left out E23" in out["explanation"]


def test_a_right_value_goes_through_on_a_row_still_flagged_for_another_cell(monkeypatch):
    # row 20 stays flagged for its Amount; the AI's Region is no longer named, so it is offered
    out = ask(monkeypatch, [{"cell": "E22", "new": "East"}], regions(), row=20)
    assert out["changes"] == [{"cell": "E22", "new": "East"}]


def test_a_number_written_the_way_the_pcs_own_excel_reads_it_is_not_judged_as_text(monkeypatch):
    # "700,0" is 700 where the comma is the decimal mark: Excel reads it, the engine can't know the PC's settings
    out = ask(monkeypatch, [{"cell": "B12", "new": "700,0"}])
    assert out["changes"] == [{"cell": "B12", "new": "700,0"}]
