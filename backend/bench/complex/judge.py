"""AH-212 judge: adversarial/judge.py's reward function, on sheet cells instead of table rows.
usage: python -I judge.py <epdir> <outdir> <keysfile>
A cell is "flagged as an error" when a High or Medium row names it (the cells the pane colours, `spots`: the row's
`cells`, or the whole row when none of them is a column). Data row i of a table sits on sheet row startRow + 2 + i
(1-based: startRow is the header's 0-based row) and column j on startCol + j. Low counts for neither side.
Key per book (FORMAT.md): errors {sheet, cell, also, kind, complex, domain_specific}, traps {sheet, cell, why}; an also
cell is on the error's own sheet ("D17") or names another tab ("Sheet name!D17").
Score per episode (max 100), as adversarial/judge.py:
  recall  = 40 * caught errors / all errors
  domain  = 40 * (domain-specific errors caught + traps left alone) / (domain-specific errors + traps)
  precision = 20 if no valid cell is flagged, else 0
  penalties: -25 per flagged valid cell (false positive), -25 per flagged trap (not also counted as a false positive)
A sheet's scan holds one table (as before AH-212) or several ({"tables": [...]}: the layout reader's, each scanned on
its own): its flagged cells are every table's.
Breakdowns: recall on complex vs ordinary errors; errors the table never read (every accepted cell outside the table,
or on a sheet with no table); flagged cells (false positives and traps) on a layout row inside the table: a blank
separator, a subtotal, a header's second row or a notes line.
"""
import json
import re
import sys
from pathlib import Path

SURE = {"High", "Medium"}
LAYOUTS = ("separator", "subtotal", "header-second-row", "notes")
TOTAL = re.compile(r"\b(sub-?)?totals?\b|\bsum\b", re.IGNORECASE)
SUMMED = re.compile(r"SUBTOTAL\(|SUM\(R\[-", re.IGNORECASE)  # a sum of the rows above it, in R1C1


def a1(col, row):
    """0-based column, 1-based row -> "C17"."""
    s, col = "", col + 1
    while col:
        col, k = divmod(col - 1, 26)
        s = chr(65 + k) + s
    return s + str(row)


def cell_at(addr):
    """"C17" -> (2, 17)."""
    m = re.fullmatch(r"([A-Z]+)(\d+)", addr)
    col = 0
    for ch in m[1]:
        col = col * 26 + ord(ch) - 64
    return col - 1, int(m[2])


def flagged(res):
    out = set()
    cols = res["columns"]
    for i, r in enumerate(res["rows"]):
        if r.get("severity") in SURE:
            js = [cols.index(c) for c in r.get("cells") or [] if c in cols] or range(len(cols))
            out |= {a1(res["startCol"] + j, res["startRow"] + 2 + i) for j in js}
    return out


def inside(res, addr):
    col, row = cell_at(addr)
    return (res["startRow"] + 2 <= row <= res["startRow"] + 1 + len(res["rows"])
            and res["startCol"] <= col < res["startCol"] + len(res["columns"]))


def layout(sheet, res, row):
    """The layout a table's sheet row (1-based) holds, or None for a data row."""
    c0, w = res["startCol"], len(res["columns"])
    vals, fs = sheet["values"][row - 1][c0:c0 + w], (sheet.get("formulas") or [[]] * row)[row - 1] or []
    fs = [f for f in fs[c0:c0 + w] if f]
    filled = [v for v in vals if v not in ("", None)]
    if not filled and not fs:
        return "separator"
    if any(isinstance(v, str) and TOTAL.search(v) for v in filled) or any(SUMMED.search(f) for f in fs):
        return "subtotal"
    if row == res["startRow"] + 2 and all(isinstance(v, str) for v in filled):
        below = [r[c0:c0 + w] for r in sheet["values"][row:res["startRow"] + 1 + len(res["rows"])]]
        def numeric(j):
            seen = [r[j] for r in below if r[j] not in ("", None)]
            return 2 * sum(isinstance(v, (int, float)) and not isinstance(v, bool) for v in seen) > len(seen)
        if any(v not in ("", None) and numeric(j) for j, v in enumerate(vals)):
            return "header-second-row"
    if len(filled) == 1 and isinstance(filled[0], str) and w >= 3:
        return "notes"
    return None


def judge(eps, scans, key):
    E = C = D = DC = FP = RB = 0
    kinds = {True: [0, 0], False: [0, 0]}  # complex or not: [caught, all]
    unread = {"outside_table": 0, "unread_sheet": 0}
    lay = dict.fromkeys(LAYOUTS, 0)
    books, detail, unread_sheets = [], [], 0
    for name, k in key.items():
        book = json.loads((eps / f"{name}.json").read_text())
        res, flags = {}, set()
        for s in book["sheets"]:
            f = scans / f"{name}__{s['name']}.json"
            r = json.loads(f.read_text()) if f.exists() else {"unread": True}
            if "error" in r:
                print("ENGINE ERROR on", name, s["name"], r)
                sys.exit(2)
            if r.get("unread"):
                unread_sheets += 1
                continue
            res[s["name"]] = r.get("tables", [r])
            flags |= {(s["name"], c) for t in res[s["name"]] for c in flagged(t)}
        b = {"E": 0, "C": 0, "CE": 0, "CC": 0, "FP": 0, "RB": 0, "U": 0, "L": 0}
        err_cells = set()
        for e in k["errors"]:
            # an also cell on another tab is "Sheet name!A1" (a name may hold spaces or "!": split at the last one)
            cells = [(e["sheet"], e["cell"])] + [tuple(c.rsplit("!", 1)) if "!" in c else (e["sheet"], c)
                                                 for c in e.get("also", [])]
            err_cells |= set(cells)
            hit = any(c in flags for c in cells)
            E += 1; C += hit; b["E"] += 1; b["C"] += hit
            kinds[bool(e.get("complex"))][0] += hit
            kinds[bool(e.get("complex"))][1] += 1
            if e.get("complex"):
                b["CE"] += 1; b["CC"] += hit
            if e.get("domain_specific"):
                D += 1; DC += hit
            if e["sheet"] not in res:
                unread["unread_sheet"] += 1; b["U"] += 1
                detail.append(f"UNREAD {name} {e['sheet']}!{e['cell']} [{e['kind']}]: the sheet has no table")
            elif not any(inside(t, c) for sh, c in cells if sh in res for t in res[sh]):
                unread["outside_table"] += 1; b["U"] += 1
                detail.append(f"UNREAD {name} {e['sheet']}!{e['cell']} [{e['kind']}]: outside the table")
            elif not hit:
                detail.append(f"MISS  {name} {e['sheet']}!{e['cell']} [{e['kind']}{', complex' if e.get('complex') else ''}]")
        traps = {(t["sheet"], t["cell"]): t["why"] for t in k["traps"]}
        D += len(traps)
        for (sh, c), why in traps.items():
            if (sh, c) in flags:
                RB += 1; b["RB"] += 1
                detail.append(f"RIGID {name} {sh}!{c} ({why})")
            else:
                DC += 1
        for sh, c in sorted(flags - err_cells - set(traps)):
            FP += 1; b["FP"] += 1
            detail.append(f"FP    {name} {sh}!{c}")
        for sh, c in sorted(flags - err_cells):
            t = next(t for t in res[sh] if inside(t, c))
            kind = layout(next(s for s in book["sheets"] if s["name"] == sh), t, cell_at(c)[1])
            if kind:
                lay[kind] += 1; b["L"] += 1
        books.append(f"{name}: recall {b['C']}/{b['E']} (complex {b['CC']}/{b['CE']}), unread {b['U']}, "
                     f"false positives {b['FP']}, traps flagged {b['RB']}, on layout rows {b['L']}")
    recall = 40 * C / E if E else 40
    domain = 40 * DC / D if D else 40
    prec = 20 if FP == 0 else 0
    score = recall + domain + prec - 25 * FP - 25 * RB
    episode = {"score": round(score, 1), "recall": f"{C}/{E}", "domain": f"{DC}/{D}", "false_positives": FP,
               "rigid_bias": RB, "parts": [round(recall, 1), round(domain, 1), prec],
               "recall_complex": "{}/{}".format(*kinds[True]), "recall_ordinary": "{}/{}".format(*kinds[False]),
               "unread": unread, "unread_sheets": unread_sheets, "layout_false_alarms": lay}
    return books, episode, detail


if __name__ == "__main__":
    books, episode, detail = judge(Path(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text()))
    print("\n".join(books))
    print(json.dumps(episode))
    print("\n".join(detail))
