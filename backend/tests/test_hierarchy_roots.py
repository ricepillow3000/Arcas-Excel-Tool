"""AH-198: a column that points at rows of its own table (a bill of materials' Parent, a Manager that is an Employee ID)
is a tree: its blank is a root, a top-level assembly or the boss, never a value left out. A bill of materials' 4 top
assemblies were each "Blank cell in column Parent, which is otherwise filled". A pointer names one row: nearly all its
values (99%) a value another column writes once. Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Part", "Parent", "Qty"]
LEAVES = ["BOLT-M8", "NUT-M8", "WASHER-8", "CABLE-1", "TIE-200", "PCB-3", "SCREW-4", "PIN-2", "CLIP-6", "SEAL-9"]


def tree(roots=5, strays=0):
    """roots top assemblies, 4 subassemblies each, 5 leaves each (from 10 parts used again and again): 120 pointers."""
    rows = []
    for a in range(roots):
        rows.append([f"ASM-{a}", None, 1])
        for s in range(4):
            rows.append([f"ASM-{a}-S{s}", f"ASM-{a}", 1 + s % 2])
            rows += [[LEAVES[(a + s + k) % 10], f"ASM-{a}-S{s}", 2 + k] for k in range(5)]
    for k in range(strays):  # a parent that is a leaf part used on many rows: no one row it names
        rows[2 + 6 * k][1] = LEAVES[k]
    return rows


def blank_flags(out):
    return {i for i, r in enumerate(out) if "Blank cell in column Parent" in r["reason"]}


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def test_the_blank_parent_of_a_top_assembly_is_a_root_never_a_value_left_out():
    assert blank_flags(scan(tree())) == set()


def test_a_pointer_with_one_value_in_a_hundred_naming_no_one_row_is_still_a_pointer():
    assert blank_flags(scan(tree(strays=1))) == set()  # 119 of 120 name one row: 99%


def test_a_column_with_two_values_naming_no_one_row_is_no_pointer_and_its_blanks_are_slips():
    assert blank_flags(scan(tree(strays=2))) == {0, 25, 50, 75, 100}  # 118 of 120


def test_a_column_of_another_columns_values_on_many_rows_is_no_tree():
    # a country of asylum is also a country of origin, but of many rows: its blank is a value left out
    places = ["Peru", "Chile", "Ghana", "Kenya", "Nepal", "Laos", "Fiji", "Oman"]
    rows = [[places[k % 8], places[(k * 3 + 1) % 8], 10 + k] for k in range(120)]
    rows[50][1] = None
    out = APP.post("/scan", json={"columns": ["Origin", "Asylum", "Refugees"], "rows": rows, "strength": 5}).get_json()["rows"]
    assert "Blank cell in column Asylum, which is otherwise filled" in out[50]["reason"]
