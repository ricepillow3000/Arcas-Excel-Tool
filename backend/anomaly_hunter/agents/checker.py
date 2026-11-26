"""Agent 3: check a fix. Put it into a copy of the table and scan again with the SAME limits, so the row is judged
exactly like the first time - by every check, not only the one that flagged it."""
import re
import time

from openpyxl.utils import column_index_from_string

from anomaly_hunter.agents.scan_agent import scan

_clock = time.monotonic  # tests replace it


def check(columns, rows, limits, i, changes, strength=5):
    """changes = [{"col": column index, "value": new cell}] in row i -> {clean, severity, reason} for that row.
    strength = the one the first scan used, so the row is judged by the same checks."""
    rows = list(rows)
    rows[i] = list(rows[i])  # the caller's table is never touched
    for c in changes:
        rows[i][c["col"]] = c["value"]
    verdict = scan(columns, rows, limits, strength=strength, fair=False)[1][i]  # one row's verdict: no fairness report
    return {"clean": verdict["severity"] in (None, "Noted"), "severity": verdict["severity"], "reason": verdict["reason"]}


def slips(v):
    """Values one typing slip away from v -> {value: what slipped}: two neighbouring digits swapped, an extra digit,
    the decimal point in the wrong place (x10^k, |k| <= 3), the sign flipped. A dropped digit is not tried: it could
    have been any of ten."""
    s, sign, out = f"{abs(v):.10g}", -1 if v < 0 else 1, {}

    def add(c, kind):
        c = float(f"{c:.10g}")
        if c != v:
            out.setdefault(c, kind)

    if "e" not in s:
        for k in range(len(s) - 1):
            if s[k] != s[k + 1] and (s[k] + s[k + 1]).isdigit():
                add(sign * float(s[:k] + s[k + 1] + s[k] + s[k + 2:]), "two digits swapped")
        for k in range(len(s)):
            if s[k].isdigit() and (t := s[:k] + s[k + 1:]) not in ("", "."):
                add(sign * float(t), "an extra digit")
    for e in (-3, -2, -1, 1, 2, 3):
        add(v * 10 ** e, "the decimal point in the wrong place")
    if v:
        add(-v, "the sign flipped")
    return out


MAX_CELLS = 300_000  # every candidate costs a full re-scan (4.7 s at this size, measured 2026-10-16); bigger: no typo hunt
BUDGET = 10  # seconds of re-scans per typo hunt; the pane's buttons wait on it (8-12 re-scans took 37-60 s)


def suggest(columns, rows, limits, i, col, strength=5):
    """For a row that is only unusual (nothing past a limit): the ONE value a typing slip away from its `col` cell that
    lands inside the column's usual range AND makes the whole row look normal again -> {value, kind}. A median would
    always "pass" and invent data, so none is offered; two candidates that both pass = no way to know which: {}."""
    if col not in columns or len(rows) * len(columns) > MAX_CELLS:
        return {}
    j = columns.index(col)
    v, lim = rows[i][j], (limits or {}).get(col)
    if type(v) not in (int, float) or not lim or lim[0] is None or lim[1] is None:
        return {}
    nums = [r[j] for r in rows if type(r[j]) in (int, float)]
    whole = sum(float(x).is_integer() for x in nums) >= 0.95 * len(nums)  # counts: 1.2 units is no fix
    ok, end = [], _clock() + BUDGET
    for c, kind in slips(v).items():
        if not (lim[0] <= c <= lim[1] and (not whole or c.is_integer())):
            continue
        if _clock() > end:  # out of time: an untried candidate might also pass, so none is "the only one"
            return {}
        if check(columns, rows, limits, i, [{"col": j, "value": c}], strength)["clean"]:
            ok.append((c, kind))
            if len(ok) > 1:
                return {}
    return {"value": ok[0][0], "kind": ok[0][1]} if ok else {}


def _typed(old, new):
    """The AI's text as the engine would read the cell after the write, or None when that can't be known here: a
    formula (Excel works it out, the engine can't) or a number cell given text Excel may still read as a number."""
    if not isinstance(new, str) or new.lstrip()[:1] == "=":
        return None
    try:
        return float(new)
    except ValueError:
        return None if type(old) in (int, float) else new


def unfixed(columns, rows, row_index, start_row, start_col, formulas, changes, strength=5):
    """AH-231: the AI's cells the engine's own checks still flag once its values are in the row -> [cell]. A value no
    check reads (a label, a formula) passes, as before. A row holding a formula is not judged: its values are the old
    ones Excel recalculates after the write, so a right fix would look wrong beside a stale total."""
    rows, put = [list(r) for r in rows], {}
    for c in changes:
        m = re.fullmatch(r"([A-Z]+)(\d+)", c["cell"])
        k, j = int(m.group(2)) - start_row - 2, column_index_from_string(m.group(1)) - 1 - start_col
        if 0 <= k < len(rows) and 0 <= j < len(columns) and (v := _typed(rows[k][j], c["new"])) is not None:
            rows[k][j] = v
            put.setdefault(k, {})[columns[j]] = c["cell"]
    if any(isinstance(f, str) and f.startswith("=") for f in formulas or []):  # the pane sends the flagged row's only
        put.pop(row_index, None)
    if not put:
        return []
    verdicts = scan(columns, rows, strength=strength, fair=False)[1]
    return [cell for k, at in put.items() if verdicts[k]["severity"] not in (None, "Noted")
            for col, cell in at.items() if col in verdicts[k]["cells"]]
