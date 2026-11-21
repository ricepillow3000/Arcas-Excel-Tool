"""Agent 1: find the problems. Table in -> a verdict per row. Limits are suggested from the data; limits the user
saved win, column by column. ponytail: no parallel helpers - every check needs whole-column statistics, so splitting
a big sheet would change the answers. 100k rows x 17 columns take ~8 s; add helpers when a real sheet is too slow."""
from anomaly_hunter.engine import fairness
from anomaly_hunter.engine.limits import suggest_limits_dict
from anomaly_hunter.engine.load import load_from_records, numbers
from anomaly_hunter.engine.pipeline import knobs, score


def _number(text):
    try:
        return float(text)
    except ValueError:
        return None


def learn(columns, rows, learned, decisions=None):
    """AH-205: the pane's {accept: [[column, value]], ignore: [[kind, column]]} -> score's (the cells {(row, column)} that
    hold a value accepted in their column, the [kind, column] pairs stopped, the rows they leave as they are), or None.
    A row the user dismissed keeps its own reasons: what it taught is for the other rows, and it is listed as they left
    it (Dismissed, its card still opens, Power BI's Status). Columns are the engine's names, as the pane keys its limits.
    A value is the pane's String(v): text as typed, a number by its value (7777 and "7777.0" are one), true/false as
    JavaScript writes them; a blank is never learned. Sets, so a sheet of a million rows and 500 accepted values is one
    look-up a cell."""
    if not learned:
        return None
    at, texts = {c: j for j, c in enumerate(columns)}, {}
    for col, text in learned.get("accept") or ():
        if col in at and text != "":
            texts.setdefault(at[col], set()).add(text)
    kept = {i for i, d in enumerate(decisions or ()) if d == "dismissed"}
    accepted = set()
    for j, said in texts.items():
        nums = {x for x in map(_number, said) if x is not None}
        for i, row in enumerate(rows):
            if i in kept:
                continue
            v = row[j]
            if (isinstance(v, bool) and ("true" if v else "false") in said or not isinstance(v, bool) and isinstance(v, (int, float))
                    and v in nums or isinstance(v, str) and v != "" and v in said):
                accepted.add((i, columns[j]))
    return accepted, {tuple(p) for p in learned.get("ignore") or ()}, kept


def scan(columns, rows, limits=None, order_by=None, strength=5, fair=True, formulas=None, learned=None, decisions=None,
         invalid=None):
    """-> (DataFrame, verdict per row, suggested limits, limits used, detector status, fairness report).
    strength 0-10, see knobs(). The fairness report tests protected subgroups on this scan's own flags (engine/fairness).
    learned (AH-205): what the user dismissed and the checks they stopped on this sheet, see learn(). invalid (AH-213): the
    [row, column] cells Excel says break their drop-down list."""
    df, types, errors = load_from_records(columns, rows)
    suggested = suggest_limits_dict(df, numbers(types), knobs(strength)[1])
    used = {**suggested, **(limits or {})}
    out, status = score(df, types, errors, used, order_by, strength, saved=list(limits or {}), grid=formulas,
                        learned=learn(list(df.columns), rows, learned, decisions), invalid=invalid)
    return df, out, suggested, used, status, fairness.report(df, types, out) if fair else None
