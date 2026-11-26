"""Scans every .xlsx in eval/ with the engine, as the pane sends a sheet (values, plus each cell's formula in R1C1),
and grades the flagged cells against ground_truth.json. A cell counts as flagged when a row's severity is set (not
"Noted") and its reasons name that cell; the Medium+ line leaves out Low ("worth a check").
Exit 1 when a score goes backwards (CI, tools/check.py). Usage: python eval/run_eval.py"""
import json
import re
import sys
from pathlib import Path

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "backend"))
from anomaly_hunter.agents.scan_agent import scan  # noqa: E402

# AH-229: the baseline of 2026-11-25. A change that misses a planted error or adds a false alarm fails; one that
# removes a false alarm lowers these in the same commit, so the gain is kept.
FALSE_ALARMS, MEDIUM_FALSE_ALARMS = 9, 2
REF = re.compile(r"(\$?)([A-Z]{1,3})(\$?)(\d+)")


def r1c1(formula, row, col):
    def part(axis, fixed, at, here):
        return f"{axis}{at}" if fixed else axis if at == here else f"{axis}[{at - here}]"
    return REF.sub(lambda m: part("R", m[3], int(m[4]), row) + part("C", m[1], column_index_from_string(m[2]), col),
                   formula)


def flagged(path):
    values = openpyxl.load_workbook(path, data_only=True).active
    forms = openpyxl.load_workbook(path).active
    head = [c.value for c in values[1]]
    rows = [[v if v is None or isinstance(v, (int, float, str)) else str(v) for v in r]
            for r in values.iter_rows(min_row=2, values_only=True)]
    formulas = [[r1c1(c.value, c.row, c.column) if c.data_type == "f" else None for c in r]
                for r in forms.iter_rows(min_row=2)]
    out = scan(head, rows, formulas=formulas, fair=False)[1]
    return {f"{get_column_letter(head.index(c) + 1)}{i + 2}": r["severity"]
            for i, r in enumerate(out) if r["severity"] not in (None, "Noted") for c in r["cells"]}


def main():
    truth = json.loads((HERE / "ground_truth.json").read_text())
    tp = fp = fn = loud_tp = loud_fp = 0
    for path in sorted(HERE.glob("*.xlsx")):
        want, quirks, got = set(truth[path.name]["errors"]), set(truth[path.name]["quirks"]), flagged(path)
        loud = {c for c, s in got.items() if s in ("Medium", "High")}
        got = set(got)
        tp, fp, fn = tp + len(want & got), fp + len(got - want), fn + len(want - got)
        loud_tp, loud_fp = loud_tp + len(want & loud), loud_fp + len(loud - want)
        print(f"{path.name}: caught {len(want & got)}/{len(want)}"
              f"  missed {sorted(want - got)}  false alarms {sorted(got - want)}"
              f"  quirks flagged {sorted(quirks & got)}")
    print(f"Precision {tp / (tp + fp) if tp + fp else 0:.2f}  Recall {tp / (tp + fn) if tp + fn else 0:.2f}"
          f"  ({tp} caught, {fn} missed, {fp} false alarms)")
    print(f"Medium+ only: Precision {loud_tp / (loud_tp + loud_fp) if loud_tp + loud_fp else 0:.2f}"
          f"  ({loud_tp} caught, {loud_fp} false alarms; Low is \"worth a check\")")
    if fn or fp > FALSE_ALARMS or loud_fp > MEDIUM_FALSE_ALARMS:
        print(f"EVAL fail: at most 0 missed, {FALSE_ALARMS} false alarms and {MEDIUM_FALSE_ALARMS} Medium+ allowed")
        return 1
    print("EVAL pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
