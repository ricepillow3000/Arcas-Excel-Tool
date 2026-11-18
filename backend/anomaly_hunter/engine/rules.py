"""AH-201: rules a sheet's subject makes true (Net = Debit − Credit, Ship date before Delivery date), proposed by the AI
from the column headers alone and checked here on every row. The AI never sees a cell; it only names headers, and a
rule is a fixed shape of columns, never text run as code. A rule is believed only where the sheet itself shows it:
on 10+ rows (MIN_ROWS), true on 95% of them (HOLDS). Then each row against it is said, naming its cells."""
import numpy as np
import pandas as pd

from anomaly_hunter.engine.detectors import say
from anomaly_hunter.engine.pipeline import _cent, _decimals, _in_order, summary_rows

MIN_ROWS = 10
HOLDS = 0.95
HEADER = 100  # characters of a header sent: a header can carry a person's name or a note, and a long one is no name
NAMES = ("target", "first", "then", "value", "when", "after", "id", "parent")
LISTS = ("plus", "minus", "factors")
TAIL = ": a rule the AI read from your headers, true on {} of {} rows."


def headers(columns):
    """The sheet's own headers as sent, one line and at most HEADER characters each -> {text: column index}, in sheet
    order. A blank header, or one two columns share, is left out: a rule naming it could mean either column."""
    seen = {}
    for j, c in enumerate(columns):
        h = " ".join(str(c).split())[:HEADER]
        if h:
            seen.setdefault(h, []).append(j)
    return {h: js[0] for h, js in seen.items() if len(js) == 1}


def check(df, types, heads, asked):
    """asked = the AI's rules ({kind, why, and the headers each kind takes}) -> (checked, rows). checked: each rule that
    names only headers in `heads`, columns of the kinds it needs, each once, with said (the rule in words), held, total
    and holds; rows: [{row, cells (column indexes), reason, rule (its index in checked)}] for a rule that holds."""
    skip = summary_rows(df)
    checked, rows = [], []
    for r in asked:
        got = _judge(df, types, heads, r, skip)
        if got is None:
            continue
        said, good, judged, broke = got
        held, total = int((good & judged).sum()), int(judged.sum())
        holds = total >= MIN_ROWS and held >= HOLDS * total
        checked.append({**r, "said": said, "held": held, "total": total, "holds": bool(holds)})
        if holds:
            rows += [{"row": int(i), "cells": cells, "reason": text + TAIL.format(held, total), "rule": len(checked) - 1}
                     for i, text, cells in broke(np.flatnonzero(judged & ~good))]
    return checked, rows


def _judge(df, types, heads, r, skip):
    """One rule -> (said, good, judged, broke) or None when it names a header not sent, a column twice, or a column of
    the wrong kind. broke(rows) -> [(row, words, cell indexes)]."""
    named = [r.get(k) for k in NAMES if r.get(k) is not None] + [h for k in LISTS for h in r.get(k) or []]
    if not named or any(h not in heads for h in named) or len(set(named)) != len(named):
        return None
    col = lambda h: df.columns[heads[h]]
    kind = lambda h: types[col(h)]
    num = lambda h: pd.to_numeric(df[col(h)], errors="coerce").to_numpy(dtype=float)
    shown = lambda h, i: _shown(df, col(h), i)
    k = r.get("kind")
    if k in ("sum", "product"):
        t, plus, minus = r.get("target"), r.get("plus") or [], r.get("minus") or []
        parts = plus + minus if k == "sum" else r.get("factors") or []
        if t is None or not (plus if k == "sum" else len(parts) >= 2) or any(kind(h) != "number" for h in [t, *parts]):
            return None
        y, p = num(t), np.array([num(h) for h in parts]).reshape(len(parts), len(df))
        if k == "sum":  # a blank part is 0 where another part is filled: a journal line's empty Credit
            filled = ~np.isnan(y) & (~np.isnan(p)).any(axis=0)
            got = np.nan_to_num(p[:len(plus)]).sum(axis=0) - np.nan_to_num(p[len(plus):]).sum(axis=0)
            expr = " + ".join(plus) + "".join(f" − {h}" for h in minus)
            slack = sum(_half(x) for x in p)
        else:
            filled = ~np.isnan(y) & ~np.isnan(p).any(axis=0)
            got, q = np.prod(np.nan_to_num(p), axis=0), np.abs(np.nan_to_num(p))
            expr = " × ".join(parts)
            slack = sum(_half(p[j]) * np.prod(np.delete(q, j, axis=0), axis=0) for j in range(len(p)))
        judged = filled & ~skip & ((y != 0) | (got != 0))  # 0 = 0 x anything says nothing of the rule
        # the target alone is named, as the sentence reads: the rule says how it is worked out from the others
        return (f"{t} = {expr}", _near(y, got, judged, slack), judged,
                lambda at: [(i, f"{t} {say(y[i])} is not {expr} ({say(got[i])})", [heads[t]]) for i in at])
    if k == "order":
        a, b = r.get("first"), r.get("then")
        if a is None or b is None or kind(a) != kind(b) or kind(a) not in ("date", "number"):
            return None
        x, z = (df[col(h)] if kind(h) == "date" else pd.Series(num(h), index=df.index) for h in (a, b))
        judged = (x.notna() & z.notna()).to_numpy() & ~skip
        dated, good = kind(a) == "date", (x <= z).to_numpy()
        # which one is wrong is unknown, unless one date column is the sheet's own order and this row keeps it: then
        # the other is named alone, as pipeline.date_order names a date against its order
        named = lambda i: [heads[h] for h in (a, b) if not (dated and _in_order(df[col(h)], i, (judged & ~good).sum()))] or [heads[a], heads[b]]
        return (f"{a} is {'on or before' if dated else 'at most'} {b}", good, judged,
                lambda at: [(i, f"{a} {shown(a, i)} is {'after' if dated else 'above'} {b} {shown(b, i)}", named(i)) for i in at])
    if k == "zero_after":
        v, w, a = r.get("value"), r.get("when"), r.get("after")
        if None in (v, w, a) or kind(v) != "number" or kind(w) != "date" or kind(a) != "date":
            return None
        y, x, z = num(v), df[col(w)], df[col(a)]
        judged = ~np.isnan(y) & (x.notna() & z.notna() & (x > z)).to_numpy() & ~skip
        return (f"{v} is 0 where {w} is after {a}", np.abs(np.nan_to_num(y)) <= _cent(y), judged,
                lambda at: [(i, f"{v} {say(y[i])} is not 0 though {w} {shown(w, i)} is after {a} {shown(a, i)}",
                             [heads[v]]) for i in at])
    if k == "rollup":
        v, me, up = r.get("value"), r.get("id"), r.get("parent")
        if None in (v, me, up) or kind(v) != "number" or "date" in (kind(me), kind(up)):
            return None
        y, ids, ups = num(v), [_key(x) for x in df[col(me)]], [_key(x) for x in df[col(up)]]
        once = pd.Series(ids).value_counts()
        under = {}
        for i, u in enumerate(ups):
            if u:
                under.setdefault(u, []).append(i)
        got, kids = np.full(len(df), np.nan), np.zeros(len(df))
        for i, mine in enumerate(ids):  # only an id written once: a part listed twice has no one parent row
            ks = under.get(mine) if mine and once[mine] == 1 else None
            if ks and not np.isnan(y[i]) and not np.isnan(y[ks]).any():
                got[i], kids[i] = y[ks].sum(), len(ks)
        judged = (kids > 0) & ~skip
        return (f"{v} is the sum of {v} over the rows whose {up} is the row's {me}", _near(y, got, judged, kids * _half(y)), judged,
                lambda at: [(i, f"{v} {say(y[i])} on {me} {ids[i]} is not the sum of the {int(kids[i])} rows whose {up} is "
                             f"{ids[i]} ({say(got[i])})", [heads[v]]) for i in at])
    return None


def _half(x):
    """Half the last digit a column is written to; 0 for whole numbers, which are exact (units, laps)."""
    d = _decimals(x)
    return 0.0 if d == 0 else 0.5 * 10.0 ** -d


def _near(y, got, judged, slack):
    """Equal to the cent (or the column's own last digit) where that holds the rule; else within what the columns' own
    rounding explains, the target's own half unit included, as pipeline.pairs judges a rule: a total written to the cent
    from parts written to the cent can miss by their half cents."""
    with np.errstate(invalid="ignore"):
        exact = np.abs(y - got) <= np.maximum(_cent(y), 1e-6 * np.abs(y))
        if (exact & judged).sum() >= HOLDS * judged.sum():
            return exact
        return exact | (np.abs(y - got) <= slack + 0.5 * 10.0 ** -_decimals(y) + 1e-9 * np.abs(y))


def _key(v):
    """An id as a parent column writes it: 1001.0 read from a number cell is "1001"."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _shown(df, c, i):
    """A cell as the user wrote it: a date as typed, a number to Excel's 15 digits."""
    written = df.attrs.get("written", {})
    if c in written:
        return written[c].iloc[i]
    v = df[c].iloc[i]
    return say(v) if isinstance(v, (int, float, np.number)) else str(v)
