"""AH-222: a grid of sibling columns whose blanks are how it is filled in. A staff timetable's 30 period columns (a class
code, PPA, or blank for a free period) were each 70-97% filled, so every free period was "Blank cell in column Wed P3,
which is otherwise filled": 97 Medium cells and a trap on one sheet (complex bench, B episode 9). Five or more columns
side by side, of one kind, each with a blank, whose blanks together are MANY+, a GRID_SHARE of their cells and spread
through the sheet, are one note, as one column's many spread blanks are; a few, a block or a thin scatter are still
each a slip. Synthetic sheets only."""
import random

from anomaly_hunter.server import create_app

APP = create_app().test_client()


def grid(cols=10, rows=30, blanks=0.15, seed=7, block=False):
    """A timetable: Teacher, then `cols` period columns of class codes, each cell blank with chance `blanks` (in the
    first fifth of the rows only, with block). Every column gets at least one blank. -> columns, rows."""
    rng = random.Random(seed)
    heads = ["Teacher", *[f"P{j}" for j in range(1, cols + 1)]]
    out = []
    for i in range(rows):
        row = [f"T{i:02d}"]
        for j in range(cols):
            gone = rng.random() < blanks and (not block or i < rows // 5)
            row.append("" if gone else f"{7 + (i + j) % 5}{'XY'[(i * j) % 2]}{1 + j % 4} {['Ma', 'En', 'Sc'][i % 3]}")
        out.append(row)
    for j in range(cols):
        if all(r[1 + j] for r in out):
            out[(3 * j) % (rows // 5 if block else rows)][1 + j] = ""
    return heads, out


def blank_flags(heads, rows):
    r = APP.post("/scan", json={"columns": heads, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    out = r.get_json()["rows"]
    return out, [i for i, o in enumerate(out) if o.get("severity") in ("High", "Medium") and "Blank cell" in o["reason"]]


def count(rows):
    return sum(v == "" for r in rows for v in r[1:])


def test_a_timetables_free_periods_spread_through_its_grid_are_one_note():
    heads, rows = grid()
    out, flagged = blank_flags(heads, rows)
    assert flagged == []
    noted = [o["reason"] for o in out if "spread through the sheet" in o["reason"]]
    assert noted == [f"P1 to P10 are blank in {count(rows)} of their 300 cells, spread through the sheet: how this grid is filled in"]


def test_four_columns_side_by_side_are_no_grid_and_five_are():
    heads, rows = grid(cols=4, rows=40)
    assert count(rows) >= 20 and blank_flags(heads, rows)[1]
    heads, rows = grid(cols=5, rows=40)
    assert blank_flags(heads, rows)[1] == []


def test_blanks_in_a_block_of_the_grid_are_still_each_a_slip():
    heads, rows = grid(rows=60, blanks=0.3, block=True)
    assert count(rows) >= 20 and len(blank_flags(heads, rows)[1]) >= 5


def scatter(k, rows=200, cols=10):
    """A full grid of `rows` x `cols` with exactly k blanks scattered through it, at most one a row and column pair."""
    heads, out = grid(cols=cols, rows=rows, blanks=0)
    for r in out:
        r[1:] = [v or f"{7 + len(r[0]) % 5}X1 Ma" for v in r[1:]]
    for m in range(k):
        out[(m * 37) % rows][1 + (m * 7 + m // rows) % cols] = ""
    assert count(out) == k
    return heads, out


def test_a_thin_scatter_of_blanks_in_a_big_grid_is_still_each_a_slip_and_a_twentieth_of_it_is_the_grid():
    assert len(blank_flags(*scatter(99))[1]) >= 50  # 4.95% of the 2,000 cells: deletions, never the grid's way
    assert blank_flags(*scatter(100))[1] == []  # 5%


def test_a_row_blank_across_four_fifths_of_the_grid_is_a_record_left_unfinished_never_the_grids():
    heads, rows = grid(rows=40)
    rows[20][1:9] = [""] * 8  # 8 of the 10 periods: a record that stopped
    out, flagged = blank_flags(heads, rows)
    assert 20 not in flagged and "unfinished record" in out[20]["reason"], out[20]
    heads, rows = grid(rows=40)
    rows[20][1:8] = [""] * 7  # 7 of 10: a part-timer's free periods, the grid's own
    out, flagged = blank_flags(heads, rows)
    assert flagged == [] and "unfinished record" not in out[20]["reason"], out[20]
