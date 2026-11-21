"""AH-214: a row filed under the wrong group. In a grouped list (a category merged down its rows, which the layout reader
fills for the engine), every code of a group starts the same way (HTL- for hand tools, 3. for the Build phase, 6 for
operating expenses), so a code that starts as another group's codes do sits under the wrong heading: 6 planted on the
complex bench's tuning episodes, a SKU, a WBS number, an account, a student, a cost code and an employee moved into
the next block. Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Category", "SKU", "Description", "Qty"]


def scan(rows, cols=COLS):
    r = APP.post("/scan", json={"columns": cols, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def said(out):
    return {i: (r["reason"], r["cells"]) for i, r in enumerate(out)
            if r.get("severity") in ("Medium", "High") and "group" in [k for k, _ in r.get("kinds", [])]}


def stock(sizes=(8, 8, 8)):
    """Fasteners, Hand tools and Power tools, each its own block of SKUs (FAS-1xxx, HTL-1xxx, PTL-1xxx), the category
    on every row as the layout reader fills a merged label down."""
    rows = []
    for (name, code), size in zip((("Fasteners", "FAS"), ("Hand tools", "HTL"), ("Power tools", "PTL")), sizes, strict=False):
        rows += [[name, f"{code}-1{k:03d}", f"{name} item {k}", 10 + k] for k in range(size)]
    return rows


def test_an_honest_grouped_list_says_nothing():
    assert said(scan(stock())) == {}


def test_a_sku_that_starts_as_another_groups_do_is_flagged_on_its_cell():
    rows = stock()
    rows[11][1] = "PTL-1193"
    assert said(scan(rows)) == {11: ('SKU "PTL-1193" starts like the rows under Power tools ("PTL-"), not like the '
                                     'other 7 under Hand tools ("HTL-")', ["SKU"])}


def test_a_row_moved_whole_is_said_once_on_its_first_column():
    """Its description starts as the other group's too ("Earthwork: ..."): one slip, one finding."""
    cols = ["Division", "Code", "Description", "Budget"]
    rows = [["26 Electrical", f"26-{100 + 10 * k}", f"Electrical: part {k}", 1000.0 + k] for k in range(8)]
    rows += [["31 Earthwork", f"31-{100 + 10 * k}", f"Earthwork: part {k}", 2000.0 + k] for k in range(6)]
    rows[4][1:3] = ["31-300", "Earthwork: painting"]
    assert said(scan(rows, cols)) == {4: (
        'Code "31-300" starts like the rows under 31 Earthwork ("31-"), not like the other 7 under 26 Electrical ("26-")',
        ["Code"])}


def test_an_account_number_of_another_class_is_flagged():
    cols = ["Section", "Acct", "Line item", "Amount"]
    rows = [["Revenue", 4000 + 100 * k, f"Revenue {k}", 500.0] for k in range(3)]
    rows += [["Cost of sales", 5000 + 100 * k, f"Cost {k}", 300.0] for k in range(3)]
    rows += [["Operating expenses", 6000 + 100 * k, f"Expense {k}", 100.0 + k] for k in range(9)]
    rows[12][1] = 5110
    assert list(said(scan(rows, cols))) == [12]


def test_five_rows_are_enough_to_know_a_groups_codes_and_four_are_not():
    rows = stock(sizes=(8, 5, 8))
    rows[10][1] = "PTL-1193"  # Hand tools: 4 HTL and this one
    assert list(said(scan(rows))) == [10]
    rows = stock(sizes=(8, 4, 8))
    rows[10][1] = "PTL-1193"  # 3 HTL and this one
    assert said(scan(rows)) == {}


def test_two_codes_of_another_group_in_one_block_are_an_honest_regrouping():
    rows = stock()
    rows[10][1], rows[13][1] = "PTL-1193", "PTL-1201"  # two power tools sold as hand tools this season
    assert said(scan(rows)) == {}


def test_a_code_that_starts_as_no_other_group_does_or_groups_that_share_a_start_say_nothing():
    rows = stock()
    rows[11][1] = "XYZ-1193"
    assert said(scan(rows)) == {}
    rows = [[g, f"S-26-{k + 10 * j:04d}", "sample", 1] for j, g in enumerate(("Glucose", "Sodium", "Potassium"))
            for k in range(8)]  # every group's codes start "S-26-00": no group has a start of its own
    rows[11][1] = "S-26-0001"
    assert said(scan(rows)) == {}


def test_a_label_written_in_more_than_one_block_is_no_grouped_list():
    rows = stock()
    rows = rows[:12] + rows[16:20] + rows[12:16] + rows[20:]  # Hand tools in two blocks, Power tools between
    rows[5][1] = "HTL-1193"
    assert said(scan(rows)) == {}


def test_groups_whose_starts_sit_one_inside_another_have_no_start_of_their_own():
    cols = ["Section", "Acct", "Line item", "Amount"]
    rows = [["Sales", 4000 + 10 * k, f"Sale {k}", 100.0] for k in range(8)]  # 4000-4070: they start with 40
    rows += [["Other income", 4100 + 100 * k, f"Income {k}", 50.0] for k in range(3)]  # 4100-4300: with 4 alone
    rows[3][1] = 4500
    assert said(scan(rows, cols)) == {}


def test_a_crafted_wide_sheet_of_grouped_columns_stays_quick():
    """Grouped columns and code columns are read in sheet order, the first GROUP_COLS and CODE_COLS: 32 grouped text
    columns beside 32 code columns took 33 s on 5,000 rows before the caps."""
    import time

    from anomaly_hunter.engine.load import load_from_records
    from anomaly_hunter.engine.pipeline import summary_rows, wrong_group
    n = 1000
    rows = [[f"G{i * 50 // n:02d}" if k % 2 == 0 else f"G{i * 50 // n:02d}-{i:06d}" for k in range(64)] for i in range(n)]
    df, types, _ = load_from_records([f"T{k}" for k in range(64)], rows)
    t = time.perf_counter()
    wrong_group(df, types, summary_rows(df))
    assert time.perf_counter() - t < 3
