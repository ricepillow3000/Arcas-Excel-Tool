"""AH-214: a formula that breaks the pattern its siblings share across its row or down its column, Excel's own
"inconsistent formula" idea read in a summary block (a SUMIFS grid by region and quarter): one cell whose criteria point
one row or column off, a COUNTIFS of another department's code, a grand total that adds its "of which" rows. The column
check of AH-152 needs 5 rows and one formula text, so a block of 4 to 12 rows, or a column whose cells each read the row
of another block (=R6C6, =R7C6, ...), went unseen: 6 planted on the complex bench's tuning episodes. Synthetic sheets."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
SUMIFS = '=SUMIFS(Orders!R2C5:R999C5,Orders!R2C3:R999C3,RC1,Orders!R2C4:R999C4,R3C)'


def scan(cols, rows, formulas):
    r = APP.post("/scan", json={"columns": cols, "rows": rows, "strength": 5, "formulas": formulas})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def said(out):
    """{row: (reason, cells)} of each row a formula reason makes Medium or worse."""
    return {i: (r["reason"], r["cells"]) for i, r in enumerate(out)
            if r.get("severity") in ("Medium", "High") and "formula" in [k for k, _ in r.get("kinds", [])]}


def grid(regions=("North", "South", "East", "West", "Central"), cell=SUMIFS):
    """A summary block: a region a row, its sales by quarter (one SUMIFS copied across and down), a row total, and a
    grand total row adding each column, sent as the layout reader sends a subtotal (its values blank, its formulas kept).
    -> columns, rows, formulas."""
    cols, rows, formulas = ["Region", *QUARTERS, "Total"], [], []
    for k, g in enumerate(regions):
        q = [1000.0 + 100 * k + 10 * j for j in range(4)]
        rows.append([g, *q, sum(q)])
        formulas.append([None, cell, cell, cell, cell, "=SUM(RC[-4]:RC[-1])"])
    n = len(regions)
    rows.append(["Grand total", "", "", "", "", ""])
    formulas.append([None, *[f"=SUM(R[-{n}]C:R[-1]C)"] * 4, "=SUM(RC[-4]:RC[-1])"])  # the corner adds across: honest
    return cols, rows, formulas


def test_an_honest_summary_block_says_nothing():
    assert said(scan(*grid())) == {}


def test_a_cell_whose_criteria_point_one_column_off_is_flagged_on_that_cell_alone():
    cols, rows, formulas = grid()
    formulas[2][2] = SUMIFS.replace("R3C)", "R3C[1])")
    out = scan(cols, rows, formulas)
    assert said(out) == {2: ("Q2 is worked out differently from the 3 other cells of its row that share one formula "
                             "(Q1, Q3, Q4)", ["Q2"])}
    assert not out[2].get("formula") and out[2]["severity"] == "Medium"  # never a fix: which one is meant is unknown


def test_a_countifs_of_another_rows_code_is_flagged():
    cols = ["Department", "G1", "G2", "G3", "G4", "Total"]
    codes = ("ENG", "OPS", "SAL", "FIN", "HRS")
    rows = [[d, 1, 2, 3, 4, 10] for d in codes]
    formulas = [[None, *[f'=COUNTIFS(Roster!R5C2:R430C2,"{d}-*",Roster!R5C5:R430C5,R4C)'] * 4, "=SUM(RC[-4]:RC[-1])"]
                for d in codes]
    formulas[3][3] = formulas[2][3]  # FIN's G3 counts SAL: copied from the row above
    assert list(said(scan(cols, rows, formulas))) == [3]


def test_a_grand_total_that_adds_its_of_which_rows_is_flagged_on_its_totals_row():
    cols, rows, formulas = ["Region", *QUARTERS, "Total"], [], []
    for k, g in enumerate(("North", "South", "East", "West", "Central")):
        rows += [[g, *[1000.0 + k] * 4, 4000.0 + 4 * k], ["   of which online", *[300.0 + k] * 4, 1200.0 + 4 * k]]
        formulas += [[None, *[SUMIFS] * 4, "=SUM(RC[-4]:RC[-1])"],
                     [None, *[SUMIFS.replace("RC1", "R[-1]C1")[:-1] + ',Orders!R2C6:R999C6,"Online")'] * 4,
                      "=SUM(RC[-4]:RC[-1])"]]
    regions = "=SUM(R[-10]C,R[-8]C,R[-6]C,R[-4]C,R[-2]C)"
    rows.append(["Grand total", "", "", "", "", ""])  # as the layout reader sends it
    formulas.append([None, "=SUM(R[-10]C:R[-1]C)", regions, regions, regions, regions])
    assert said(scan(cols, rows, formulas)) == {10: (
        "Q1 is worked out differently from the 4 other cells of its row that share one formula (Q2, Q3, Q4 and 1 more)",
        ["Q1"])}


def test_a_link_that_reads_the_next_rows_cell_breaks_its_columns_pattern():
    """Budget FY links each line to its own row of the budget block above it (=R6C6, =R7C6, ...): the same formula read
    as a distance, though no two cells hold the same text."""
    lines = ["Revenue", "Cost of sales", "Salaries", "Rent", "Marketing", "IT", "Travel", "Fees"]
    cols = ["Line", "Actual FY", "Budget FY", "Variance"]
    rows = [[x, 100.0 + k, 90.0 + k, 10.0] for k, x in enumerate(lines)]
    formulas = [[None, None, f"=R{6 + k}C6", "=RC[-2]-RC[-1]"] for k in range(len(lines))]
    formulas[5][2] = "=R12C6"  # IT reads Travel's budget
    assert said(scan(cols, rows, formulas)) == {5: (
        "Budget FY is worked out differently from the 7 other rows of its column, which follow one pattern", ["Budget FY"])}


def test_three_siblings_are_enough_and_two_are_not():
    cols, rows, formulas = grid(regions=("North", "South", "East"))
    formulas[1][1] = SUMIFS.replace("RC1", "R[-1]C1")
    assert list(said(scan(cols, rows, formulas))) == [1]  # its row: 3 agree
    for f in formulas:
        f[4] = None  # Q4 typed: 2 siblings left in each row, and in each column 2
    for r in rows:
        r[4] = 5.0
    assert said(scan(cols, rows, formulas)) == {}


def test_two_odd_cells_in_one_row_or_column_are_how_it_is_written():
    cols = ["Measure", "Q1", "Q2", "Q3", "Q4", "Q5"]  # one row of key figures: no column has siblings
    formulas = [[None, *[SUMIFS] * 3, *[SUMIFS.replace("R3C)", "R3C[1])")] * 2]]
    assert said(scan(cols, [["Net sales", 1.0, 2.0, 3.0, 4.0, 5.0]], formulas)) == {}
    formulas[0][5] = SUMIFS
    assert list(said(scan(cols, [["Net sales", 1.0, 2.0, 3.0, 4.0, 5.0]], formulas))) == [0]  # one odd of five
    cols, rows = ["Line", "Budget FY"], [[f"Line {k}", 90.0] for k in range(8)]
    formulas = [[None, f"=R{6 + k}C6"] for k in range(8)]
    formulas[2][1], formulas[5][1] = "=R9C6", "=R12C6"  # two lines read the next line's budget
    assert said(scan(cols, rows, formulas)) == {}


def test_a_column_that_differs_on_every_row_the_same_way_is_its_role():
    """A running balance across the months: the first month starts from the opening balance on every row."""
    cols = ["Account", "Opening", "Jan", "Feb", "Mar", "Apr"]
    rows = [[a, 100.0, 110.0, 120.0, 130.0, 140.0] for a in ("Cash", "Bank", "Savings", "Petty cash")]
    formulas = [[None, None, "=RC[-1]+Moves!R2C2", "=RC[-1]+Moves!R2C3", "=RC[-1]+Moves!R2C4", "=RC[-1]+Moves!R2C5"]
                for _ in rows]
    for f in formulas:  # every month adds its own column of moves: Jan alone reads differently in each row
        f[2:] = ["=SUM(RC[-1],Moves!RC)"] + ["=SUM(RC[-1],Moves!RC[1])"] * 3
    assert said(scan(cols, rows, formulas)) == {}


def test_a_lone_formula_or_a_column_with_two_breaks_at_its_top_says_nothing():
    cols = ["Line", "Actual FY", "Budget FY"]
    rows = [[f"Line {k}", 100.0 + k, 90.0] for k in range(10)]
    formulas = [[None, f"='P&L'!R{k + 10}C16", None] for k in range(10)]
    formulas[0][1], formulas[1][1] = "='P&L'!R9C16", "='P&L'!R13C16"  # the totals link to their own rows above
    formulas[4][2] = "=SUM(Budget!R2C2:R9C2)"
    assert said(scan(cols, rows, formulas)) == {}


def test_a_running_total_across_a_row_starts_its_chain_with_a_formula_of_its_own():
    cols, rows, formulas = ["Line", "W1", "W2", "W3", "W4", "W5"], [], []
    for k, g in enumerate(("Concrete", "Metals", "Wood", "Finishes")):
        rows.append([g, *[100.0 + k] * 5])
        formulas.append([None, *["=ROUND(Budget!R2C2*R1C,0)"] * 5])
    rows.append(["Cumulative", *[0.0] * 5])
    formulas.append([None, "=R[-1]C", *["=RC[-1]+R[-1]C"] * 4])  # the first week has no week before it to add
    assert said(scan(cols, rows, formulas)) == {}
    formulas[-1][3] = "=RC[-2]+R[-1]C"  # a week that skips the one before it still breaks the chain
    assert list(said(scan(cols, rows, formulas))) == [4]


def test_a_subtotal_row_that_counts_its_ids_and_adds_its_amounts_is_two_formulas():
    cols, rows, formulas = ["Department", "Employee ID", "FTE", "Salary", "Bonus", "Cost"], [], []
    for d, size in (("NUR", 6), ("ADM", 5)):  # of two sizes: no two subtotal rows alike down a column
        for k in range(size):
            rows.append([d if k == 0 else "", f"{d}-{1000 + k}", 1.0, 30000.0 + k, 0.0, 33000.0 + k])
            formulas.append([None] * 6)
        rows.append(["", "", "", "", "", ""])
        formulas.append([None, f"=SUBTOTAL(3,R[-{size}]C:R[-1]C)", *[f"=SUBTOTAL(9,R[-{size}]C:R[-1]C)"] * 4])
    assert said(scan(cols, rows, formulas)) == {}


def test_a_grand_total_alone_in_its_corner_is_no_break_of_the_row_totals_above_it():
    cols, rows, formulas = grid()
    formulas[-1][1:5] = [None] * 4  # the totals row adds only its Total column
    formulas[-1][5] = "=SUM(R[-5]C:R[-1]C)"
    assert said(scan(cols, rows, formulas)) == {}


def kpi(gap):
    """A summary: four links to a bill of quantities' totals, then (past `gap` blank rows) a floor area typed and a cost
    per square metre worked out from it. -> columns, rows, formulas."""
    cols = ["Item", "Amount"]
    rows = [[f"Section {k}", 1000.0 + k] for k in range(4)] + [["", ""]] * gap + [["Floor area", 1240.0],
                                                                                  ["Cost per m2", 3.3]]
    formulas = [[None, f"=BOQ!R{94 + k}C8"] for k in range(4)] + [[None, None]] * gap + [[None, None],
                                                                                      [None, "=TenderTotal/R[-1]C"]]
    return cols, rows, formulas


def test_a_formula_past_a_blank_row_and_a_typed_cell_is_no_sibling_of_the_run_above_it():
    assert said(scan(*kpi(gap=1))) == {}
    cols, rows, formulas = kpi(gap=0)
    del rows[4], formulas[4]  # the typed floor area out too: the cost now sits right under the links
    assert list(said(scan(cols, rows, formulas))) == [4]  # in the run: still a break
    cols, rows, formulas = kpi(gap=1)
    formulas[3][1] = "=BOQ!R98C8"  # the run's own last link reads one row off: still flagged
    assert list(said(scan(cols, rows, formulas))) == [3]
