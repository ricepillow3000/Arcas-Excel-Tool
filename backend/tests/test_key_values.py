"""AH-198 fix round 2: a column that holds one value for each value of a key column (a part's unit cost, an account's
name, a child's level under its parent), in all but max(1, 5%), and at most 2, of the key's 10+ groups of 2+ rows. In
a group with one other value, written once against 2+ rows that agree, that cell is wrong (a part costed 0.4 on one
line of its 12, 0.04 on the rest). The key a code: two people or two carousels share a name. Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Line", "Part", "Qty", "UnitCost"]


def lines(parts=10, each=4):
    """Each part on `each` lines of an order book, always at its own unit cost."""
    return [[f"L{p * each + k}", f"P-{100 + p}", 1 + (p + k) % 6, round(0.5 + p * 1.37, 2)] for k in range(each) for p in range(parts)]


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def keyed(out):
    return {i for i, r in enumerate(out) if "rows of Part" in r["reason"] and r["severity"] == "Medium" and "UnitCost" in r["cells"]}


def test_a_cost_its_parts_two_other_lines_never_write_is_wrong():
    rows = lines(each=3)
    rows[13][3] = round(rows[13][3] + 0.2, 2)  # P-103 on its 2nd line
    out = scan(rows)
    assert keyed(out) == {13}
    assert "other 2 rows of Part P-103, which all have 4.61 (UnitCost is one value for each Part in 9 of 10)" in out[13]["reason"]


def test_nine_parts_are_too_few_to_know_the_rule():
    rows = lines(parts=9)
    rows[12][3] = round(rows[12][3] + 0.2, 2)
    assert keyed(scan(rows)) == set()


def test_a_part_of_two_lines_has_no_agreeing_two_to_go_by():
    rows = lines(each=2)
    rows[13][3] = round(rows[13][3] + 0.2, 2)
    assert keyed(scan(rows)) == set()


def test_two_parts_off_in_twenty_are_how_the_costs_are():
    rows = lines(parts=20)
    for i in (13, 27):
        rows[i][3] = round(rows[i][3] + 0.2, 2)
    assert keyed(scan(rows)) == set()


def test_two_parts_off_in_forty_are_each_a_slip():
    rows = lines(parts=40)
    for i in (13, 47):
        rows[i][3] = round(rows[i][3] + 0.2, 2)
    assert keyed(scan(rows)) == {13, 47}


def test_a_name_is_no_key_two_parts_may_share_one():
    names = ["Bolt", "Nut", "Washer", "Cable", "Tie", "Board", "Screw", "Pin", "Clip", "Seal"]
    rows = [[line, names[int(part[-1])], q, c] for line, part, q, c in lines()]
    rows[13][3] = round(rows[13][3] + 0.2, 2)
    assert keyed(scan(rows)) == set()


def test_a_word_for_no_value_is_never_another_value_of_its_key():
    cols = ["Line", "Part", "Qty", "Supplier"]
    rows = [[line, part, q, f"Maker {part[-1]}"] for line, part, q, _ in lines()]
    rows[13][3] = "Unknown"
    out = APP.post("/scan", json={"columns": cols, "rows": rows, "strength": 5}).get_json()["rows"]
    assert not any("differs from the other" in r["reason"] for r in out)


def test_three_parts_off_are_how_the_costs_are_however_many_parts_agree():
    rows = lines(parts=100)
    for i in (13, 47, 151):
        rows[i][3] = round(rows[i][3] + 0.2, 2)
    assert keyed(scan(rows)) == set()


def test_a_date_is_no_key_two_things_happen_on_one_day():
    rows = [[line, f"12/{int(part[-1]) + 10}/1823", q, c] for line, part, q, c in lines()]  # before 1900: kept as text
    rows[13][3] = round(rows[13][3] + 0.2, 2)
    assert keyed(scan(rows)) == set()
