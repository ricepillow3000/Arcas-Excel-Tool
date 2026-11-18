"""AH-198 fix round 2: a minus sign a category explains. A column that is otherwise never negative, whose negatives are
exactly the rows of one label of a text column (2+ rows, every row it labels, no other): those are the label's meaning,
never a stray minus (a carrier's volume rebate, coded REBATE, credited as -150 on the 2 invoices that carry it). A
negative its label does not account for is still a slip. Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Invoice", "Code", "Surcharge"]


def sheet(n=120):
    return [[f"INV-{1000 + i}", ["TOLL", "THC", None][i % 3], [18.5, 285.0, None][i % 3] if i % 3 < 2 else None]
            for i in range(n)]


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def flagged(out):
    return {i for i, r in enumerate(out) if r["severity"] in ("High", "Medium") and "Surcharge" in r.get("cells", [])}


def test_negatives_that_are_every_row_of_one_label_are_that_labels_meaning():
    rows = sheet()
    for i in (40, 100):
        rows[i][1:] = ["REBATE", -150.0]
    assert flagged(scan(rows)) == set()


def test_a_label_written_on_one_negative_row_alone_explains_nothing():
    rows = sheet()
    rows[40][1:] = ["REBATE", -150.0]
    assert flagged(scan(rows)) == {40}


def test_a_negative_its_label_writes_positive_elsewhere_is_still_a_stray_minus():
    rows = sheet()
    rows[40][1:] = ["REBATE", -150.0]
    rows[100][1:] = ["REBATE", -150.0]
    rows[103][1:] = ["REBATE", 150.0]
    assert flagged(scan(rows)) == {40, 100}
