"""AH-198 fix round 2: an indented list (a bill of materials, an org chart printed as a tree) is written depth first,
and a sub-assembly that several products share is listed again under each of them: its lines repeat exactly. Those
are the tree's layout, never "Duplicate of row N" (1,700 cells of one costed bill), and a top product's blank parent
is a root, though its part numbers repeat and no one row is named. The same line twice under one parent is still a
copy. Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Level", "Part", "Parent", "Qty", "Cost"]
SHARED = [("BOLT-M8", 4, 0.12), ("NUT-M8", 4, 0.05), ("WASHER-8", 8, 0.02), ("CABLE-1", 2, 3.4), ("TIE-200", 6, 0.04)]


def bill(products=6):
    """Each product: its own frame (3 parts) and the shared drive sub-assembly with its 5 parts, listed again in full."""
    rows = []
    for p in range(products):
        rows.append([0, f"PROD-{p}", None, 1, 900.0 + 37 * p])
        rows.append([1, f"FRAME-{p}", f"PROD-{p}", 1, 120.0 + 11 * p])
        rows += [[2, f"BAR-{p}-{k}", f"FRAME-{p}", 2 + k, 8.0 + p + k] for k in range(3)]
        rows.append([1, "DRIVE", f"PROD-{p}", 1, 240.0])
        rows += [[2, part, "DRIVE", qty, cost] for part, qty, cost in SHARED]
    return rows


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def said(out, words):
    return {i for i, r in enumerate(out) if words in r["reason"]}


def test_a_shared_sub_assembly_listed_again_under_another_product_is_the_trees_layout_never_a_copy():
    out = scan(bill())
    assert said(out, "Duplicate of row") == set()
    assert said(out, "Blank cell in column Parent") == set()  # 6 products, each a root: their part numbers repeat


def test_the_same_line_twice_under_one_parent_is_still_a_copy():
    rows = bill()
    rows.insert(8, list(rows[7]))  # BOLT-M8 listed twice under the first DRIVE
    assert said(scan(rows), "Duplicate of row") == {8}


def deep(levels):
    """4 roots, each over the same chain of sub-assemblies `levels` deep: no part number names one row."""
    rows = []
    for r in range(4):
        rows.append([0, f"ROOT-{r}", None, 1, 10.0 + r])
        rows += [[k, f"N-{k}", f"ROOT-{r}" if k == 1 else f"N-{k - 1}", 1, 5.0 + k] for k in range(1, levels)]
    return rows


def test_a_tree_sixty_four_levels_deep_is_still_a_tree():
    assert said(scan(deep(64)), "Blank cell in column Parent") == set()


def test_a_chain_sixty_five_levels_deep_is_no_tree():
    # each row the next one's parent all the way down is a chain, never walked to its end: its blanks are judged
    assert said(scan(deep(65)), "Blank cell in column Parent") == {0, 65, 130, 195}


def test_a_bill_with_one_line_in_a_hundred_hung_under_no_row_on_its_path_is_still_a_tree():
    rows = bill(products=20)  # 200 lines with a parent: 2 may miss theirs (99%)
    rows[13][2] = "FRAME-7"  # a bar of product 1 hung under product 7's frame, listed nowhere above it
    out = scan(rows)
    assert said(out, "Duplicate of row") == set() and said(out, "Blank cell in column Parent") == set()
