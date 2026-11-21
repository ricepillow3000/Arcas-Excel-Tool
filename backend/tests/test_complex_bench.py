"""AH-212: the complex-workbook bench reads each sheet as Find problems does (grid -> the layout reader -> one /scan per
table) and judges flags as sheet cells. A synthetic book: a title, a small rates table above the main one, a two-row
header with a merged group, one wrong total, subtotal rows, and a second tab whose table sits under 11 rows of notes."""
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "backend" / "bench" / "complex"
spec = importlib.util.spec_from_file_location("complex_judge", BENCH / "judge.py")
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)


def budget():
    v = [["Cost report Q3", "", "", "", "", ""],
         ["Region", "Rate", "", "", "", ""],
         ["North", 0.2, "", "", "", ""],
         ["South", 2.5, "", "", "", ""],  # B4: a rate typed 10x, in the small table above the main one
         ["", "", "", "", "", ""],
         ["Item", "Region", "Costs", "", "", "Total"],
         ["", "", "Jan", "Feb", "Mar", ""]]
    f = [[None] * 6 for _ in v]
    for region in ("North", "South"):
        top = len(v)
        for i in range(12):
            a, b, c = 100 + 7 * i, 200 + 3 * i, 150 + 5 * i
            v.append([f"{region[0]}-{i + 1:02d}", region, a, b, c, a + b + c])
            f.append([None] * 6)
        v.append([f"Subtotal {region}", "", *[sum(r[j] for r in v[top:]) for j in (2, 3, 4, 5)]])
        f.append([None, None, *["=SUM(R[-12]C:R[-1]C)"] * 4])
    v[12][5] += 900  # F13: the wrong total
    return {"name": "Budget", "values": v, "formats": [["General"] * 6 for _ in v], "formulas": f,
            "merged": ["A1:F1", "C6:E6", "A6:A7", "B6:B7", "F6:F7"]}


def prices():
    v = [[f"Note {i + 1}: read the rules before you change a price", "", ""] for i in range(11)]
    v.append(["Code", "Price", "Qty"])
    v += [[f"P{i}", 2.5 + i, 10 + i] for i in range(8)]
    v[14][1] = 250  # B15
    return {"name": "Prices", "values": v, "formats": [["General"] * 3 for _ in v], "formulas": [[None] * 3 for _ in v]}


KEY = {"Costs": {"domain": "budget", "errors": [
    {"sheet": "Budget", "cell": "F13", "also": ["C13", "D13", "E13"], "kind": "sum", "complex": True},
    {"sheet": "Budget", "cell": "B4", "kind": "x10", "complex": True},
    {"sheet": "Prices", "cell": "B15", "kind": "x100", "complex": False}],
    "traps": [{"sheet": "Budget", "cell": "F20", "why": "subtotal row"}]}}


def run(*args):
    return subprocess.run([sys.executable, "-I", *map(str, args)], capture_output=True, text=True, check=True).stdout  # noqa: S603 - our own scripts


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    if not shutil.which("node"):
        pytest.skip("the bench reads each sheet with the pane's own tableFromGrid, in node")
    d = tmp_path_factory.mktemp("complex")
    (d / "ep").mkdir()
    (d / "ep" / "Costs.json").write_text(json.dumps({"name": "Costs", "sheets": [budget(), prices()]}))
    (d / "keys.json").write_text(json.dumps(KEY))
    run(BENCH / "scan.py", ROOT, d / "ep", d / "out")
    return d


def test_a_flagged_total_under_a_two_row_header_maps_to_its_own_sheet_cell(scanned):
    rates, main = json.loads((scanned / "out" / "Costs__Budget.json").read_text())["tables"]
    assert (rates["startRow"], rates["startCol"], rates["columns"]) == (1, 0, ["Region", "Rate"])  # the small table above
    assert (main["startRow"], main["startCol"]) == (6, 0)  # header on rows 6 and 7: its data from row 8
    assert main["columns"] == ["Item", "Region", "Costs Jan", "Costs Feb", "Costs Mar", "Total"]
    assert "F13" in judge.flagged(main)
    assert all(c.endswith("13") for c in judge.flagged(main))  # the subtotal rows (20, 33) are sent blank: never flagged


def test_a_table_under_a_long_block_of_notes_and_one_above_the_header_are_both_read(scanned):
    prices = json.loads((scanned / "out" / "Costs__Prices.json").read_text())
    assert [(t["startRow"], t["columns"]) for t in prices["tables"]] == [(11, ["Code", "Price", "Qty"])]
    assert prices["unread_cells"] == []
    lines = run(BENCH / "judge.py", scanned / "ep", scanned / "out", scanned / "keys.json").splitlines()
    episode = json.loads(lines[1])
    assert episode["unread"] == {"outside_table": 0, "unread_sheet": 0}
    assert episode["unread_sheets"] == 0
    # B4, a rate typed 10x, is read now, but two rates are too few for any limit
    assert (episode["recall"], episode["recall_complex"], episode["recall_ordinary"]) == ("2/3", "1/2", "1/1")
    assert episode["rigid_bias"] == 0  # the subtotal F20 left alone
    assert lines[0].startswith("Costs: recall 2/3 (complex 1/2), unread 0,")


def test_the_layout_rows_inside_a_table_are_told_apart_from_its_data():
    res = {"startRow": 5, "startCol": 0, "columns": ["Item", "Region", "Costs", "", ".1", "Total"], "rows": [{}] * 26}
    assert judge.layout(budget(), res, 7) == "header-second-row"
    assert judge.layout(budget(), res, 20) == "subtotal"
    assert judge.layout(budget(), res, 13) is None


def test_the_judge_scores_cells_as_the_adversarial_judge_scores_rows(tmp_path):
    grid = [["", "Item", "Qty", "Total"], ["", "a", 5, 10], ["", "b", 6, 12], ["", "", "", ""], ["", "c", 7, 14],
            ["", "Total", 18, 36]]
    (tmp_path / "ep").mkdir()
    (tmp_path / "out").mkdir()
    (tmp_path / "ep" / "Hand.json").write_text(json.dumps({"name": "Hand", "sheets": [{"name": "S", "values": grid}]}))
    rows = [{"severity": "Medium", "cells": ["Qty"]},  # C2: an error
            {"severity": "High", "cells": []},  # no cell named: the whole row, B3 C3 D3 (D3 an error)
            {"severity": "Medium", "cells": ["Total"]},  # D4: on the blank separator
            {"severity": "Low", "cells": ["Qty"]},  # C5: worth a check counts for neither side
            {"severity": "Medium", "cells": ["Total"]}]  # D6: the subtotal, a trap
    (tmp_path / "out" / "Hand__S.json").write_text(json.dumps(
        {"startRow": 0, "startCol": 1, "columns": ["Item", "Qty", "Total"], "rows": rows}))
    key = {"Hand": {"domain": "x", "errors": [
        {"sheet": "S", "cell": "C2", "kind": "k", "complex": True, "domain_specific": True},
        {"sheet": "S", "cell": "D3", "kind": "k"},
        {"sheet": "S", "cell": "C5", "kind": "k"},
        {"sheet": "S", "cell": "H2", "kind": "k", "complex": True}],
        "traps": [{"sheet": "S", "cell": "D6", "why": "subtotal"}, {"sheet": "S", "cell": "B4", "why": "separator"}]}}
    books, episode, detail = judge.judge(tmp_path / "ep", tmp_path / "out", key)
    # recall 40 * 2/4 = 20, domain 40 * (C2 + B4 left alone) / (1 + 2 traps) = 26.7, precision 0, FP B3 C3 D4, trap D6
    assert episode == {"score": round(20 + 80 / 3 - 3 * 25 - 25, 1), "recall": "2/4", "domain": "2/3", "false_positives": 3,
                       "rigid_bias": 1, "parts": [20.0, 26.7, 0], "recall_complex": "1/2", "recall_ordinary": "1/2",
                       "unread": {"outside_table": 1, "unread_sheet": 0}, "unread_sheets": 0,
                       "layout_false_alarms": {"separator": 1, "subtotal": 1, "header-second-row": 0, "notes": 0}}
    assert books == ["Hand: recall 2/4 (complex 1/2), unread 1, false positives 3, traps flagged 1, on layout rows 2"]
    assert {d.split()[0] for d in detail} == {"UNREAD", "MISS", "RIGID", "FP"}


def test_an_also_cell_on_another_tab_counts_as_caught_and_a_bare_one_means_the_keys_own_sheet(tmp_path):
    """A key names an `also` cell on another tab as "Sheet name!A1" (a sheet name may hold spaces and "!": split at the
    last one), a bare "A1" on the key's own sheet."""
    grid = [["Item", "Qty"], ["a", 5], ["b", 6], ["c", 7]]
    (tmp_path / "ep").mkdir()
    (tmp_path / "out").mkdir()
    sheets = [{"name": "S", "values": grid}, {"name": "Totals tab!2", "values": grid}]
    (tmp_path / "ep" / "Hand.json").write_text(json.dumps({"name": "Hand", "sheets": sheets}))
    quiet = [{"severity": None}] * 3
    flag = lambda i: [*quiet[:i], {"severity": "Medium", "cells": ["Qty"]}, *quiet[i + 1:]]
    for sheet, rows in (("S", flag(2)), ("Totals tab!2", flag(0))):  # S!B4 and 'Totals tab!2'!B2 flagged
        (tmp_path / "out" / f"Hand__{sheet}.json").write_text(json.dumps(
            {"startRow": 0, "startCol": 0, "columns": ["Item", "Qty"], "rows": rows}))
    key = {"Hand": {"domain": "x", "traps": [], "errors": [
        {"sheet": "S", "cell": "B3", "also": ["Totals tab!2!B2"], "kind": "k"},  # caught on the other tab
        {"sheet": "Totals tab!2", "cell": "B3", "also": ["B4"], "kind": "k"}]}}  # B4 of its own tab: not flagged there
    books, episode, detail = judge.judge(tmp_path / "ep", tmp_path / "out", key)
    assert episode["recall"] == "1/2" and episode["false_positives"] == 1  # S!B4 is no cell of either error
    assert sorted(d.split()[0] + " " + d.split()[2] for d in detail) == ["FP S!B4", "MISS Totals"]
