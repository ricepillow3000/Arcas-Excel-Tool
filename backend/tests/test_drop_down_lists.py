"""AH-213: a value outside its cell's drop-down list. Excel itself knows which cells break their data validation
(Range.getDataValidationInvalidCellsOrNullObject, ExcelApi 1.9); the pane sends them with /scan as `off_list`, [row,
column] of the table, and the engine says each one, its value as typed, never a fix ("Reciept" among Receipt, Issue
and Return; 5 planted on the complex bench's tuning episodes, all missed). Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Date", "Type", "Qty"]
ROWS = [[f"2026-01-{1 + k % 28:02d}", ("Receipt", "Issue", "Return")[k % 3], 5 + k % 7] for k in range(40)]


def post(invalid, rows=ROWS):
    return APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5, "off_list": invalid},
                    headers={"Origin": "https://127.0.0.1:5055"})


def test_a_cell_excel_says_is_off_its_list_is_flagged_on_that_cell_with_its_value_as_typed():
    rows = [list(r) for r in ROWS]
    rows[7][1], rows[12][2] = "Lost", 0.5
    out = post([[7, 1], [12, 2]], rows).get_json()["rows"]
    assert out[7]["severity"] == "Medium" and out[7]["cells"] == ["Type"]
    assert 'Type "Lost" is not one of the choices its drop-down list allows' in out[7]["reason"]
    assert ["validation", "Type"] in out[7]["kinds"] and not out[7]["likely"] and not out[7]["maybe"]
    assert "Qty 0.5 is not one of the choices its drop-down list allows" in out[12]["reason"]


def test_without_invalid_cells_nothing_is_said_of_a_list_and_a_blank_cell_never_is():
    rows = [list(r) for r in ROWS]
    rows[7][1] = ""
    out = post(None, rows).get_json()["rows"]
    assert not any("drop-down" in r["reason"] for r in out)
    out = post([[7, 1]], rows).get_json()["rows"]
    assert not any("drop-down" in r["reason"] for r in out)


def test_invalid_cells_are_checked_before_any_work_at_their_limit():
    many = [[k % len(ROWS), k % 3] for k in range(1000)]  # server.INVALID
    assert post(many).status_code == 200
    assert post([*many, [0, 0]]).status_code == 400
    for bad in ([[40, 0]], [[0, 3]], [[-1, 0]], [[0, True]], [[0.0, 1]], [[0]], [[0, 1, 2]], [["0", 1]], {"0": 1}, "A1",
                [None]):
        r = post(bad)
        assert r.status_code == 400 and "'off_list'" in r.get_json()["error"], bad
    assert post([[39, 2], [0, 0]]).status_code == 200
