"""Score a loaded DataFrame: 3 detector votes + hygiene facts -> severity, bucket, reason per row.
Shared by CLI and server."""
import collections
import datetime
import hashlib
import itertools
import re

import numpy as np
import pandas as pd

from anomaly_hunter.engine import fairness
from anomaly_hunter.engine.detectors import Why, _result, ecod_detector, far_off, limits_detector, say, sequence_detector, unexplained
from anomaly_hunter.engine.load import EXCEL_ERROR, NO_VALUE_WORD, PLACEHOLDER, _blank, _dates, _orders, numbers
from anomaly_hunter.powerbi import FORMULA_START

def summary_rows(df):
    """Rows that summarise the data instead of being data -> bool array: fully blank rows, rows labelled
    Total/Subtotal/Mean/... that are sparser than a normal row ("Total Wine" the vendor is a full row), and
    unlabelled rows whose numbers equal the sum of the rows above them."""
    if df.empty:  # headers only: nothing to summarise (np.median of nothing warns)
        return np.zeros(len(df), dtype=bool)
    cols = [c for c in df.columns if c != "source_file"]
    count = (~df[cols].apply(_blank)).sum(axis=1).to_numpy()
    nums = [c for c in cols if df[c].dtype.kind in "fi"]
    # no text filled in (a date may be: a month-end subtotal is dated) - on a sheet with no text, no date either
    labels = [c for c in cols if c not in nums and df[c].dtype.kind != "M"] or [c for c in cols if c not in nums]
    unlabelled = df[labels].apply(_blank).all(axis=1).to_numpy()
    rows_with = lambda key: df.index.isin(df.attrs.get(key, ()))  # set by load, before coercion
    sparse = count < np.median(count)  # a totals row leaves the label/date/text cells empty
    # "Total" + sparse; "Average"/"Mean" only if half empty ("Average" can be a rating in a normal row)
    mask = (count == 0) | (rows_with("total_rows") & sparse) | (rows_with("stat_rows") & (count <= np.median(count) / 2))
    x = df[nums].to_numpy(dtype=float)
    run = np.vstack([np.zeros(len(nums)), np.nancumsum(x, axis=0)])  # run[i] = sum of rows before i
    start = 0
    for i in np.flatnonzero(mask | sparse):  # only sparse rows can be unlabelled totals
        if mask[i]:
            start = i + 1
            continue
        above = run[i] - run[start]
        have = ~np.isnan(x[i]) & (above != 0)
        if i - start >= 2 and sparse[i] and unlabelled[i] and have.any() and (np.abs(x[i][have] - above[have]) <= 0.005 * np.abs(above[have])).all():
            mask[i], start = True, i + 1
    return mask


PASTED = 5  # copies of this many consecutive rows in a row: a range pasted again


def duplicates(df, errors_log=(), column_types=None, skip=None):
    """Row equal to an earlier row in every column but source_file. Text typed into a number or date column is compared as
    that text: loading had blanked it, so "R+33.2" and "D+6.3" rows looked equal (513 false duplicates, 2026-10-16).
    -> (reasons per row, notes per row): max(MANY, SHARE of the rows) repeats found in every fifth of the sheet are one
    note on the first (AH-48: a hotel table with no ID repeats 4,324 bookings); a few, or a block, are each a slip."""
    cols = [c for c in df.columns if c != "source_file"]
    cells, at = df[cols].astype(str).to_numpy(copy=True), {c: k for k, c in enumerate(cols)}
    for i, c, raw in errors_log:
        cells[i, at[c]] = f"text:{raw}"
    # a name not kept ("?", "*", Unknown) in a column whose labels mostly differ row to row (as many as half its cells) is no
    # proof of one record: a contest's unknown entrants with tied scores were 41 "Duplicate of row N" (AH-173)
    kind = {c: (column_types or {}).get(c, "text" if df[c].dtype == object else "") for c in cols}
    known = {}
    for c in cols:
        v, filled = df[c].astype(str).str.strip(), ~_blank(df[c])
        known[c] = filled & ~(v.str.fullmatch(NO_VALUE_WORD) | ~v.str.contains(r"\w"))
    # a row with its own id or name (a column 95% distinct over 20+ known values) is told apart by it, whatever "NA" sits
    # elsewhere: lunala copied exactly, its url_icon "NA" like 229 of 950 rows, was no duplicate (Pokemon, blind round 1,
    # AH-173 fix round 1). A measure never names a row: a score to the hundredth is 97% distinct, and two "?" entrants
    # tied on it were one record again (AH-173 fix round 2)
    ids = [c for c in cols if kind[c] in ("text", "id") and known[c].sum() >= MANY
            and df[c][known[c]].astype(str).str.strip().nunique() >= 0.95 * known[c].sum()]
    named = np.logical_or.reduce([known[c].to_numpy() for c in ids]) if ids else np.zeros(len(df), bool)
    for c in cols:
        if kind[c] not in ("text", "id"):
            continue
        v, filled = df[c].astype(str).str.strip(), ~_blank(df[c])
        unknown = filled & ~known[c]
        if unknown.any() and v[known[c]].nunique() >= 0.5 * filled.sum():
            for i in np.flatnonzero(unknown.to_numpy() & ~named):
                cells[i, at[c]] = f"unknown:{i}"
    # AH-198 fix round 2: in a tree a row is also where it hangs: a shared sub-assembly listed again under another product
    # is the layout, never a copy (1,700 cells of one costed bill were "Duplicate of row N"); the same row twice under one
    # parent still is
    for parent in itertools.islice(_tree(df, column_types or {}, np.zeros(len(df), bool) if skip is None else skip).values(), 1):
        cells = np.column_stack([cells, parent.astype(str)])
    seen, out = {}, []
    # a totals row is no record: its numbers left out, 150 subtotal rows reading only "Total" were "many repeats", and the
    # one note on a skipped row hid a real copy (blind round 2, AH-178)
    skip = np.zeros(len(df), bool) if skip is None else skip
    keys = [("total row", i) if skip[i] else tuple(row) for i, row in enumerate(cells)]
    # when most rows repeat, a repeat is the data: 4 agree/disagree answers from 1,529 voters gave 199 different rows,
    # and 1,330 were "Duplicate of row N" (real survey, 2026-10-16). A double entry repeats a row that is otherwise unique
    notes = [[] for _ in keys]
    kept = [k for k, s in zip(keys, skip, strict=True) if not s]
    if len(set(kept)) < 0.5 * len(kept):
        return [[] for _ in keys], notes
    first = [seen.setdefault(key, i) for i, key in enumerate(keys)]
    n, copies = len(keys), [i for i, j in enumerate(first) if j != i]
    # many repeats through the whole sheet, with nothing (an ID) to tell two real records apart, are how the data is:
    # two bookings of the same room type, dates and rate. A slip is rare, or a range pasted twice, all in one place
    # A range pasted again is copies of 5+ consecutive rows, one after another, wherever it lands: 5 ranges of 12 rows,
    # one in each fifth of the sheet, were one note (AH-48 review). The hotel table repeats real bookings in pairs and
    # threes (65 runs of 2, one of 3, one of 4 in round 36), never 5
    step = [0 < i and first[i] != i and first[i - 1] != i - 1 and first[i] == first[i - 1] + 1 for i in range(n)]
    pasted, k = set(), 0
    while k < n:
        e = k + 1
        while e < n and step[e]:
            e += 1
        if e - k >= PASTED and first[k] != k:
            pasted.update(range(k, e))
        k = e
    spread = [i for i in copies if i not in pasted]
    # a column no two different rows share (an Order ID, an invoice code) tells records apart: a row that repeats it is the
    # same record twice. 120 orders imported twice and sorted by date were one note saying "nothing like an ID" (AH-48 review)
    distinct = df.iloc[[i for i in range(n) if first[i] == i and not skip[i]]]
    def ident(c):
        t, v = (column_types or {}).get(c), distinct[c]
        whole = t == "id" or t == "text" or (t == "number" and pd.to_numeric(v, errors="coerce").dropna().mod(1).eq(0).all())
        return whole and len(v) >= MANY and v.notna().all() and v.is_unique
    if len(spread) >= max(MANY, SHARE * n) and len({i * 5 // n for i in spread}) == 5 and not any(map(ident, cols)):
        notes[spread[0]].append(Why(f"{len(spread)} of {n} rows repeat an earlier row exactly, all through the sheet - "
                                    f"the first is this one, a copy of row {first[spread[0]] + 2}", *cols))
        copies = set(copies) - set(spread)
    copies = set(copies)
    for i, j in enumerate(first):
        src = f" ({df['source_file'].iloc[j]})" if "source_file" in df else ""  # CLI path only
        out.append([Why(f"Duplicate of row {j + 2}{src}", *cols)] if i in copies else [])  # the whole row is the copy
    return out, notes


def _short(t):
    """Cell text quoted in a reason, at most 60 characters: a 32k-character cell keeps the reason readable."""
    t = str(t)
    return t if len(t) <= 60 else t[:57] + "..."


MISSING = re.compile(r"na|nan|none|missing", re.I)


def _shape(raw):
    """R+51.5 -> a+9.9, 16A -> 9a: the pattern of a code, not its value."""
    return re.sub(r"[^\W\d_]+", "a", re.sub(r"\d+", "9", str(raw).strip()))


def _serial(text):
    """A whole number Excel could hold as a date -> that date as Excel's 1900 date system reads it, else None. Serial 1 is
    1900-01-01, and Excel counts a 1900-02-29 that never was (Lotus 1-2-3's leap-year bug), so from 61 on a serial is
    a day past 1899-12-30; 2958465 is 9999-12-31, its last."""
    try:
        n = float(text) if len(text) <= 20 else 0.0  # never a long digit run through float()
    except ValueError:
        return None
    if not (n.is_integer() and 1 <= n <= 2958465):
        return None
    if n == 60:
        return "1900-02-29"
    # (datetime, not pandas: a pandas timestamp ends in 2262)
    return (datetime.date(1899, 12, 30 if n > 60 else 31) + datetime.timedelta(days=int(n))).isoformat()


def type_errors(df, errors_log, column_types):
    """Text in a number or date column. A text shape the column repeats 5+ times is its own code system (partisan lean
    "R+51.5", district "16A": 8,000 false rows on one real sheet, 2026-10-16), not a slip; placeholders and missing-value
    words (N/A, -, NA) never are. The cells stay in errors_log: they are text, for duplicates and blanks alike.
    -> (reasons, notes): a placeholder the column writes max(MANY, NO_VALUE_SHARE of the rows) times through 4 of the 5
    fifths of the sheet is its code for "no value", one note (AH-45: a survey's 1-5 rating of Italy's cuisine, "N/A" 67 times)."""
    n = len(df)
    out, notes = [[] for _ in range(n)], [[] for _ in range(n)]
    ph = collections.defaultdict(lambda: collections.defaultdict(list))  # column -> spelling -> rows
    other = collections.Counter()  # text that is no word for no value
    for i, col, raw in errors_log:
        if PLACEHOLDER.fullmatch(str(raw).strip()) and str(raw).strip().upper() != "ERROR":
            ph[col][str(raw).strip().upper()].append(i)
        else:
            other[col] += 1
    coded = set()
    for col, spelt in ph.items():
        # every spelling of no value counted together, the export's NA read as missing too: 47 "N/A", 26 "NA", 6 "-" and
        # 3 "None" each fell short of the bar and were each Medium; and where the column is already a fifth empty (any
        # spelling or blank), another spelling is one more of them, never a slip (blind round 2, AH-177)
        rows = sorted(i for r in spelt.values() for i in r)
        said = df.attrs.get("no_value", {}).get(col, ((),))[0]
        every = sorted(set(rows) | set(said))
        if len(every) >= max(MANY, NO_VALUE_SHARE * n) and _spread(every, n) or _blank(df[col]).sum() - other[col] >= EMPTY * n:
            coded |= {(i, col) for i in rows}
            words = sorted(spelt, key=lambda k: (-len(spelt[k]), min(spelt[k])))
            raws = [next(str(r).strip() for j, c, r in errors_log if j == spelt[k][0] and c == col) for k in words]
            notes[rows[0]].append(Why(f'{col} is {" or ".join(chr(34) + _short(r) + chr(34) for r in raws)} (no value) in {len(rows)} of {n} rows', col))
    code = lambda raw: not (EXCEL_ERROR.match(str(raw).strip()) or PLACEHOLDER.fullmatch(str(raw).strip())
                            or MISSING.fullmatch(str(raw).strip()))
    shapes = collections.Counter((col, _shape(raw)) for _, col, raw in errors_log if code(raw))
    for i, col, raw in errors_log:
        kind, text = "date" if column_types[col] == "date" else "number", str(raw).strip()
        if code(raw) and shapes[col, _shape(raw)] >= 5 or (i, col) in coded:
            continue
        raw = _short(raw)
        # a number in a column of dates is usually a date cell Excel shows as its serial (a column whose first row is text
        # reaches the pane as numbers): say which day it would be, a hint to check, never a fix (AH-76)
        if kind == "date" and (day := _serial(text)):
            out[i].append(Why(f"{col} {say(float(text))} is a number in a column of dates (an Excel date serial for {day}?)", col))
            continue
        out[i].append(Why(f"Excel error {raw} in {col}" if EXCEL_ERROR.match(text) else f'Placeholder "{raw}" in column {col}'
                          if PLACEHOLDER.fullmatch(text) else f'Text "{raw}" in {kind} column {col}', col))
    for col, cells in df.attrs.get("as_text", {}).items():  # AH-210: "48 " typed as text among numbers
        for i, raw in cells.items():
            out[df.index.get_loc(i)].append(Why(f'{col} "{_short(raw)}" is a number typed as text, a space beside it: '
                                                "Excel's SUM and averages leave it out", col))
    return out, notes


def lost_zeros(df, column_types, skip):
    """A digit code shorter than the width its column writes ("2134" among ZIPs "02134", EmployeeID "123" among "000101"):
    its leading zeros were lost, usually by a cell formatted as a number (AH-75). Flag only, never a fix: padding is a
    guess about the source, and a card never writes into an ID column."""
    out = [[] for _ in range(len(df))]
    for col, width in df.attrs.get("padded", {}).items():
        v = df[col][~skip].astype(str).str.strip()
        # ...only as many as the column's codes write: a ZIP "02134" among ZIP+4s "021341234" (2 leading zeros at most)
        # cannot have lost 4, and 44 were flagged on one grants table (AH-173)
        full = v[v.str.fullmatch(r"\d+") & (v.str.len() == width)]
        zeros = (full.str.len() - full.str.lstrip("0").str.len()).max()
        for i in v.index[v.str.fullmatch(r"\d+") & (v.str.len() < width) & (width - v.str.len() <= zeros)]:
            k = len(v[i])
            out[i].append(Why(f'{col} "{v[i]}" is {k} digit{"s" if k > 1 else ""} where the column writes {width}: '
                              f'did it lose its leading zero{"s" if width - k > 1 else ""}?', col))
    return out


def placeholders(df, column_types, skip):
    """ERROR / UNKNOWN / N/A / NULL / ? / - left in a text column, when that word is rare (< 8% of the column: more often
    it's a real category, like Status "Error"). Excel errors (#N/A) always: they are a broken formula, never a category.
    -> (reasons per row, notes per row): a word the column writes max(MANY, NO_VALUE_SHARE of it) times through 4 of the 5
    fifths of the sheet is its own code for "no value", one note on its first row (AH-45): water points' "Unknown" 797 times and "NULL" 436 times, a survey's "N/A"
    173 times were each a Medium row in blind round 36, like R's NA (AH-27). A rarer one is still each a slip."""
    out, notes = [[] for _ in range(len(df))], [[] for _ in range(len(df))]
    for col, t in column_types.items():
        if t != "text":
            continue
        v = df[col].astype(str).str.strip()
        err = v.str.match(EXCEL_ERROR)
        ph, key = v.str.fullmatch(PLACEHOLDER) & ~skip, v.str.upper()
        filled = (~_blank(df[col]) & ~skip).sum()
        times = key.map(key[ph].value_counts()).fillna(0)
        rare = times <= max(1, 0.08 * filled)
        # ...never ERROR: a log's Level ERROR on 3% of rows is a real category, not "no value" (AH-45 review), so it keeps
        # the rare-word flag it always had
        code = ph & rare & (key != "ERROR")
        # every spelling of no value counted together ("N/A", "NA", "-", "None": each short of the bar, each Medium), and
        # where the column is already a fifth empty (any spelling or blank) another spelling is one more, never a slip (AH-177)
        said = (code | v.str.fullmatch(NO_VALUE_WORD)) & ~_blank(df[col]) & ~skip
        at = np.flatnonzero(said.to_numpy())
        # ...found in 4 of the 5 fifths of the sheet, like blanks (AH-28, AH-142): a block of 50 "?" in a census's first 150 rows is a
        # paste or an export that went wrong, still each a slip (test_wild_census)
        # ...or sparse among real values where it is: a contest sorted newest first wrote "?" for its oldest years'
        # unknown entrants, 1 in 18 of the rows it spanned, 164 Medium rows (AH-173)
        many = len(at) >= max(MANY, NO_VALUE_SHARE * filled) and (_spread(at, len(df)) or not _block(at))
        code &= many or (said | _blank(df[col]) & ~skip).sum() >= EMPTY * (~skip).sum()
        if code.any():
            words = [v[code & (key == k)].mode().iloc[0] for k in key[code].value_counts().index]
            notes[df.index[code][0]].append(Why(f'{col} is {" or ".join(chr(34) + w + chr(34) for w in words)} (no value) in {int(code.sum())} of {(~skip).sum()} rows', col))
        hit = (err & ~skip) | (ph & rare & ~code)
        if hit.any():
            for i in df.index[hit]:
                out[i].append(Why(f"Excel error {v[i]} in {col}" if err[i] else f'Placeholder "{v[i]}" in column {col}', col))
    return out, notes


MANY = 20  # blanks in one column: from here, spread through the sheet, they are how the data is (AH-28)
SHARE = 0.01  # ...and at least 1% of its rows: 20 values gone from a 20,000-row column are still each a slip (AH-28 review)
# a blank or a placeholder from 0.5%: 1% made a ZIP's 280 unknowns in 28,156 rows (0.99%) and a coo_name's 459 "Unknown"
# in 50,000 each a Medium row (AH-142); 20 in 20,000 (0.1%) are still each a slip
NO_VALUE_SHARE = 0.005
EMPTY = 0.2  # a column a fifth empty already: another word for no value in it is one more of them (AH-177)


def _spread(pos, n):
    """Found in 4 of the 5 fifths of the sheet: rodents' tag, blank for 2,064 animals never tagged from row 6,772 on, had
    none in the first fifth and was 2,064 Medium rows (AH-142). A block (a paste, an export that stopped) sits in one or two:
    a fifth counts only with 2% of the cells, so 300 deleted in a row beside 3 strays elsewhere stay each a slip (AH-142
    review: a fifth of one cell counted, and 093's names, fifths 2/2/89/33/0, were one note)."""
    c = np.bincount(np.asarray(pos, dtype=int) * 5 // n, minlength=5)
    return (c >= 0.02 * len(pos)).sum() >= 4


BLOCK = 1 / 8  # a block fills at least 1 in 8 of the rows it spans: a paste or an export gone wrong fills 1 in 4 or more


def _block(pos):
    """Positions that fill the stretch they sit in (BLOCK of its rows), 2% at each end left out as strays (AH-173)."""
    k = int(0.02 * len(pos))
    core = np.sort(np.asarray(pos))[k:len(pos) - k]
    return len(core) >= BLOCK * (core[-1] - core[0] + 1)


def _sorted_end(s, blank, skip):
    """The blanks at the very end of a table sorted by this column (Marvel's APPEARANCES, most first): Excel's sort puts
    blank cells last, both ways (AH-46). -> their positions, or none when the column's values are in no order."""
    live = np.flatnonzero(~np.asarray(skip))
    tail = len(live) - next((k + 1 for k in range(len(live) - 1, -1, -1) if not blank[live[k]]), 0)
    v = s.iloc[live[:len(live) - tail]][~blank[live[:len(live) - tail]]].dropna()
    # a few blanks stay each a slip: 3 deleted invoice numbers at the end of a list in number order are no sort's doing
    if tail < MANY or len(v) < 20 or v.nunique() < 5:  # a constant or two-label column is in order by itself
        return live[:0]
    v = v.astype(str).str.casefold() if v.dtype.kind not in "biufmM" else v  # A-Z as Excel sorts, any capitals
    # in order but for a slip or two: round 36's x10 plant (528 typed 5280) stood against the order once in 15,280 rows
    # ...counted against the column's changes of value: Manager grouped by a sorted Region (Dave, Alice, Eve, Bob, Carol)
    # changes 4 times, 2 of them against any order, and is in no order at all
    step = np.sign(np.diff(v.rank(method="min").to_numpy()))
    step = step[step != 0]
    against = min((step > 0).sum(), (step < 0).sum())
    return live[len(live) - tail:] if against <= max(2, 0.001 * len(v)) and against <= 0.05 * len(step) else live[:0]


# a header that asks: "Do you ever gamble?", "How worried are you about the Big One?" - never "Paid?" or "Shipped?", an
# orders sheet's yes/no columns, which are one or two words
ASKING = re.compile(r"(?i)^\s*(?:q\d+[.:)]?\s*)?(?:how|what|which|who|whom|whose|when|where|why|do|does|did|are|is|was|were|"
                    r"would|could|should|have|has|had|will|can|please|to what|in general|if you)\b")


def _asks(col):
    """A header that is a question: 3+ words ending in "?", or 4+ words opening as one."""
    return len(w := str(col).split()) >= 3 and str(col).strip().endswith("?") or len(w) >= 4 and bool(ASKING.match(str(col)))


def _survey(cols):
    """A sheet is a survey when 3+ of its headers, and half of them, are questions: its answers may be left unanswered,
    a blank is no slip (AH-56). Half, not a quarter: an orders sheet with 3 of its 8 headers worded as questions ("Is this
    a repeat customer?") passed a quarter, and its deleted Revenue cells were read as skipped answers (AH-56 review)."""
    asked = [c for c in cols if _asks(c)]
    return len(asked) >= 3 and len(asked) >= 0.5 * len(cols)


POINTS = 0.99  # a column whose filled cells name this share of values another column holds points at that column's rows
DEPTH = 64  # levels of a tree, at most: a bill of materials or an org chart is a dozen deep


def _tree(df, column_types, skip):
    """AH-198 fix round 2: an indented list (a bill of materials, a chart of accounts, an org chart printed as a tree) is
    written depth first: each row's pointer names a row on the path above it (its parent, or an ancestor's sibling's
    parent). A shared sub-assembly is listed again under every product that uses it, so the part numbers repeat and no
    one row is named, and 1,700 cells of one costed bill were "Duplicate of row N". Read by walking the rows with the path
    so far: a pointer found on it is a child of that row; POINTS of a column's 20+ filled pointers (5+ different values,
    never a copy of its id column on 90% of rows) must be found. A country of asylum among countries of origin is found on
    no path. -> {pointer column: parent row per row, -1 for a root or none}. The first 64 text or id columns."""
    cols = [c for c, t in column_types.items() if t in ("text", "id")][:64]
    said = {c: df[c].astype(str).str.strip().where(~skip & ~_blank(df[c])).to_numpy(object) for c in cols}
    out, values = {}, {c: set(v[~pd.isna(v)]) for c, v in said.items()}
    for p in cols:
        has = ~pd.isna(said[p])
        if has.sum() < MANY or len(values[p]) < 5:
            continue
        for k in cols:  # a pointer's values are its id column's: anything else is never walked
            if k == p or pd.Series(said[p][has]).isin(values[k]).mean() < POINTS or (said[p][has] == said[k][has]).mean() > 0.1:
                continue
            parent, path, missed = np.full(len(df), -1), [], 0
            for i in range(len(df)):
                if skip[i] or pd.isna(said[k][i]):
                    continue
                if pd.isna(said[p][i]):
                    path = [i]
                    continue
                at = next((d for d in range(len(path) - 1, -1, -1) if said[k][path[d]] == said[p][i]), None)
                if at is None:
                    missed += 1
                    if missed > (1 - POINTS) * has.sum():
                        break
                    continue
                parent[i], path = path[at], path[:at + 1] + [i]
                if len(path) > DEPTH:  # a chain (each row the next one's parent) is no tree, and would walk forever
                    break
            else:
                out[p] = parent
                break
    return out


def _pointers(df, column_types, skip, blank):
    """Columns that point at rows of their own table: a Parent Part whose every value is a Part Number above or below it,
    a Manager that is an Employee ID. Its blank is a root (a top-level assembly, the boss), never a value left out: a
    bill of materials' 4 top assemblies were each "Blank cell in column Parent Part" (AH-198). 5+ different values, nearly
    all of them (POINTS) a value another text or id column writes once, so each names one row: a country of asylum is
    also a country of origin, but of many rows, and its blank is a value left out. And that column's own value on nearly
    every row (90%) another one: a column that copies its neighbour is no pointer. The first 64 text or id columns, in
    sheet order: a crafted wide sheet stays fast. -> the columns among `blank` (those with a blank to judge) that point."""
    said = {c: df[c][~skip & ~_blank(df[c])].astype(str).str.strip()
            for c in [c for c, t in column_types.items() if t in ("text", "id")][:64]}
    held = {c: set((n := v.value_counts()).index[n == 1]) for c, v in said.items()}  # each names one row
    out = {c for c in _tree(df, column_types, skip) if c in blank}
    for c in (c for c in said if c in blank and c not in out):
        counts = said[c].value_counts()
        if len(counts) >= 5 and any(k != c and counts[counts.index.isin(held[k])].sum() >= POINTS * len(said[c]) and
                                    (said[c] != df[k][said[c].index].astype(str).str.strip()).mean() >= 0.9 for k in said):
            out.add(c)
    return out


ALMOST = 0.02  # a group of 20+ rows blank on all but this share of them (or one row) is still blank by layout


def _all_blank(per, size):
    """-> per group: a column's blanks are the group's layout. All its rows, 5 or more; or all but max(1, ALMOST) of
    20 or more: one cell filled where it should not be is that cell's mistake, never 50 blanks'. A bank reconciliation's
    outstanding cheques have no bank date or amount, 50 of 51 (the 51st cleared, a planted slip), and its 100 valid
    blank cells were each Medium (AH-208, adversarial episode 5)."""
    return (per == size) & (size >= 5) | (per >= size - np.maximum(1, ALMOST * size)) & (size >= 20)


FILLS = 0.95  # a group that fills a column on this share of its rows, beside groups that leave it empty
LABEL_SLIP = 2  # columns a row fills where its label leaves them empty, from which the label is the row's one slip


def group_gaps(df, column_types, skip, computed=None):
    """AH-208 fix round 2: one cell filled where its group leaves the column empty (blank, or 0 for a number), the
    mirror of _all_blank: a close date on one of 61 open claims, a deductible on one of 120 health claims, state tax on
    one of 47 periods in a state with none (episodes 6-8, 7 of their misses; a cleared date on an outstanding cheque in
    episode 5). Only where a text column of 2-50 labels decides the column: every label of 20+ rows leaves it empty on
    all but max(1, ALMOST) of them or fills it on FILLS of them, and one label fills it. A bonus paid on 12% of every
    department's rows, rain on 2% of every station's hours: no label decides those, so nothing is said. Never a
    protected label (a person's cell is never judged by their sex or race), nor a formula's cell (its inputs are).
    -> (reasons, explained: per row, the blank cells a label's slip explains)."""
    out, explained = [[] for _ in range(len(df))], [set() for _ in range(len(df))]
    computed, prot = computed or {}, set(fairness.protected(column_types))
    cols, labels, blank = list(column_types)[:200], {}, {}
    for c in cols:  # each text read once, as a label and as a cell (twice took 3 s on 100,000 rows x 16 labels)
        if column_types[c] != "number":
            s = df[c].astype(str).str.strip()
            blank[c] = (df[c].isna() | (s == "")).to_numpy(bool)
            if column_types[c] == "text" and c not in prot and len(labels) < 16:
                lab = s.where(~skip & ~blank[c])
                if 2 <= lab.nunique() <= 50:
                    labels[c] = pd.factorize(lab)[0]
    if not labels:
        return out, explained
    # every column at once, a label at a time: one pass a column took 8 s on 100,000 rows
    num = lambda c: np.nan_to_num(df[c].to_numpy(dtype=float)) == 0  # a number column: blank (NaN) or 0
    empty = np.column_stack([num(c) if column_types[c] == "number" else blank[c] for c in cols])
    live = np.column_stack([~np.asarray(skip, bool) & ~computed.get(c, np.zeros(len(df), bool)) for c in cols])
    filled_in = live & ~empty
    found = collections.defaultdict(list)  # (row, label column) -> the reasons of the cells it fills where its label leaves them empty
    # AH-211: ...and the columns it leaves empty where its label fills them, each with the labels that leave it empty
    unfilled, fillers = collections.defaultdict(list), {}
    for g, code in labels.items():
        on = code >= 0
        at = (code[on][:, None] * len(cols) + np.arange(len(cols))).ravel()  # (label, column) of each cell, counted at once
        count = lambda m, at=at, on=on, g=len(np.unique(code[on])): np.bincount(at, weights=m[on].ravel(), minlength=g * len(cols)).reshape(g, -1).astype(int)
        sizes, fills = count(live), count(filled_in)
        for j, col in enumerate(cols):
            if col == g:
                continue
            size, filled, x, typ = sizes[:, j], fills[:, j], df[col], column_types[col]
            big = size >= 20
            empty_g = big & (filled <= np.maximum(1, ALMOST * size))
            full_g = big & (filled >= FILLS * size)
            if not full_g.any() or not empty_g.any() or (big & ~empty_g & ~full_g).any():
                continue
            fillers[g, col] = set(np.flatnonzero(full_g))
            for i in np.flatnonzero(live[:, j] & empty[:, j] & np.isin(code, np.flatnonzero(full_g))):
                unfilled[i, g].append((col, set(np.flatnonzero(empty_g))))
            if not (empty_g & (filled > 0)).any():
                continue
            for i in np.flatnonzero(live[:, j] & ~empty[:, j] & np.isin(code, np.flatnonzero(empty_g & (filled > 0)))):
                k = code[i]
                said = "blank" if typ != "number" else "blank or 0"
                found[i, g].append(Why(f"{col} {_shown(x.iat[i])} is filled where {g} {_short(df[g].iat[i])} leaves it {said} "
                                       f"on {int(size[k] - filled[k])} of {int(size[k])} rows", col))
    # AH-210: one slip changes one cell: a row that fills two or more columns its label leaves empty is the label's slip
    # (a house listed as Land, with its bathrooms, living area and year built), named alone: its filled cells were each
    # coloured wrong (2 tuning episodes)
    for (i, g), said in found.items():
        filled = [r.cols[0] for r in said]
        if len(said) >= LABEL_SLIP:
            said = [Why(f"{g} {_short(df[g].iat[i])} does not fit this row, which fills {', '.join(filled[:-1])} and "
                        f"{filled[-1]}, where {g} {_short(df[g].iat[i])} leaves them empty", g)]
        # AH-211: a row that fills a column its label leaves empty and leaves empty one its label fills, both as one other
        # label has them, is that label's row: a salaried employee typed Hourly, with a salary and no hourly rate, had
        # Annual Salary coloured (valid) and the Pay Type slip missed (adversarial episode 17)
        elif gone := [c for c, empties in unfilled.get((i, g), ()) if set.intersection(empties, *(fillers[g, f] for f in filled))]:
            said = [Why(f"{g} {_short(df[g].iat[i])} does not fit this row, which fills {', '.join(filled)} and leaves "
                        f"{', '.join(gone)} blank, where {g} {_short(df[g].iat[i])}'s other rows do the opposite", g)]
            explained[i].update(gone)
        out[i] += said
    return out, explained


FIRST_ROWS = 0.8  # share of an entity column's first rows (a vehicle's, a meter's) a column leaves blank, 5 or more


def _firsts(df, column_types, skip):
    """The first row of each value of the first 64 text or id columns (a crafted wide sheet stays fast), one mask each."""
    out = []
    for c in [c for c, t in column_types.items() if t in ("text", "id")][:64]:
        v = df[c].astype(str).str.strip().where(~skip & ~_blank(df[c]))
        out.append((v.notna() & ~v.duplicated()).to_numpy())
    return out


def _first_rows(firsts, b):
    """AH-210: a column blank on each entity's first row (a vehicle's first fill has no distance since its previous one, a
    meter's first read no previous read): the first row of each value of a text or id column (`_firsts`), when FIRST_ROWS
    of those first rows (and 5 or more) are blank and they hold FIRST_ROWS of the column's blanks: 30 incomes deleted at
    the top of a sheet hold every city's first row, and are still each a slip. -> those rows, or none. A blank on any
    later row is still each a slip."""
    for first in firsts:
        if (b & first).sum() >= max(5, FIRST_ROWS * first.sum(), FIRST_ROWS * b.sum()):
            return b & first
    return np.zeros(len(b), bool)


STAGE = 0.2  # share of a label's rows left blank (5+) where the rest fill a column: a stage the label allows
OPEN = 0.98  # rows (of DATE_ROWS+) on which a date column is on or after another before its blanks can be ends not reached


def _open_end(df, col, cols, column_types, skip, b, when):
    """AH-210: an end date not reached yet (an item still out, a case still open): a date column on or after another on
    OPEN of the rows that fill both, blank on 5+ rows that fill the other, half of those among its latest quarter: what
    started most recently has most often not ended. 22 of a library's 25 blank return dates were its last 41 loans.
    -> (those rows, the start column), or None. A blank on a row of no such order, or spread evenly, is still a slip.
    when: each date column read once, shared by every call."""
    if column_types.get(col) != "date":
        return None
    read = lambda c: when[c] if c in when else when.setdefault(c, pd.to_datetime(df[c], errors="coerce", utc=True).where(~skip))
    end = read(col)
    for a in [c for c in cols if c != col and column_types[c] == "date"][:DATE_COLS]:
        start = read(a)
        both = start.notna() & end.notna()
        at = b & start.notna().to_numpy()
        if both.sum() < DATE_ROWS or (end[both] >= start[both]).mean() < OPEN or at.sum() < 5:
            continue
        if start[at].median() > start[both].quantile(0.75):
            return at, a
    return None


def _stage(df, col, pos, groups, labels, prot, n, notes):
    """AH-210: a stage one label allows (an open ticket not yet given an agent): a label of 20+ rows holding STAGE of its
    rows (5 or more) among blanks that would each be a slip, where all but 1% of the other rows fill the column. Its blanks
    are one note on the first; a blank under any other label is still each a slip (a closed ticket with no agent). Never
    by a protected label. -> the positions still each a slip."""
    b = np.zeros(len(df), bool)
    b[pos] = True
    for g, (code, size, _) in groups.items():
        if g == col or g in prot:
            continue
        now = np.bincount(code[code >= 0], weights=b[code >= 0], minlength=len(size)).astype(int)
        for k in np.flatnonzero((size >= 20) & (now >= np.maximum(5, STAGE * size)) & (b.sum() - now <= 0.01 * (n - size))):
            at = np.flatnonzero(b & (code == k))
            lab = _short(labels[g].iat[at[0]])
            notes[df.index[at[0]]].append(Why(f"{col} is blank on {len(at)} of the {size[k]} rows of {g} {lab}, where the other "
                                              f"rows fill it: a blank {lab} allows", col))
            b[at] = False
    return np.flatnonzero(b)


def blanks(df, column_types, skip, errors_log, threshold=0.80, computed=None):
    """Blank cell in a column that is >= 80% filled (summary rows not counted): a required field left empty. Mostly-empty
    columns (notes, optional extras) are left alone. Was 95%: a credit sheet's Income, 92% filled, hid 39 blanks.
    -> (blank reasons per row, notes per row): 20+ blanks found in 4 of the 5 fifths of the sheet are one note on the first."""
    out, prot = [[] for _ in range(len(df))], fairness.protected(column_types)
    notes = [[] for _ in range(len(df))]
    wrong = {}  # text/errors already named as such are not blanks
    for i, c, _ in errors_log:
        wrong.setdefault(c, []).append(i)
    # a blank its whole category group shares is the sheet's layout (a long-format sheet fills "value" for some metrics,
    # "pct" for others: 17,852 false rows on one real sheet, 2026-10-16); a blank inside an otherwise filled group is a slip
    labels = {}
    for g, t in column_types.items():
        lab = df[g].astype(str).str.strip().where(~skip & ~_blank(df[g])) if t == "text" else None
        # 200 labels of 5+ rows on average, never an ID's or a note's: outer space objects' Code is blank for the 13 of 110
        # entities with no ISO code, and the old cap of 50 made all 142 Medium (AH-142)
        many = lab is not None and (lab.nunique() <= 50 or lab.nunique() <= 200 and lab.count() >= 5 * lab.nunique())
        if many and len(labels) < 64:  # 64: a crafted 1,000-column sheet stays fast
            labels[g] = lab
    cols = list(column_types)
    if not cols:
        return out, notes
    # a negative code the column writes for "no value" (-1, -9999) is held as a blank: one note for the column, never a
    # blank cell to fill (AH-62)
    codes = df.attrs.get("codes", {})
    for c, (rows, code) in codes.items():
        first = min(rows)
        notes[first].append(Why(f"{c} {say(code)} is written {len(rows)} times: the column's code for no value", c))
    # AH-210: a formula's own blank (=IF(B2="","",...)) is its inputs' to judge, never a value left out
    computed = computed or {}
    blank = np.column_stack([(_blank(df[c]) & ~skip & ~df.index.isin(wrong.get(c, [])) & ~df.index.isin(list(codes.get(c, ((),))[0])))
                             .to_numpy(bool) & ~computed.get(c, np.zeros(len(df), bool)) for c in cols])
    n = max(1, (~skip).sum())
    firsts, when = None, {}  # read once, and only for a sheet with a blank: each column reading them made a wide scan 3x slower
    for j, col in enumerate(cols):  # AH-210: blanks the sheet's own course explains, before any is read as a slip
        if not blank[:, j].any():
            continue
        firsts = _firsts(df, column_types, skip) if firsts is None else firsts
        blank[:, j] &= ~_first_rows(firsts, blank[:, j])
        if (ended := _open_end(df, col, cols, column_types, skip, blank[:, j], when)) is not None:
            at, a = ended
            notes[df.index[np.flatnonzero(at)[0]]].append(Why(
                f"{col} is blank in {at.sum()} of {n} rows, half of them or more among the latest by {a}: an end not reached "
                "yet (an item still out, a case still open)", col))
            blank[:, j] &= ~at
    # blanks per label per column, counted for every column at once: grouping each label column against each column
    # took 168 s on a crafted 64 x 1,500-column sheet (AH-16 build, 2026-10-22)
    groups = {}
    for g, lab in labels.items():
        code = pd.factorize(lab)[0]
        keep = np.flatnonzero(code >= 0)
        order = keep[np.argsort(code[keep], kind="stable")]
        if not len(order):
            continue
        starts = np.flatnonzero(np.r_[True, np.diff(code[order]) != 0])
        size = np.diff(np.r_[starts, len(order)])
        groups[g] = (code, size, np.add.reduceat(blank[order].astype(np.int32), starts, axis=0))
    def _stopped(slip):  # -> (the rows with a slip in most of the usually filled columns: unfinished records, those columns)
        full = np.flatnonzero(1 - blank.sum(axis=0) / n >= threshold)
        gone = slip[:, full].sum(axis=1)
        return (gone >= 3) & (gone >= 0.5 * len(full)) & (len(full) >= 4), full

    roots = _pointers(df, column_types, skip, {c for j, c in enumerate(cols) if blank[:, j].any()})  # AH-198
    survey, pend = _survey(cols), []  # pend: (column, its blanks each a slip, the sentence for one) - said after the loop
    events = []  # in column order: ("note", row, why), ("pend", column, rows, sentence), ("part", column, rows, said so, word)
    for j, col in enumerate(cols):
        b = blank[:, j].copy()
        if col in roots:  # a pointer's blank is a root of the table's tree
            continue
        if b.any() and 1 - b.sum() / n >= threshold:
            for g, (code, size, per) in groups.items():
                # a group all blank before the groups above took theirs; the rest counted again on what is left
                if g == col or not _all_blank(per[:, j], size).any() or not (b & (code >= 0)).any():
                    continue
                now = np.bincount(code[code >= 0], weights=b[code >= 0], minlength=len(size))
                b &= ~np.isin(code, np.flatnonzero(_all_blank(now, size)))
            # an unknown age on 177 of 891 Titanic passengers, a film with no cast listed: one Medium per row was 1,401 rows
            # on two real tables (blind round 23). Many blanks in every fifth of the sheet are the data; a few, or a block
            # (a paste or an export that stopped), are still each a slip
            # Where the export writes "NA" for no value, those cells and the truly empty ones are judged apart: R never
            # leaves a cell empty, so an empty one among 638 bye-week NAs is a deleted value (blind round 23's NFL plant).
            # An "NA" the column writes 5+ times is its convention, like a code it repeats (type_errors), even in a block:
            # the Tour de France's first 8 years have no times, on purpose; a one-off is still a blank
            said, word = df.attrs.get("no_value", {}).get(col, (frozenset(), ""))
            coded = df.index.isin(list(said))
            end = _sorted_end(df[col], b & ~coded, skip)
            if len(end):
                events.append(("note", df.index[end[0]], Why(f"{col} is blank in {len(end)} of {n} rows, all at the end of the table, which is sorted by {col}", col)))
                b[end] = False
            for said_so in (True, False):
                events.append(("part", j, np.flatnonzero(b & (coded if said_so else ~coded)), said_so, word))
        elif b.any():
            # a long-format sheet fills Value for some indicators and Pct for others, so Value is 2/3 filled, under the bar,
            # and a blank in a GDP row went unseen (AH-17 stress hunt, 9 of 9 missed). A group that fills the column
            # (95%+, 20+ rows) next to one that leaves it empty (20% or less, 20+ rows) is the layout; a blank in the filled group
            # is a slip. Never judged by a protected group: a person's blank is not measured against their sex or race
            for g, (code, size, per) in groups.items():
                if g == col or g in prot or not 2 <= len(size) <= 20:
                    continue
                fill = 1 - per[:, j] / size
                full = np.flatnonzero((fill >= 0.95) & (size >= 20))
                # ...and the empty group is layout only with 20+ rows of its own: a real planets table's distance (96% filled
                # for one method) had only 1 of 5 Pulsar rows empty-ish, and 23 real gaps were called a slip (blind round 22)
                empty = (fill <= 0.2) & (size >= 20)
                # ...and only when the groups explain the column's blanks: in a long-format sheet nearly every blank is in
                # a group that never fills it. DC's HAIR is blank for an eye colour or two and for many others besides:
                # "otherwise filled for EYE Brown Eyes" was 43 honest unknowns on a wide sheet (round 37, AH-56)
                if len(full) and empty.any() and per[empty, j].sum() >= 0.8 * b.sum():
                    pos = np.flatnonzero(b & np.isin(code, full))
                    if len(pos) >= max(MANY, NO_VALUE_SHARE * len(b)) and _spread(pos, len(b)):  # many and spread: the data
                        events.append(("note", df.index[pos[0]], Why(f"{col} is blank in {len(pos)} of {n} rows where {g} would fill it, spread through the sheet", col)))
                    else:
                        events.append(("pend", j, pos, lambda i, col=col, g=g: f"Blank cell in column {col}, which is otherwise filled for {g} {_short(labels[g][i])}"))
                    break
    # In a survey, the respondents who stopped are taken out before a column's blanks are read as spread through the
    # sheet: 60 dropouts passed the bar in each question they left, so every such column was one note, and the one
    # respondent who skipped a question had no row or cell of their own (round 38, AH-64). Who stopped is judged as if
    # every blank were each a slip; on a data table nothing is taken out (20 deleted values stay each a slip, AH-28)
    drop = np.zeros(len(df), dtype=bool)
    if survey:
        slip = np.zeros_like(blank)
        for e in events:
            if e[0] == "pend" or e[0] == "part" and not (e[3] and len(e[2]) >= 5):
                slip[e[2], e[1]] = True
        drop = _stopped(slip)[0]
    for e in events:
        if e[0] == "note":
            notes[e[1]].append(e[2])
            continue
        if e[0] == "pend":
            pend.append(e[1:])
            continue
        _, j, pos, said_so, word = e
        col, live = cols[j], pos if said_so else pos[~drop[pos]]
        if len(pos) >= 5 if said_so else len(live) >= max(MANY, NO_VALUE_SHARE * len(blank)) and _spread(live, len(blank)):
            notes[df.index[live[0]]].append(Why(f'{col} is "{word}" (no value) in {len(pos)} of {n} rows' if said_so
                                                else f"{col} is blank in {len(live)} of {n} rows, spread through the sheet", col))
            pos = pos[drop[pos]]  # ...and those who stopped still count toward their unfinished record, below
        if len(pos) and not said_so:
            pos = _stage(df, col, pos, groups, labels, prot, n, notes)
        if len(pos):
            pend.append((j, pos, lambda i, col=col: f"Blank cell in column {col}, which is otherwise filled"))
    # A row with a blank in most of the columns that are otherwise filled, each a blank no layout, sort or export explains,
    # is one unfinished record (a respondent who stopped the survey): one note, not a Medium a column. Round 37: 25 of
    # sleeping alone's 27 flagged rows were 80-100% blank, the earthquake survey's 12 were 50-80% blank; round 36's
    # Thanksgiving's 6 were 63 of 65. Counted after the layouts: a respondent routed past a page is not one (AH-56)
    slip = np.zeros_like(blank)
    for j, pos, _ in pend:
        slip[pos, j] = True
    quit, full = _stopped(slip)
    for i in np.flatnonzero(quit):
        miss = [cols[k] for k in full if slip[i, k]]
        notes[df.index[i]].append(Why(f"{len(miss)} of the {len(full)} usually filled cells in this row are blank: an unfinished "
                                      "record (in a survey, a respondent who stopped answering)", *miss))
    for j, pos, say_it in pend:
        pos = pos[~quit[pos]]
        if len(pos) and not _unanswered(df, cols[j], column_types[cols[j]], pos, n, survey, notes):
            for i in df.index[pos]:
                out[i].append(Why(say_it(i), cols[j]))
    return out, notes


def _unanswered(df, col, kind, pos, n, survey, notes):
    """In a survey, a question left blank is one the respondent skipped: the religion survey's 175 Medium+ rows were 144
    respondents who answered nearly everything and left a question or two (round 37, AH-56). One note for the column, not
    a Medium a cell; never an ID's blank, and never on a data table (20 deleted values stay each a slip, AH-28). Each
    skipped answer is a note on its own row (many spread ones are already one note, above): one note on the first hid
    the others' rows and cells, and a data table with three questions for headers lost a deleted Revenue (AH-56 review)."""
    # ...and only an answer: a column whose header is a question, or a survey's category answer (US Region, an age band:
    # the religion survey's top 50); never a number its header does not ask for, an order's Revenue (AH-56 review)
    if not survey or not len(pos) or kind == "id" or _ID_HEAD.search(str(col)) or not (_asks(col) or kind == "text"):
        return False
    for i in df.index[pos]:
        notes[i].append(Why(f"{col} is unanswered in {len(pos)} of {n} rows: a survey question a respondent may skip", col))
    return True


_ID_HEAD = re.compile(r"(?i)(?:^|[\s_])(?:id|key|respondent ?id|code|no\.?|number|#)$")


def whole_numbers(df, column_types, skip):
    """A lone decimal in a column of whole numbers: study day 7.3 typed for 73, between days 72 and 74 - no limit can
    catch it (real clinical sheet, 2026-10-16). Worth a check (Low), no fix: the slip could be anywhere in the number."""
    out = [[] for _ in range(len(df))]
    for col, t in column_types.items():
        x = df[col][~skip].dropna() if t == "number" else ()
        if len(x) < 30 or x.nunique() < 3:
            continue
        odd = (x - x.round()).abs() > 1e-9 * x.abs().clip(lower=1)  # float noise (2.99 - 1.99) is still whole
        # A part the column writes 3+ times is its own way of writing: 69 honest half-kilo weights among 15,553 athletes
        # each read "not a whole number - every other weight is" (blind round 23, AH-38), untrue. A slip's part is its
        # own (73 typed 7.3, 42 typed 4.2): a few of those, up to 0.5% of the column, are each worth a check. Counting
        # every decimal instead, with a fixed 2, lost 3 slips on 1,000 rows and 8 on 2,000 (AH-38 review); 3 are allowed on
        # any sheet (3 on 300 rows were lost too): on 158 real tables it still names only mpg's displacement 97.5
        part = (x - np.floor(x)).round(6)
        usual = [f for f, c in part[odd].value_counts().items() if c >= 3]
        slip = odd & ~part.isin(usual)
        # ...one or two such parts (halves; quarters); more is a column of decimals (fares, prices), never "whole"
        if len(usual) <= 2 and 1 <= slip.sum() <= max(3, 0.005 * len(x)):
            ends = " or ".join(f"{f:g}".lstrip("0") for f in sorted(usual))
            # with 2+ slips, "the other values are whole or end in .5" is untrue: the other slip is neither (AH-38 try 2 review)
            rest = (f"every other {col} is" if slip.sum() == 1 else f"only {int(slip.sum())} {col} values are not") if not usual else \
                f"the other {col} values are whole or end in {ends}" if slip.sum() == 1 else \
                f"only {int(slip.sum())} {col} values are neither whole nor end in {ends}"
            for i in x.index[slip]:
                out[i].append(Why(f"{col} {say(x[i])} is not a whole number - {rest}", col))
    return out


PERSON_AGE = {"patient", "participant", "victim", "actor", "actress", "employee", "customer", "respondent", "applicant", "student",
              "member", "client", "worker", "player", "passenger", "athlete", "person", "child", "mother", "father", "driver",
              "rider", "voter", "resident", "subject", "defendant", "suspect", "officer", "candidate", "ceo", "senator", "artist",
              "author", "winner", "borrower", "tenant", "user", "donor", "inmate", "pupil", "teacher", "nurse", "doctor", "spouse"}
# "Birth month", "birth_month", "start month": a month too (round 37 missed a 13 in both; AH-55), never a count of months
# ("Months", "Months since"), a day of it, or what happened in one ("per month", "last month")
BOUNDED = [(r"(?:(?!(?:of|per|a|an|each|every|this|last|next|prev|previous|current|same|prior|that|in|by|the)\b)[a-z]+ )?month", 1, 12), (r"quarter|qtr", 1, 4), (r"hour", 0, 24), (r"minute|second", 0, 59),
           (r"weekday|day of week", 0, 7), (r"lat|latitude", -90, 90), (r"lon|lng|long|longitude", -180, 180),
           # a person's age: "age" alone or after a word for a person (victim age, actor 1 age, age years): LA riots' 310
           # for 31 in 62 rows was said nothing at level 5 (AH-47). A thing's age is not a person's: a tree's 180, a
           # building's 135, an account's or a bond's could each be said "outside what it can be" (AH-47 review). Not one
           # in days, weeks or months, and not Average, Mileage or Age group
           (r"(?:(?:" + "|".join(sorted(PERSON_AGE)) + r") )?(?:\d+ )?age(?: years| in years| yrs)?", 0, 120)]
AGE_UNITS = re.compile(r"\b(days?|weeks?|months?|hours?|minutes?|seconds?|hrs?|mins?|ms|d|wk|mo)\b")
SCALE = re.compile(r"\(\s*(\d+)\s*(?:-|–|to)\s*(\d+)\s*\)|\bout of (\d+)\b", re.I)


def _bounds(col):
    """What a column's name says its numbers can be: the header IS the name ("date of month" and "count per hour" are
    not), or it writes its own scale ("Rating (1-5)", "out of 10"). Long headers are questions or notes, not names."""
    # camelCase is words too: a birthMonth 13 among 1-12 went unseen (round 38, AH-64); "monthsActive" stays a count.
    # One lookbehind and one lookahead a position: linear on a 100,000-character header
    h = " ".join(re.sub(r"[_.]+", " ", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(col))).split()).lower()
    if len(h) > 200:
        return None
    if m := SCALE.search(h):
        return (float(m[1]), float(m[2])) if m[1] else (0.0, float(m[3]))
    # Not a percentage: a name says % far more often than it says "share of a whole". Attendance, utilization, occupancy,
    # markup, ROI, CPU, debt of GDP and a speed's % of its limit pass 100, inflation and a % increase go below 0, and a
    # 0-100 bound said "outside what it can be" of every one (AH-30 review); a 233.4 among 0-100 stands alone (AH-29)
    whole = re.sub(r"\([^()]*\)", "", h).strip()  # "Month (number)" is still Month
    return next(((float(lo), float(hi)) for pat, lo, hi in BOUNDED if re.fullmatch(pat, whole)
                 and not (hi == 120 and AGE_UNITS.search(h))), None)


# A share of a whole by its name: "Percent", "cocoa_percent", "Rate (%)". Never a percentile (a wage), "Tax 5%" (an
# amount), or one the CLAUDE.md list says can pass 100: a change, a return, attendance, occupancy, utilization, markup,
# ROI, CPU, debt of GDP, a % of a target or a limit (AH-30 review)
PERCENT = re.compile(r"percent(?:age)?\b|\bper cent\b|\bpct\b|(?<![\d.\s])\s*%|\(%\)|^%")
NOT_SHARE = re.compile(r"chang|growth|increas|decreas|diff|return|\broi\b|markup|margin|gain|loss|yoy|\bvar|attend|occupan|"
                       r"utili[sz]|cpu|gdp|debt|limit|speed|target|goal|budget|quota|plan\b|capacity|over|above|error")


def _share_over(col, x):
    """A percentage far past 100 in a column whose every other value is a share of a whole (0 to 100): a 200 among 40
    rows was found only at level 10, as an odd combination (round 37, AH-55). Far past: more than 150, as a slip writes
    it (x2, x10, 233.4); an honest 100.4 (a bonus share rounded up, 1 of 48,711 real rows in round 36) stays quiet, and
    a column with a third value over 100, or any below 0, is not a share at all."""
    h = " ".join(re.sub(r"[_.]+", " ", str(col)).split()).lower()
    if len(h) > 200 or not PERCENT.search(h) or NOT_SHARE.search(h) or len(x) < 20 or x.min() < 0:
        return ()
    over = x[x > 100]
    return over.index if 1 <= len(over) <= 2 and (over > 150).all() else ()


def named_bounds(df, column_types, skip):
    """A number past what its column's name allows: Month 13, Hour 25, a 6 on "Rating (1-5)" - each just past the other
    values, so no limit can call it (John's "syntactically correct but contextually impossible", AI council 2026-10-16).
    Quiet when more than max(2, 1%) break the bound: then the name means something else (yyyymm months, visit month 0,
    longitudes on 0-360). 40 random real tables: 13 such columns, 0 flags. Worth a check (Low), no fix."""
    out = [[] for _ in range(len(df))]
    for col, t in column_types.items():
        b = _bounds(col) if t == "number" else None
        x = df[col][~skip].dropna() if b else ()
        bad = x[(x < b[0]) | (x > b[1])] if b else ()
        if 1 <= len(bad) <= max(2, 0.01 * len(x)):
            for i in bad.index:
                out[i].append(Why(f"{col} {say(x[i])} is outside what {col} can be ({b[0]:g} to {b[1]:g})", col))
        if t == "number" and not b:
            x = df[col][~skip].dropna()
            for i in _share_over(col, x):
                rest = "every other" if len(x[x > 100]) == 1 else "every other but one"
                out[i].append(Why(f"{col} {say(x[i])} is over 100, and {rest} {col} is a share between 0 and 100", col))
    return out


YEAR_FIRST = r"^(\d{4})([-/.])\d{1,2}\2\d{1,2}(?:$|[T ])"  # 2024-01-05, 2024/1/5, "2024-01-05 08:30:00"
SPLIT_YEAR_LAST = r"^(\d{1,2})([-/.])(\d{1,2})\2(\d{4}|\d{2})(?:$|[T ])"  # 05/01/2024, 5.1.24
TIME_ONLY = r"\s*\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*(?:[AaPp]\.?[Mm]\.?)?\s*"  # 17:43, 0:00:00, 5:30 PM
SHARE_OF_FORM = 0.8  # a form this much of a column writes is the column's own; under it, the column has none


def date_forms(df, column_types, skip):
    """A date typed in another form than its column's (31/12/2023 among YYYY-MM-DD): it was read by guessing its order,
    and an export or a paste is the usual cause. Read as 2023-12-31 without a word in the chaos audit (AH-76), and
    03/04/2024 is April 3rd in London and March 4th in New York. -> (reasons, notes): a date in another form than the one
    80%+ of the column writes is flagged with how it was read, or both readings when its day and month could swap; a
    column with no such form gets one note naming its forms. Among dates written with the year last, one that can only
    be read in the order fewer of them show (12/25 where 25/12 is the rule) is flagged too: the column mixes two orders."""
    n = len(df)
    out, notes = [[] for _ in range(n)], [[] for _ in range(n)]
    for col, text in df.attrs.get("written", {}).items():
        if column_types.get(col) != "date":
            continue
        d = df[col][~skip].dropna()
        if len(d) < 5:
            continue
        t = text[d.index]
        if t.str.fullmatch(TIME_ONLY).all():  # times with no day: each was "read as" the day of the scan (AH-142)
            continue
        # a year alone has no day or month to misread, only less of the date: a film list's 241 "2017" among "26-Oct-12"
        # were each a Medium row (AH-142); written 5+ times it is one note, a few still each a date to check
        year = t.str.fullmatch(r"\d{4}")
        if year.sum() >= 5:
            notes[t.index[year][0]].append(Why(f"{col} gives only the year in {year.sum()} rows, read as 1 January", col))
            d, t = d[~year], t[~year]
            if t.empty:
                continue
        told = _orders(text.where(text.str.len() <= 64, ""))
        dayfirst = told[0] > told[1]  # as load read the column (a cell a date fits in, load._dates)
        yf, yl = t.str.extract(YEAR_FIRST), t.str.extract(SPLIT_YEAR_LAST)
        first, second = yl[0].astype(float), yl[2].astype(float)
        key = pd.Series("other", index=t.index)
        key[t.str.contains(r"[A-Za-z]{3}")] = "name"
        key[yl[0].notna()] = "?" + yl[1] + "?" + yl[1] + yl[3].str.len().map({2: "YY", 4: "YYYY"})
        key[yf[0].notna()] = "YYYY" + yf[1] + "MM" + yf[1] + "DD"
        other = key == "other"  # a form of its own: its shape, "20240105" -> 99999999
        # a run of digits is one 9: "0:00:00" and "17:43:00" are one form (388 Medium rows on eclipse_partial_2024, AH-142)
        key[other] = "shape:" + t[other].str.split(r"[T ]", n=1).str[0].str.replace(r"\d+", "9", regex=True)

        def label(k, t=t, key=key, dayfirst=dayfirst):
            if k.startswith("?"):
                a, b = ("DD", "MM") if dayfirst else ("MM", "DD")
                return f"{a}{k[1]}{b}{k[1]}{k[4:]}"
            return "the month's name" if k == "name" else f'like "{_short(t[key == k].iloc[0])}"' if k.startswith("shape:") else k

        count = key.value_counts()
        main = count.index[0]
        on = lambda i, d=d: f"{d[i]:%Y-%m-%d}"
        odd = key != main
        if count.iloc[0] >= SHARE_OF_FORM * len(key):
            for i in key.index[odd]:
                raw, k = _short(t[i]), key[i]
                if k.startswith("?") and first[i] <= 12 and second[i] <= 12 and first[i] != second[i]:
                    y = d[i].year
                    out[i].append(Why(f'{col} "{raw}" is written with the year last where the column writes {label(main)}: it '
                                      f'could be {y}-{int(second[i]):02d}-{int(first[i]):02d} or {y}-{int(first[i]):02d}-'
                                      f'{int(second[i]):02d}', col))
                    continue
                how = ("day-first" if first[i] > 12 else "month-first" if second[i] > 12 else "with the year last") \
                    if k.startswith("?") else "with the month's name" if k == "name" else "in another form" \
                    if k.startswith("shape:") else f"as {k}"
                out[i].append(Why(f'{col} "{raw}" is written {how} where the column writes {label(main)} (read as {on(i)})', col))
        elif len(count) > 1:
            forms = ", ".join(f"{label(k)} ({c})" for k, c in count.items())
            notes[key.index[odd][0]].append(Why(f"{col} writes its dates in {len(count)} forms: {forms}", col))
        # two regional orders in one column: each date only the rarer order can read is flagged, not read silently
        days, months = int((first > 12).sum()), int((second > 12).sum())
        if days and months:
            mine, theirs, many = ("month", "day", days) if dayfirst else ("day", "month", months)
            for i in key.index[(second > 12) if dayfirst else (first > 12)]:
                if not out[i]:
                    out[i].append(Why(f'{col} "{_short(t[i])}" is written {mine}-first where {many} of the column\'s dates can '
                                      f'only be {theirs}-first (read as {on(i)})', col))
    return out, notes


def far_dates(df, column_types, skip):
    """Date more than the column's whole span away from it (a 2018 sheet with 2084 in it; detectors.far_off, whose span
    leaves at least one date past each end). Birthdates spread over decades widen the span themselves. ponytail: misses a near miss like 2019 in a 2018 sheet - no rule knows that."""
    out = [[] for _ in range(len(df))]
    for col, t in column_types.items():
        d = df[col][~skip].dropna() if t == "date" else ()
        if t == "text":
            # a column of dates before 1900 is text (Excel keeps them so): read for this check alone, its type unchanged,
            # so a Nobel laureate born in 2862 among the 1800s is caught (blind round 23, AH-32)
            v = df[col][~skip & ~_blank(df[col])]
            # a cell too long for a date is none, unparsed: a crafted 100,000-character cell doubled the scan (AH-32 review)
            w = _dates(v.where(v.astype(str).str.strip().str.len() <= 40), wide=True) if len(v) >= 30 else v.iloc[:0]
            d = w.dropna() if len(w) and w.notna().mean() >= 0.9 and (w.dt.year < 1900).any() else ()
        if t == "number" and {"year", "yr"} & set(fairness._words(col)):
            # a year typed as a number (year, Yr, release_year, yearBuilt) is a date too: 2084 among 1981-2022 passed
            # (blind round 2, AH-178). The same span rule, in years; never "years_of_service" or "Yearly sales"
            x = df[col][~skip].dropna()
            if len(x) >= 30 and ((x == x.round()) & x.between(1000, 2200)).mean() >= 0.95:
                far, lo, hi = far_off(x.astype(float), least=pd.Timedelta(days=30) / pd.Timedelta(days=365.25))
                for i in x.index[far]:
                    out[i].append(Why(f"{col} {say(x[i])} is far outside the column's years ({lo:.0f} to {hi:.0f})", col))
            continue
        if len(d) < 30:
            continue
        far, lo, hi = far_off(d)
        for i in d.index[far]:
            out[i].append(Why(f"{col} {d[i]:%Y-%m-%d} is far outside the column's dates ({lo:%Y-%m-%d} to {hi:%Y-%m-%d})", col))
    return out


def sums(df, column_types, skip, held=None):
    """A column that is the sum of others in >= 95% of rows (Total = Fare + Tip + Tax): the other rows don't add up.
    Least squares finds the parts; kept only when every weight is 0 or 1 (a plain sum, found once, from the total's
    side). ponytail: plain sums only - a weighted rule (tax 8.25%) or a difference written as a sum of +1s only."""
    out = [[] for _ in range(len(df))]
    cols = numbers(column_types)
    done = _totals(df, cols, skip, out, held)
    x = df[cols][~skip]
    x = x.fillna({c: 0 for c in cols if x[c].isna().mean() >= SPARSE}).dropna()  # as _totals: a part blank on 95%+ of rows
    if len(cols) < 3 or len(x) < 20 * len(cols):  # few rows: least squares "fits" anything
        return out
    a = x.to_numpy(dtype=float)
    for t, col in enumerate(cols):
        if col in done:
            continue
        y, rest = a[:, t], np.delete(a, t, axis=1)
        w = np.linalg.lstsq(rest, y, rcond=None)[0]
        res = np.abs(y - rest @ w)
        keep = res <= np.quantile(res, 0.9)  # refit without the worst 10%: broken rows must not bend the weights
        w = np.linalg.lstsq(rest[keep], y[keep], rcond=None)[0]
        ones = np.round(w)
        if (np.abs(w - ones) > 0.02).any() or not set(ones) <= {0.0, 1.0} or ones.sum() < 2:
            continue
        got = rest @ ones
        bad = np.abs(y - got) > np.maximum(_cent(y), 1e-6 * np.abs(y))  # 1 cent (or the column's own last digit) + float slack
        # ...or within what rounding explains where 3+ rows miss so, as _totals: half of each part's last written digit
        # (none for whole numbers) and the total's own half. Coffee's ten scores to the hundredth summed to 86.85 for a
        # total_cup_points of 86.83: 47 rows called wrong (round 38, AH-64 try 1 review); one or two such misses are slips
        slack = sum(0.5 * 10.0 ** -d for d in (_decimals(rest[:, j]) for j in np.flatnonzero(ones)) if d)
        near = bad & (np.abs(y - got) <= slack + 0.5 * 10.0 ** -_decimals(y) + 1e-9 * np.abs(y))
        if near.sum() >= 3:
            bad &= ~near
        if bad.mean() > 0.05:
            continue
        part = [c for c, o in zip(np.delete(np.array(cols, dtype=object), t), ones) if o]
        bad &= ~_left_out(a, y - got, [t, *(cols.index(c) for c in part)])
        for i, v, g in zip(x.index[bad], y[bad], got[bad]):  # the total and every part: any one of them may be the slip
            out[i].append(Why(f"{col} {say(v)} does not add up: {' + '.join(part)} = {g:.10g}", col, *part))
    return out


SPARSE = 0.95  # a number column blank on this share of rows: where blank, it adds nothing to a total (AH-174)


# a header that says its column adds others up: "Total", "Total population", "All ages", "Sum", "TOTAL_CASES"
TOTAL_HEAD = re.compile(r"\b(?:totals?|sum|all)\b")


def named_totals(cols):
    """The columns whose header says they add others up; /profile names them before a scan (AH-169)."""
    return [c for c in cols if len(h := " ".join(re.sub(r"[_.]+", " ", str(c)).split()).lower()) <= 200 and TOTAL_HEAD.search(h)]


def _totals(df, cols, skip, out, held=None):
    """A column headed Total, Sum or All that is, to the cent, the other number columns added up, or the 3+ number
    columns beside it, on 95% of rows: the other rows don't add up. Round 37 missed Male + Female + Intersex = Total on 48
    rows and 8 age groups = Total on 200: least squares needs 20 rows a column, and an extra Year or Area column bends
    it. An exact sum cannot hold by chance on 10 rows with something to add, so no such minimum; two parts are pairs'.
    Capped in sheet order (20 totals, 40 columns a side), never by a clock: the same sheet gives the same answer.
    Adds its reasons to out, and the rows each held on to held (see confirm); -> the totals it explained, so least squares
    does not judge them again (AH-55)."""
    done, order, nums = set(), list(df.columns), {c: k for k, c in enumerate(cols)}
    named = named_totals(cols)
    # ...and any other number column, as the sum of 3+ beside it: a "Budget" or a "Field4" that adds up Salaries + Rent +
    # Travel was judged only by least squares, 20 rows a column, so on 60 rows its slip was missed and a real Travel -123
    # whose row adds up got "likely 123" (AH-150). Same flags under other headers (test_schema_agnostic)
    heads = named + [c for c in cols if c not in named]
    rows = df.index[~skip]
    a = df.loc[rows, cols].to_numpy(dtype=float) if len(cols) > 3 else None
    # a part blank on 95%+ of rows adds nothing there: read as 0, so the rule is judged on the rows it is blank on and
    # the 0-part rule below settles the rest. Left blank, every try with it had no rows: a total beside a part blank on
    # 99.9% of rows was never judged, and its 51 for 15 was missed (blind round 1, AH-174)
    b = None if a is None else np.where(np.isnan(a) & (np.isnan(a).mean(axis=0) >= SPARSE), 0.0, a)
    halves = {}  # as pairs: a column of whole numbers is exact, one written to d decimals off by up to half its last digit
    half = lambda c: halves.setdefault(c, 0.0 if (d := _decimals(a[:, nums[c]])) == 0 else 0.5 * 10.0 ** -d)
    for col in heads[:20] if a is not None else ():
        y, at, tries = a[:, nums[col]], order.index(col), [[c for c in cols if c != col]] if col in named else []
        own = 0.5 * 10.0 ** -_decimals(y)
        for step in (-1, 1):  # the number columns right beside it, nearest first, up to the first other column
            run, j = [], at + step
            while 0 <= j < len(order) and order[j] in nums and len(run) < 40:
                run.append(order[j])
                j += step
            ks = range(3, len(run) + 1)
            if col not in named and len(run) >= 3:  # a running sum that meets the column on under 10 rows is no try: every
                # column of 30,000 rows x 45 tried every run in full took 100 s (AH-150)
                tol = np.maximum(0.011, 1e-6 * np.abs(y))[:, None] + np.cumsum([half(c) for c in run]) + own
                hit = (np.abs(y[:, None] - np.cumsum(b[:, [nums[c] for c in run]], axis=1)) <= tol).sum(axis=0)
                ks = [k for k in ks if hit[k - 1] >= 10]
            tries += [run[:k] for k in ks]
        best = None
        # the exact cent first; then, where it fails, what the rounding of the parts and the total explains, never looser:
        # ten parts written to 1 decimal and a total rounded from the unrounded ones miss by up to 0.55 (round 38, AH-64)
        for loose in (False, True):
            for parts in tries:  # one column more each try: a sum of a few thousand rows, not a copy of the sheet
                judged = None
                for _ in range(2):  # a second pass judges the candidate again without the parts the first showed are none
                    if len(parts) < 3:
                        break
                    p = b[:, [nums[c] for c in parts]]
                    ok = ~np.isnan(y) & ~np.isnan(p).any(axis=1)
                    if not (p[ok] != 0).any(axis=0).all():  # every part counts somewhere
                        break
                    got = p[ok].sum(axis=1)
                    tol = np.maximum(0.011, 1e-6 * np.abs(y[ok]))  # 1 cent + float slack, as sums
                    if loose:  # half of each part's last written digit (none for whole numbers), and the total's own half
                        tol = np.maximum(tol, sum(half(c) for c in parts) + own + 1e-9 * np.abs(y[ok]))
                    bad = np.abs(y[ok] - got) > tol
                    # a part that is 0 in most rows shows it belongs only on the rows where it is not. One that adds up on
                    # none of them is no part: an "Adjustment" beside the total, 0 in 96% of rows, "held" on the rest and
                    # flagged its 16 other rows (AH-55 review); left in, it was named in the sentence, "Food + Drinks + Merch
                    # + Adjustment" (AH-55 review 3), so the candidate is judged again without it. One that adds up on most
                    # of them (all but 20%, or under 5 rows all but a minority) is a part, every row judged: Refunds on 9-14
                    # of a stand's 90 days, a slip on one found. Between (1 of 2 days adds up) nothing shows which: those
                    # rows are left unjudged, never called wrong
                    none, judged = [], np.ones(len(bad), dtype=bool)
                    for k in np.flatnonzero((p[ok] != 0).mean(axis=0) < 0.2):
                        on = p[ok][:, k] != 0
                        if not (~bad[on]).any():
                            none.append(parts[k])
                        elif bad[on].sum() > (0.2 * on.sum() if on.sum() >= 5 else (on.sum() - 1) // 2):
                            judged &= ~on
                    if not none:
                        break
                    parts, judged = [c for c in parts if c not in none], None
                if judged is None:
                    continue
                live, bad = (p[ok] != 0).any(axis=1) & judged, bad & judged
                share = bad[judged].mean() if judged.any() else 1.0
                if (~bad[live]).sum() < 10 or share > 0.05 or (best and share >= best[0]):
                    continue
                # ...and once a rule holds, a miss within that rounding is rounding where 3+ rows miss so: coffee's ten
                # scores to the hundredth summed to 86.85 for a total of 86.83 on 47 rows (round 38, AH-64 try 1 review);
                # one or two such misses are still each a slip
                near = bad & (np.abs(y[ok] - got) <= sum(half(c) for c in parts) + own + 1e-9 * np.abs(y[ok]))
                slip = bad & ~near if near.sum() >= 3 else bad
                best = (share, sorted(parts, key=order.index), rows[ok][judged & ~slip], rows[ok][slip], y[ok][slip], got[slip])
            if best:
                break
        if best:
            done.add(col)
            for i, v, g in zip(*best[3:]):
                out[i].append(Why(f"{col} {say(v)} does not add up: {' + '.join(best[1])} = {g:.10g}", col, *best[1]))
            if held is not None:  # a sum: changing any one of its cells breaks it
                confirm(held, len(df), best[2], f"{col} = {' + '.join(best[1])}", [col, *best[1]])
    return done


STEP_BAND = 5  # a ratio band at most this wide (high end / low end): a x10 slip of one cell always leaves it
STEP_ROWS = 20  # rows where both columns hold a number other than 0, to read the band from
BAND_ROWS = 5000  # rows a ratio band is read from, evenly spaced (see in_step)


def _reads(grid, cols):
    """{column: the columns its formulas read on their own row, all the way down}, from the pane's R1C1 text: a value
    worked out from another repeats it, so it is no witness for it."""
    out = {}
    for row in grid or ():
        for j, f in enumerate(row):
            if f:
                out.setdefault(cols[j], set()).update(cols[j + int(k or 0)] for k in re.findall(r"(?<![\w\]])RC(?:\[(-?\d+)\])?", str(f))
                                                      if 0 <= j + int(k or 0) < len(cols))
    for seen in out.values():
        todo = list(seen)
        while todo:
            for d in out.get(todo.pop(), ()):
                if d not in seen:
                    seen.add(d)
                    todo.append(d)
    return out


def in_step(df, column_types, skip, limits, reads, held):
    """A typo changes one cell. A value past its usual limits that keeps its usual ratio to another column on its row,
    itself past its own usual limits there, is a big row, never a slip: an executive's 40,000 bonus made Gross Pay big,
    and Federal Tax, 27% of it as on that person's other periods, was Medium beside it (AH-208, episodes 6-8: 3 traps
    and 6 valid cells); a house fire's approval kept its 92% of a big claim. Confirmed, as a row that adds up is (see
    confirm): worth a check, never a vote or a fix. The ratio band is read where both columns hold a number other than
    0 (STEP_ROWS of them), from the 1st to the 99th percentile, one sign, at most STEP_BAND wide: a x10 slip of either
    cell always leaves it. Never a witness worked out from the value itself (=Hours*Rate repeats an 800 hours typed for
    80), nor a column of formulas on that row (a formula's value is never judged here)."""
    cols = [c for c in numbers(column_types) if limits.get(c) and limits[c][0] is not None and limits[c][1] is not None][:64]
    if len(cols) < 2:
        return
    rows = df.index[~skip]
    a = df.loc[rows, cols].to_numpy(dtype=float)
    lo, hi = np.array([limits[c][0] for c in cols]), np.array([limits[c][1] for c in cols])
    with np.errstate(invalid="ignore"):
        out = (a < lo) | (a > hi)
    nz = np.isfinite(a) & (a != 0)
    # the band from at most BAND_ROWS rows, evenly spaced, so 64 columns that all move together stay a second's work on
    # 100,000 rows (10 s reading every row), and the same sheet gives the same band on any PC
    seen = np.unique(np.linspace(0, len(a) - 1, min(len(a), BAND_ROWS)).astype(int))
    for j, col in enumerate(cols):
        if not (past := np.flatnonzero(out[:, j])).size:
            continue
        # a witness must be past its own limits on one of these rows: that settles nearly every pair before the band is
        # read (100,000 rows x 64 columns took 8 s reading every band)
        for k in np.flatnonzero(out[past].any(axis=0)):
            other = cols[k]
            if k == j or col in reads.get(other, ()):
                continue
            both = seen[nz[seen, j] & nz[seen, k]]
            if len(both) < STEP_ROWS:
                continue
            q1, q99 = np.quantile(a[both, j] / a[both, k], [0.01, 0.99])
            if q1 * q99 <= 0 or max(abs(q1), abs(q99)) > STEP_BAND * min(abs(q1), abs(q99)):
                continue
            # ...and 1% either side: ratios of amounts rounded to the cent wobble, and a band's own end (a 27% rate on a
            # few periods) fell outside its 99th percentile by 1e-7
            s, cand = np.sign(q1), past[nz[past, j] & nz[past, k] & out[past, k]]
            r = a[cand, j] / a[cand, k]
            at = cand[(s * r >= min(s * q1, s * q99) / 1.01) & (s * r <= max(s * q1, s * q99) * 1.01)]
            if len(at):
                confirm(held, len(df), df.index.get_indexer(rows[at]), f"{col} keeps its usual share of {other}", [col])


def confirm(held, n, at, rule, pinned):
    """held[col] += (rows, rule): the rows where a rule of the row's own arithmetic holds, and the cells it pins, the
    ones no single change could leave the rule holding on. The chaos audit (2026-10-30, AH-74): an HR sheet's real top
    earner, AnnualSalary 1150000 + Bonus 400000 = TotalComp 1550000, was Medium with "Bonus ... (likely 4000)", a card
    that would break the row's own sum. limits_detector reads this: such a value is confirmed, never a vote or a fix."""
    m = np.zeros(n, dtype=bool)
    m[np.asarray(at, dtype=int)] = True
    for c in pinned:
        held.setdefault(c, []).append((m, rule))


ROUNDED = 3  # rows a held exact rule misses within its columns' rounding: that many are rounding, never slips (AH-211)
LEFT_OUT = 0.8  # a column 0 or blank on this share of rows can be a part a rule holding on 95% of rows never sees


def _left_out(a, miss, rule):
    """-> per row: the rule misses by exactly another cell of the row (to the cent, either sign), from a column 0 or blank
    on LEFT_OUT of the rows and not in the rule: a part the rule leaves out, never a slip. A payroll's Gross Pay =
    Regular Pay + Overtime Pay held on 95% of rows because Bonus is 0 on all but 30 of 640; on those 30, "Gross Pay does
    not add up" named 95 valid cells, each missing by exactly its Bonus (AH-208, adversarial episode 4). A rule that held
    with that part in it is another rule: only columns outside this one count."""
    hit = np.zeros(len(miss), dtype=bool)
    with np.errstate(invalid="ignore"):
        for k in range(a.shape[1]):
            v = a[:, k]
            if k in rule or (np.nan_to_num(v) == 0).mean() < LEFT_OUT:
                continue
            hit |= (v != 0) & (np.abs(np.abs(miss) - np.abs(v)) <= np.maximum(_cent(v), 1e-6 * np.abs(v)))
    return hit


def _restated(grid, order, cols, rows):
    """-> f(rule's columns) = per row: one of the rule's cells holds a formula that reads all its other columns, so the
    rule is that formula said again and its row can never break it by a slip: only the formula's own rounding or its
    other inputs move it. A pharmacy's Days Supply =ROUND(Qty/(Units per Dose x Doses per Day),0) made "Qty = Doses per
    Day x Days Supply", and a liquid's 5 mL a dose broke it on 4 valid cells; a box score's FG% =ROUND(FGM/FGA,3) made
    FGM = FGA x FG% (AH-211 episodes 18 and 19). A typed value there is still judged (and the formula check names it)."""
    reads = _reads(grid, order)
    worked = {c: np.array([row[j] is not None for row in grid])[rows] for j, c in enumerate(order) if c in reads and c in cols}

    def on(rule):
        named = {cols[k] for k in rule}
        hit = np.zeros(int(rows.sum()), dtype=bool)
        for c in named & set(worked):
            if named - {c} <= reads[c]:
                hit |= worked[c]
        return hit
    return on


def _cent(x):
    """How near counts as equal "to the cent": a cent, or one unit of the column's own last digit when it is written finer.
    College admissions' rates, all under 0.06, were each within a cent of any product of two others: 474 Medium rows and
    10 wrong "likely" values from rules no column follows (blind round 37, AH-54)."""
    return min(0.011, 1.1 * 10.0 ** -_decimals(x))


def _decimals(x):
    """How many decimals a column is written with: the fewest that hold 95% of its values (0 = whole numbers)."""
    x = x[np.isfinite(x)]
    if not len(x):  # no number on the rows read (all on a skipped row): the mean of nothing was an HTTP 500 (fuzz, 2026-11-16)
        return 0
    return next((d for d in range(7) if (np.abs(x - np.round(x, d)) < 1e-9).mean() >= 0.95), 6)


def pairs(df, column_types, skip, limits=None, held=None, grid=None):
    """A column that is two others multiplied or added in >= 95% of rows (Line Total = Qty x Unit Price, Net New =
    New + Churned), or two multiplied after a 0-1 discount (Units x Unit Price x (1 - Discount)): the other rows don't
    add up. Tried pair by pair, so a x10 typo elsewhere can't bend it the way it
    bends sums' least squares, and small sheets (48 months) are checked too. To the cent, like sums; both columns must
    vary (x 1, or x a 0/1 flag, is no rule). Pairs are tried on a 64-row sample first, so a 50-column sheet stays fast.
    -> (reasons, fixes, fits). A broken row with exactly ONE cell outside its usual range gets that cell solved from the
    other two (Units -5 with Total 170.43 = Units x 2.99 -> 57) when the answer is a usual value written like its
    column: exact, where the pane would otherwise offer the median. Two odd cells: the arithmetic can't say which.
    fits[i][col](v): the rule holds on row i, to the cent or within its columns' rounding, with that cell set to v.
    held: filled with the rows each rule holds on (see confirm). grid: the pane's R1C1 formulas (see _restated)."""
    out, fix, fits = [[] for _ in range(len(df))], [{} for _ in range(len(df))], [{} for _ in range(len(df))]
    cols = numbers(column_types)
    a = df[cols][~skip].to_numpy(dtype=float)
    index = df.index[~skip]
    restated = _restated(grid, list(df.columns), cols, ~skip)
    if len(cols) < 3 or len(a) < 20:
        return out, fix, fits
    bounds = lambda j: (limits or {}).get(cols[j]) or (None, None, None, None)
    usual = lambda j, v: (bounds(j)[0] is None or v >= bounds(j)[0]) and (bounds(j)[1] is None or v <= bounds(j)[1])
    # the first 64 varying columns: pairs x fractions grows with the cube of the width (160 columns took 20 s, 2026-10-16)
    vary = [j for j in range(len(cols)) if len(np.unique(a[:, j][~np.isnan(a[:, j])])) >= 3][:64]
    cent = np.array([_cent(a[:, j]) for j in range(len(cols))])  # 1 cent, or the column's own last digit (AH-54)
    near = lambda y, got, c: np.abs(y - got) <= np.maximum(c, 1e-6 * np.abs(y))  # + float slack
    # ...or within what rounding can explain, where the exact rule does not hold: a race time = laps x an average lap time
    # written to the cent, so 16 laps carry 16 x 0.005 s (marbles, blind round 23: never learnt, a 26.1 typed 261 passed).
    # A column of whole numbers is exact (laps, units); one written to d decimals is off by up to half its last digit
    half = np.array([0.0 if (d := _decimals(a[:, j])) == 0 else 0.5 * 10.0 ** -d for j in range(len(cols))])
    # ...and where rounding explains it, the total is rounded too: a gross written to the dollar from one with cents. Its
    # own half unit, whole numbers included: Broadway's gross missed avg ticket price (to the cent) x seats by 1.0004-1.009
    # times the half cent per seat, 62 Medium rows in blind round 37 (AH-54)
    own = np.array([0.5 * 10.0 ** -_decimals(a[:, j]) for j in range(len(cols))])

    def rounded(y, cs, op, rows):
        if len(cs) != 2:
            return None  # the discount rule stays exact
        p, q = (a[rows, c] for c in cs)
        slack = half[cs[0]] * np.abs(q) + half[cs[1]] * np.abs(p) if op is np.multiply else np.full(len(p), half[cs[0]] + half[cs[1]])
        return slack, 1e-9 * np.abs(y)
    sample = a[:64]
    rules = [((p, q), f"{cols[p]} {sign} {cols[q]}", op) for (p, q), (sign, op) in
             itertools.product(itertools.combinations(vary, 2), (("×", np.multiply), ("+", np.add)))]
    # order sheets: Units x Unit Price x (1 - Discount). The fraction column is 0 to 1 in 99% of rows, so one
    # Discount typed 25 for 0.25 doesn't hide the rule it breaks
    fracs = [j for j in vary if np.nanmin(a[:, j]) >= 0 and np.nanquantile(a[:, j], 0.99) < 1]
    rules += [((p, q, f), f"{cols[p]} × {cols[q]} × (1 - {cols[f]})", lambda x, y, z: x * y * (1 - z))
              for p, q in itertools.combinations([j for j in vary if j not in fracs], 2) for f in fracs]
    for cs, said, op in rules:
        got_s = op(*(sample[:, c] for c in cs))
        hits = near(sample, got_s[:, None], cent[None, :]).mean(axis=0)
        if (r := rounded(sample, cs, op, slice(0, len(sample)))) is not None:
            tol = r[0][:, None] + own[None, :] + r[1]
            hits = np.maximum(hits, (np.abs(sample - got_s[:, None]) <= tol).mean(axis=0))
        for t in np.flatnonzero(hits >= 0.8):
            if t in cs:
                continue
            y, got = a[:, t], op(*(a[:, c] for c in cs))
            ok = ~np.isnan(y) & ~np.isnan(got)
            # judged where the numbers aren't all zero: 0 = 0 x anything made a rule of three TV-spot columns that were 0
            # in 91% of weeks - it held in 64 of the 120 weeks with spots (real sheet, 2026-10-16)
            live = ok & ((y != 0) | (got != 0))
            # ...and a sum where every term carries weight: tornado records' sn (0/1) "= ns + f3" held in 97% of rows
            # only because f3, a third county's code, is 0 in 97.5% of them (648 Medium rows, blind round 37, AH-54).
            # A sum must also hold on the rows where none of its terms is 0: on 5 of them at least, all but 5% or one.
            # The tornado rule breaks on nearly all of f3's own rows; an honest New + Reactivated = Net adds, Reactivated
            # 0 in 80-90% of 60 months, holds on its 6-12 (a 20-row minimum there lost the rule and its slip, AH-54 review)
            full = ok & np.all([a[:, c] != 0 for c in cs], axis=0) if op is np.add else live
            holds = lambda good: ((good & (y != 0)).sum() >= 20 and (good & live).sum() >= 0.95 * live.sum()
                                  and (good & full).sum() >= 5 and (full & ~good).sum() <= max(1, 0.05 * full.sum()))
            good = ok & near(y, got, cent[t])
            r = rounded(y, cs, op, slice(None))
            within = ok & (np.abs(y - got) <= r[0] + own[t] + r[1]) if r is not None else good
            if not holds(good):  # the exact rule first; then what rounding explains, never looser than that
                good = within
                if not holds(good):
                    continue
            elif (within & ~good).sum() >= ROUNDED:
                # ...and once the exact rule holds, a miss within that rounding is rounding where ROUNDED+ rows miss so,
                # as _totals: FGM = FGA x FG%, FG% =ROUND(FGM/FGA,3), held to the cent on 96% of a box score's rows, and
                # 17 rows with 20+ attempts missed by up to 0.0135 (51 valid cells, AH-211 episode 18); one or two such
                # misses are still each a slip
                good = within
            if held is not None:
                # a cell is pinned where no change to it alone keeps the rule: every cell of a sum; the total of a product,
                # and a factor only where the other factors are not 0 (0 x anything is 0: Qty 0 says nothing of the price)
                rule, named = f"{cols[t]} = {said}", [cols[t], *(cols[c] for c in cs)]
                confirm(held, len(df), index[np.flatnonzero(good & live)], rule, named if op is np.add else named[:1])
                if op is not np.add:  # the factors of Units x Price x (1 - Discount): Units, Price, 1 - Discount
                    f = [a[:, c] if k < 2 else 1 - a[:, c] for k, c in enumerate(cs)]
                    for k, c in enumerate(cs):
                        others = np.all([g != 0 for m, g in enumerate(f) if m != k], axis=0)
                        confirm(held, len(df), index[np.flatnonzero(good & live & others)], rule, [cols[c]])
            for i in np.flatnonzero(ok & ~good & ~_left_out(a, y - got, [t, *cs]) & ~restated((t, *cs))):
                out[index[i]].append(Why(f"{cols[t]} {say(y[i])} does not add up: {said} = {got[i]:.10g}", cols[t], *(cols[c] for c in cs)))
                odd = [j for j in (t, *cs) if not usual(j, a[i, j])]
                if len(odd) != 1:
                    continue
                j = odd[0]
                with np.errstate(divide="ignore", invalid="ignore"):
                    if j == t:
                        v = got[i]
                    elif op is np.add:
                        v = y[i] - a[i, cs[1] if j == cs[0] else cs[0]]
                    elif len(cs) == 3 and j == cs[2]:  # the fraction: 1 - Total / (Units x Price)
                        v = 1 - y[i] / (a[i, cs[0]] * a[i, cs[1]])
                    else:  # one factor: Total / the others
                        v = y[i] / np.prod([a[i, c] if k < 2 else 1 - a[i, c] for k, c in enumerate(cs) if c != j])
                d = _decimals(a[:, j])
                if np.isfinite(v) and abs(v - np.round(v, d)) < 0.01 * 10.0 ** -d + 1e-9 * abs(v) and usual(j, np.round(v, d)):
                    fix[index[i]][cols[j]] = float(f"{np.round(v, d):.10g}")

                    def fit(w, i=i, j=j, t=t, cs=cs, op=op):
                        row = a[i].copy()
                        row[j] = w
                        y1, got1 = row[t], op(*(row[c] for c in cs))
                        if near(y1, got1, cent[t]):
                            return True
                        if len(cs) != 2:
                            return False
                        p, q = row[cs[0]], row[cs[1]]
                        slack = half[cs[0]] * abs(q) + half[cs[1]] * abs(p) if op is np.multiply else half[cs[0]] + half[cs[1]]
                        return bool(abs(y1 - got1) <= slack + own[t] + 1e-9 * abs(y1))
                    fits[index[i]][cols[j]] = fit
    return out, fix, fits


def _one_edit(a, b):
    """a and b differ by one wrong letter, two neighbours swapped, or one letter typed twice ("NOTT DONE", "itraconazolle",
    4 of 9 blind misspellings, 2026-10-16). Any other added or dropped letter is left out on purpose: too often a different
    word (Laptop/Laptops, Sara/Sarah, Jon/John)."""
    long, short = (a, b) if len(a) > len(b) else (b, a)
    if len(long) == len(short) + 1:
        return any(long[k] == long[k - 1] and long[:k] + long[k + 1:] == short for k in range(1, len(long)))
    if a == b or len(a) != len(b):
        return False
    d = [k for k in range(len(a)) if a[k] != b[k]]
    return len(d) == 1 or (len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]])


def _dropped(rare, usual, vowel=False):
    """rare is usual with one letter left out inside a word ("Grmany", "parietl", "Nuclear Enrgy": 4 of 6 misspellings
    blind round 22 planted in real tables were missed, AH-23). Never a word's first or last letter (Laptop/Laptops,
    Sara/Sarah, "Phone Case"/"Phones Case": a different word or a plural) and never a space; vowel: only a, e, i, o, u.
    Measured on the 10,000 commonest English words: one inner letter dropped gives another word for 2.2% (vowel) and 5.8%
    (consonant) of 5-letter words - one wrong letter, which _one_edit allows, does for 60.8% of them."""
    if len(usual) != len(rare) + 1:
        return False
    return any(usual[:k] + usual[k + 1:] == rare and usual[k].isalpha() and usual[k - 1] not in " -" and usual[k + 1] not in " -"
               and (not vowel or usual[k] in "aeiou") for k in range(1, len(usual) - 1))


def _swapped(a, b):
    """a and b are the same letters with two neighbours swapped ("rian" for "rain")."""
    d = [k for k in range(len(a)) if len(a) == len(b) and a[k] != b[k]]
    return len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]]


def _misspelt(rare, usual):
    """Is rare (casefolded, 1-2 rows) a slip of usual (5+ rows, 5x as common)? 5+ letters each: one wrong letter, two
    neighbours swapped, a letter typed twice (_one_edit) or one inner letter dropped (_dropped). 4 letters: only two
    neighbours swapped (4.9% of 4-letter words have such a twin: form/from) or a vowel dropped from a 5-letter label
    ("japn" for "japan": 7.2%, plan/plain). Never one wrong letter in 4 (89%: Iran/Iraq, Mark/Mary), a consonant
    dropped (14.8%: Chad/Chard) or anything in 3 (Jon/John)."""
    # words joined by hyphens are read word by word: "Month-to-mnoth" was never read as words (blind round 36), and the
    # word that differs is judged by its own length, so a region "Russia-SW" is no slip of "Russia-SE" (round 22, AH-32).
    # So are words between any other marks: "East Aisa & Pacific", "ulrta_low_sulfur", "Irish Poundd (Punt)" were never
    # judged (blind round 1, AH-174). The marks and digits between them must agree: "Room 1" is no slip of "Room 11"
    if not (rare + usual).replace(" ", "").isalpha():
        a, b = re.split(r"([\W\d_]+)", rare), re.split(r"([\W\d_]+)", usual)
        diff = [(k, x, y) for k, (x, y) in enumerate(zip(a, b)) if x != y]  # words at even places, marks at odd
        return len(a) == len(b) and len(diff) == 1 and diff[0][0] % 2 == 0 and _misspelt(*diff[0][1:])
    word = lambda w, lo: lo <= len(w) <= 60 and w.replace(" ", "").isalpha()
    if word(rare, 5) and word(usual, 5):
        return _one_edit(rare, usual) or _dropped(rare, usual)
    if len(rare) == 4 and rare.isalpha():
        return (len(usual) == 4 and usual.isalpha() and _swapped(rare, usual)) or (
            len(usual) == 5 and usual.isalpha() and _dropped(rare, usual, vowel=True))
    return False


def _short_for(short, label):
    """Is short a short form of label (both casefolded)? See spellings()."""
    w, v = short.split(), label.split()
    if len(w) > 1:
        return len(w) == len(v) and all(b.startswith(a) for a, b in zip(w, v))
    if label.startswith(short):
        return len(short) <= 4
    # a contraction keeps the word's first and last letters (Std, Mgmt, Dept, Bldg): "Iran" is not one of "Ireland"
    rest = iter(label[1:])
    return (len(short) <= 4 and short[0] == label[0] and short[-1] == label[-1]
            and sum(ch in "aeiou" for ch in short[1:]) <= 1 and all(ch in rest for ch in short[1:]))


# a column of people's names: one-slip twins are honest there (Thomson/Thompson, Philips/Phillips, Mathew/Matthew).
# Measured on the 10,000 commonest US surnames and first names (AH-24): one inner letter dropped gives another real
# name for 21% of surnames and 37% of first names (4.8% of common words), a letter typed twice 4% and 13% (0.3%)
PERSON = {"surname", "surnames", "forename", "forenames", "firstname", "lastname", "fullname"}
# a role that is a person on its own ("Employee", "Sales Rep"): AH-24 try 1 read only "<role> name", so Employee, Patient,
# Driver, Author and Customer columns still called Thomson a misspelling of Thompson (Council A)
ROLE = {"customer", "client", "employee", "emp", "staff", "patient", "student", "pupil", "contact", "person", "member", "user",
        "owner", "manager", "author", "applicant", "candidate", "teacher", "doctor", "driver", "rep", "buyer", "player",
        "guest", "passenger", "mother", "father", "spouse", "tenant", "volunteer", "attendee", "participant", "respondent",
        "recipient", "sender", "holder",
        # AH-26 (Council A, AH-24 try 2: these still called Thomson a misspelling of Thompson)
        "physician", "nurse", "assignee", "salesperson", "athlete", "coach", "instructor", "reviewer"}
# "<this> name" is a person's; on their own these are often not ("Agent" is a browser's in a log, a "Partner" a company)
PERSON_NAME = ROLE | {"first", "last", "given", "family", "middle", "full", "maiden", "nick", "christian", "legal", "preferred",
                      "agent", "seller", "parent", "partner", "donor"}
# a winner, a champion, a laureate or a rider is a person only beside a person's age, sex or birth date, like a plain
# "Name": a Tour de France winner (age, born) and a Nobel laureate (gender, birth_date) are people (blind round 23 called a
# winner's name a misspelling), but a World Cup's winner is a country, an election's a party, a product test's a phone and
# an insurance policy's rider a cover ("Accidentl Death"): all silenced as people (AH-32 review)
BESIDE = {"winner", "winners", "champion", "champions", "laureate", "laureates", "rider", "riders"}
# a customer or client that is a company: its names are checked like any label
COMPANY = {"inc", "ltd", "llc", "llp", "corp", "corporation", "co", "company", "gmbh", "plc", "group", "pty", "ag", "sa", "bv"}


# a person's age, in years: "Age", "Age (years)", "Patient age". A stock's "Age (days)" or "Stock age" is not (AH-26)
YEARS = {"age", "years", "year", "yrs", "yr", "in"}


def _person_name(col, columns, labels):
    """A column of people's names: Surname, LastName, "First name", "Customer name", "Name of patient", "Name (Last,
    First)", a role on its own ("Employee", "Sales Rep") unless its labels are companies, and a plain "Name" only beside a
    person's age, sex or birth date (Titanic): on its own it named products, cities, car models and airports (Council A:
    all 3 plain "name" columns in blind round 22's 59 real tables). "Product name", "Company name", "City" are labels."""
    w = fairness._words(col)
    if PERSON & set(w):
        return True

    role = len(w) <= 2 and set(w) & BESIDE and set(w) <= BESIDE | {"name", "names"}

    def personal(c):
        cw = fairness._words(c)
        if set(cw) & {"sex", "gender", "dob", "birth", "birthday", "birthdate"}:
            return True
        # ...or, for a Rider, Winner or Champion, a column that is a nationality and nothing else: a cyclist roster (Rider,
        # Team, Nationality) called "Thomson" a misspelling of "Thompson" (AH-51). Not for a plain "Name": a ship's
        # beside its flag's Nationality, a dish's beside its cuisine's, lost their spelling check; nor "Host nationality"
        # beside a World Cup's winners (AH-51 review). A "Country" alone is a place
        if role and cw in (["nationality"], ["nationalities"], ["citizenship"]):
            return True
        return "age" in cw and (set(cw) <= YEARS or (len(cw) == 2 and cw[1] == "age" and cw[0] in ROLE))
    if w in (["name"], ["names"]) or role:
        return any(personal(c) for c in columns if c != col)
    named = bool(w) and w[-1] in ("name", "names") and len(w) > 1 and w[-2] in PERSON_NAME
    named |= len(w) > 1 and w[0] in ("name", "names") and (w[1] in PERSON_NAME or w[1:2] == ["of"] and w[2:3] and w[2] in PERSON_NAME)
    if named:
        return True
    if w and len(w) <= 2 and (w[-1] in ROLE or w[-2:] == ["assigned", "to"]):
        companies = sum(bool(set(fairness._words(v)) & COMPANY) for v in labels)
        return companies < max(1, len(labels) / 10)
    return False


USUAL = 2000  # the commonest labels a misspelling guess compares with: bounds the work on a crafted list, in count order


def spellings(df, column_types, skip):
    """Same category typed differently ("Sales" / "sales " / "SALES"): a stray space splits SUMIFS, COUNTIF and pivots (they ignore case).
    Only case/space differences, only in category-like columns (<= 50 distinct). Every spelling but the right one is
    flagged, however common ("employed" 77 times next to "Employed" 82): the right one is written like the column's other
    labels (capitalised or not), then the most common. A common second spelling in the column's own style is one note
    for the column (AH-64). Plus possible misspellings: a rare word (1-2 times) one slip from
    a usual one (5+ times and 5x as common): one letter wrong, two swapped, one typed twice or one dropped inside a word,
    both 5+ letters; at 4 letters only a swap or a dropped vowel (_misspelt) - no digits ("A101"/"A102" are codes), no
    short names (Mark/Mary). -> (reasons, {col: usual spelling}, misspelling reasons (worth a check, not "wrong"),
    {col: usual spelling} for misspellings - a guess, never auto-fixed, {col: usual} when 5x as common - auto-fixable)."""
    n = len(df)
    out, fix, missed = [[] for _ in range(n)], [{} for _ in range(n)], [[] for _ in range(n)]
    maybe, exact = [{} for _ in range(n)], [{} for _ in range(n)]
    for col, t in column_types.items():
        if t != "text":
            continue
        s = df[col][~skip].dropna().astype(str)
        # formula-like text is never a "spelling": Excel reads a full-width ＝ as = too (AH-160: its capitals fix was a formula)
        s = s[(s.str.strip() != "") & ~s.str.lstrip().str[:1].isin(FORMULA_START)]
        # category-like: 50 labels; and for a misspelling guess (below), any number that repeat 10 times each on average -
        # 68 countries over 2,530 bars of chocolate hid "Frnace", 51 menu items over 4,622 orders "Chiken Bowl" (blind
        # rounds 36 and 23, AH-32), and past 200 labels "Hoorror", "Abgentina", "Bankign" (blind round 2, AH-178). Not
        # for capitals: 1,222 Medium rows of "Yes"/"yes" and "9th place Match" came with it
        many = s.nunique() > 50
        if many and len(s) < 10 * s.nunique():
            continue
        keys = s.map(lambda v: " ".join(v.split()).casefold())
        capital = lambda v: v.strip()[:1].isupper()
        labels = list(s.drop_duplicates())
        up = sum(map(capital, labels))
        caps = up >= len(labels) / 2  # the column's style: most labels start with a capital
        # ...and a style only when 2/3 of the labels share it: codes (domus, New, MusCal, aim82NM) have none, and "Misc" 38
        # times beside "misc" 207 was "off style", a card a row auto-applied (blind round 2, AH-177)
        styled = max(up, len(labels) - up) >= 2 * len(labels) / 3
        rights, spelt = {}, {}  # label -> its right spelling; label -> {raw spelling: rows}
        for raw, c in s.value_counts().items():  # one count per column, not per label: 400 columns took 20 s (2026-10-16)
            spelt.setdefault(" ".join(raw.split()).casefold(), {})[raw] = c
        for key, counts in spelt.items():
            right = rights[key] = max(counts, key=lambda v: (capital(v) == caps and v == " ".join(v.split()), counts[v]))
            if NO_VALUE_WORD.fullmatch(key):  # "NA" beside "na" both say no value: 3,213 Medium rows on one real table (AH-142)
                continue
            for raw, c in counts.items():
                if raw == right or many:
                    continue
                # a second spelling the source writes 5+ times, itself in the column's style (capitalised like it, clean
                # spaces), is its way of writing: "Collins glass" 150 times beside "Collins Glass" 200 was 150 Medium
                # rows (round 38, AH-64). One note for the column, both spellings and their counts; a rare one, or one
                # off the column's style ("employed" 77 times beside "Employed" 82), is still each a slip. A count, not
                # a share: on the round 22-38 sheets every such variant written 4+ times was the source's own, however
                # rare beside the usual one (wildlife strikes' ARRIVAL 7 of 20,000, cocktails' Highball Glass 75 beside
                # 302, under AH-64's third), and one written 2-4 times stays a slip to check (AH-67)
                # also one note, written 5+ times: more often than the "right" one (LazyData "true" 5,156 beside "TRUE"
                # 790: each card rewrote a correct cell to the minority's form), or only its spaces differ (shelter
                # color1 "brown " 2,415 beside "brown" 4,482, from a split): 21,572 Medium rows on 16 of 323 real tables (AH-142)
                if c >= 5 and (not styled or capital(raw) == caps and raw == " ".join(raw.split()) or c >= counts[right]
                               or raw.split() == right.split()):
                    missed[s.index[s == raw][0]].append(Why(f'{col} is written "{_short(raw)}" {c} times and "{_short(right)}" '
                                                            f'{counts[right]} time{"s" * (counts[right] > 1)} (same word, different capitals/spaces)', col))
                    continue
                for i in s.index[s == raw]:
                    out[i].append(Why(f'{col} "{_short(raw)}" looks like "{_short(right)}" (same word, different capitals/spaces)', col))
                    fix[i][col] = right
                    if counts[right] >= 5 * c:  # auto-fix only when the right spelling is plainly the usual one
                        exact[i][col] = right
        cnt = keys.value_counts()
        if _person_name(col, column_types, labels):  # capitals/spaces of the very same name above, never a guess at another name (AH-24)
            continue
        # 3 letters only in a closed set: 16% of the 664 three-letter words among the 10,000 commonest have a swap twin
        # (own/won), so "Yse" once beside "Yes" 20+ times in a column of 6 labels or fewer, never an open list (AH-139)
        three = lambda r, u, c, m: len(cnt) <= 6 and c == 1 and m >= 20 and len(r) == len(u) == 3 and r.isalpha() and _swapped(r, u)
        # over 60 characters is a note, not a label: crafted 32,000-character labels took 58 s here (council, 2026-10-16)
        # Every slip _misspelt and three allow is one letter changed, swapped, added or dropped, so the two labels share
        # a spelling with one letter left out: only those are compared. Every rare label against every usual one grew
        # with the square of the labels once the 200-label cap went (5,000 x 5,000 crafted: minutes, AH-178), and the
        # commonest USUAL usual labels bound what is kept
        usual_ = [(u, m) for u, m in cnt.items() if m >= 5 and len(u) <= 60][:USUAL]
        near = collections.defaultdict(list)  # a spelling with at most one letter left out -> the usual labels it comes from
        for r, (u, _) in enumerate(usual_):
            for v in {u, *(u[:k] + u[k + 1:] for k in range(len(u)))}:
                near[v].append(r)
        for rare, c in cnt[cnt <= 2].items():
            if NO_VALUE_WORD.fullmatch(rare) or len(rare) > 60:  # "Blank" is no race, never a misspelling of "Black" (AH-50)
                continue
            ranks = sorted({r for v in {rare, *(rare[:k] + rare[k + 1:] for k in range(len(rare)))} for r in near.get(v, ())})
            usual = next((u for u, m in (usual_[r] for r in ranks) if m >= 5 * c
                          and (_misspelt(rare, u) or three(rare, u, c, m))), None)
            if usual is None:
                continue
            word = s[keys == usual].value_counts().index[0]  # how the usual one is usually written
            for i in keys.index[keys == rare]:
                missed[i].append(Why(f'{col} "{_short(s[i])}" looks like a misspelling of "{_short(word)}"', col))
                maybe[i][col] = word
        if many:  # past 50 labels the misspelling guess alone (see the cap above)
            continue
        # a short form of exactly one other label (5+ rows, 2+ letters longer): its start ("EMP" for "Employed"), each
        # word's start ("In Prog" for "In Progress"), or a contraction ("Std" for "Standard": same first letter, the rest
        # in order, at most one vowel - "Fee" is not short for "Free")
        # A whole word of another label is a label of its own: Periode "II" next to "II-III?" (blind real sheet, 123
        # correct cells offered "II-III?", 2026-10-16), "Pen" next to "Pen Set"
        # ...words split at any mark: "mm" is a word of "mm_prediction_random_forest", no short form of it (AH-177)
        tokens = collections.Counter(w for u in cnt.index for w in set(re.split(r"[\W_]+", u)))
        whole = lambda short: tokens[short] > 1  # a word of some other label too, not only of itself
        for short in cnt.index:
            # a short form is the rarer spelling - the full label at least twice as common: "CAF" (51 rows) is not short
            # for "CONCACAF" (30), nor "VI" for "VIII" - 71 cards would have overwritten correct labels (real sheets, 2026-10-16)
            longer = [u for u, m in cnt.items() if m >= max(5, 2 * cnt[short]) and len(u) >= len(short) + 2 and _short_for(short, u)]
            if 2 <= len(short.replace(" ", "")) <= 6 and short.replace(" ", "").isalpha() and len(longer) == 1 and not whole(short) \
                    and not NO_VALUE_WORD.fullmatch(short):
                for i in keys.index[keys == short]:
                    missed[i].append(Why(f'{col} "{_short(s[i])}" looks like a short form of "{_short(rights[longer[0]])}"', col))
                    maybe[i][col] = rights[longer[0]]
        # a label written in lowercase where the column's 3+ other labels all start with a capital ("retired" next to
        # "Employed", "Unemployed"): sorts and reads as a different label in a pivot
        if len(cnt) >= 4:
            for key, right in rights.items():
                if right.islower() and right.replace(" ", "").replace("-", "").isalpha() and all(
                        capital(r) for k, r in rights.items() if k != key):
                    for i in keys.index[keys == key]:
                        missed[i].append(Why(f'{col} "{_short(s[i])}" is lowercase where the column\'s other labels are capitalised', col))
                        maybe[i][col] = right[:1].upper() + right[1:]
    return out, fix, missed, maybe, exact


ORDER_ROWS = 1000  # rows with both filled before an order is judged: blind round 2's probe of 42 real tables found the
# planted swaps and 1 false row from 1,000 rows, about 25 false rows from 100 (AH-178)
# Only headers that name an order are judged (AH-178 fix round 1): any two neighbours that merely sat in order on 99.9% of
# rows were judged, and blind rounds 2-3 got about 60 false Medium rows from unrelated pairs (UFC's b_draw under b_wins,
# hotels' booking_changes under agent and required_car_parking_spaces under adr, age under height, lng under lat).
# Two headers name an order when their words are the same but one each, and those two are (low end, high end) here,
# or ranks that climb (10th < 90th, p10 < p90, q1 < q3, Quantile 25 < Quantile 75); the order is the one the words give
LOWS, MIDS, HIGHS = {"min", "minimum", "lowest", "low"}, {"avg", "average", "mean", "median"}, \
    {"max", "maximum", "top", "peak", "highest", "high"}
ORDER_WORDS = {("min", "max"), ("minimum", "maximum"), ("low", "high"), ("lowest", "highest"), ("lower", "upper"),
               ("lo", "hi"), ("start", "end"), ("begin", "end"), ("first", "last"), ("earliest", "latest"), ("from", "to"),
               ("open", "high"), ("close", "high"), ("low", "open"), ("low", "close")} \
    | set(itertools.product(LOWS, MIDS)) | set(itertools.product(MIDS, HIGHS))
ORDER_VOCAB = {w for pair in ORDER_WORDS for w in pair}
# A number is a rank only when it says so (AH-178 fix round 2): an ordinal (10th), a tag (p10, q3, pct25) or a header that
# says quantile; a plain number (Sales 2019/Sales 2020, Score 1/Score 2) is a growth series or two scores, no order
RANK = re.compile(r"(p|q|pct)?(\d{1,9})(st|nd|rd|th)?")  # 9 digits at most: int() refuses a 4,300-digit run
QUANTILE = {"percentile", "percentiles", "quantile", "quartile", "decile", "pctile", "centile"}
ORDER_COLS, ORDER_PAIRS = 300, 100  # in sheet order: a crafted wide sheet costs at most 300 columns' headers, 100 pairs


def _order_words(col):
    """'Hourly 10th Percentile' -> ['hourly', '10th', 'percentile']; 'minTemp' -> ['min', 'temp']: camelCase and any
    mark split words, digits kept. A header of over 8 words names no order (and a 100,000-character one costs nothing)"""
    w = re.findall(r"[a-z]*\d+(?:st|nd|rd|th)?|[a-z]+", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(col)).lower())
    return w if len(w) <= 8 else []


def _names_order(x, y):
    """Do header words x name the low end of an order whose high end y names?"""
    diff = [(p, q) for p, q in zip(x, y) if p != q]
    if not x or len(x) != len(y) or len(diff) != 1:
        return False
    p, q = diff[0]
    m, n = RANK.fullmatch(p), RANK.fullmatch(q)
    if (p, q) in ORDER_WORDS:
        return True
    return bool(m and n and m[1] == n[1] and int(m[2]) < int(n[2]) and (m[1] or m[3] and n[3] or QUANTILE & set(x)))


def order(df, column_types, skip):
    """A number column at most another on every other row (max(2, 0.1%) rows may break it), their headers naming the
    order and their values meeting where it holds: the row where it is above (a 10th percentile above its 90th, a Low
    above its High). Which of the two cells is wrong is unknown, so never a fix."""
    out = [[] for _ in range(len(df))]
    words = {c: _order_words(c) for c, t in column_types.items() if t == "number"}
    cols = [c for c, w in words.items() if any(x in ORDER_VOCAB or RANK.fullmatch(x) for x in w)][:ORDER_COLS]
    pairs = (p for p in itertools.permutations(cols, 2) if _names_order(words[p[0]], words[p[1]]))
    for lo, hi in itertools.islice(pairs, ORDER_PAIRS):
        u, v = (pd.to_numeric(df[c], errors="coerce").to_numpy(float) for c in (lo, hi))
        both = ~skip & ~np.isnan(u) & ~np.isnan(v)
        if both.sum() < ORDER_ROWS:
            continue
        above, holds = both & (u > v), both & (u <= v)
        if 0 < above.sum() <= max(2, 0.001 * both.sum()) and u[holds].max() > v[holds].min():
            for i in np.flatnonzero(above):
                out[i].append(Why(f"{lo} {say(df[lo].iat[i])} is above {hi} {say(df[hi].iat[i])}, where {lo} is at "
                                  f"most {hi} on {holds.sum()} of {both.sum()} rows", lo, hi))
    return out


DATE_COLS = 20  # date columns whose pairs are read, in sheet order: a crafted wide sheet stays fast
DATE_ROWS = 50  # rows with both dates before an order between two date columns is read: the same bar as a check's 50


def date_order(df, column_types, skip, far, records=None):
    """AH-198: two date columns where one is on or after the other on every row but max(1, 0.1%), their dates meeting
    where it holds (a sample resulted on or after it was drawn, delivered on or after it shipped): a row where it comes
    before is a contradiction. Which date is wrong is unknown, unless one column is the sheet's own order (its dates
    never go back down the rows, at most the same few) and this row keeps that order: then the other is named alone. Two
    breaks in 64 or 1,181 rows were a medicines register's re-examined opinions, honest. A date already far outside its
    column (far) is that date's slip, said once. records: see _odd_line."""
    out = [[] for _ in range(len(df))]
    cols = [c for c, t in column_types.items() if t == "date"][:DATE_COLS]
    odd = _odd_line(df, records or {}, cols)
    when = {c: pd.to_datetime(df[c], errors="coerce", utc=True).where(~skip) for c in cols}  # utc: a +02:00 beside a plain date
    # AH-210: a date already far outside its column is that date's slip, never a row against the order: a checkout typed
    # in 2125 made "returned before checked out" a second break, and the real one went unsaid (3 of 4 tuning episodes)
    off = {c: np.array([any(c in r.cols for r in said) for said in far], bool) for c in cols}
    broken = []  # (row, a, b, sentence, the cells named)
    for a, b in itertools.permutations(cols, 2):
        u, v = when[a], when[b]
        both = (u.notna() & v.notna()).to_numpy() & ~off[a] & ~off[b]
        if both.sum() < DATE_ROWS:
            continue
        before, holds = both & (v < u).to_numpy(), both & (v >= u).to_numpy()
        if not 0 < before.sum() <= max(1, 0.001 * both.sum()) or not u[holds].max() > v[holds].min():
            continue
        for i in np.flatnonzero(before):
            named = [c for c in (b, a) if not _in_order(when[c], i, before.sum())] or [b, a]
            broken.append((i, a, b, f"{b} {v.iat[i]:%Y-%m-%d} is before {a} {u.iat[i]:%Y-%m-%d}, where {b} is on or after {a} "
                                    f"on {holds.sum()} of {both.sum()} rows", named))
    # AH-210: one slip changes one date: the date of the row that breaks its order with more of the row's other dates
    # than its partner does is the odd one (a ticket closed a month before it was opened and first answered), named alone
    hits = collections.Counter((i, c) for i, a, b, *_ in broken for c in (a, b))
    for i, a, b, text, named in broken:
        if hits[i, a] != hits[i, b]:
            named = [a if hits[i, a] > hits[i, b] else b]
        # AH-211: ...and so is the one that also differs from its own record's other lines, where every record shares that
        # date (a report's Submitted date, a day before its expense and a month before the report's other line)
        elif len(named) == 2 and len(lone := [c for c in named if odd[c][i]]) == 1:
            named = lone
        out[i].append(Why(text, *named))
    return out


def _odd_line(df, records, cols):
    """AH-211: {column: per row, its value differs from another line of its record}, for a column every record of 2+
    lines (RECORDS+ of them) writes once but max(1, 1%), as same_in_record reads one, besides the row's own record (the
    slip being judged: a report submitted early and another late were 2 of 165, episode 19); all False for any other
    column. A record of 2 lines cannot say which line is odd: only a second contradiction (date_order's) can."""
    out = {c: np.zeros(len(df), dtype=bool) for c in cols}
    for run in records.values():
        keep = run >= 0
        for c in cols:
            v = pd.Series(df[c].astype(str).str.strip().where(~_blank(df[c])).to_numpy(object)[keep])
            kinds = v.groupby(run[keep]).nunique(dropna=False)
            if len(kinds) >= RECORDS and (kinds > 1).sum() - 1 <= max(1, 0.01 * len(kinds)):
                out[c][np.flatnonzero(keep)[np.isin(run[keep], kinds.index[kinds > 1])]] = True
    return out


def _in_order(d, i, slack):
    """d's dates never go back down the rows (at most `slack` times: the rows a contradiction may hold), and row i keeps
    to that order: the column the sheet is sorted by, its date on row i not the odd one."""
    x = d.dropna()
    if (x.diff() < pd.Timedelta(0)).sum() > slack:
        return False
    k = x.index.get_loc(d.index[i])
    return (k == 0 or x.iat[k - 1] <= x.iat[k]) and (k == len(x) - 1 or x.iat[k] <= x.iat[k + 1])


BALANCE_COLS = 40  # number columns whose pairs are summed per record, in sheet order: a crafted wide sheet stays fast
RECORDS = 20  # records of 2+ lines a column must hold before its lines are read as one record's


def _records(df, column_types, skip):
    """Text or id columns that split a record over lines (a journal entry, an order's items): each value's rows one run
    down the sheet, RECORDS+ values on 2+ rows, at most 10 rows each in the middle, half the rows in such a run. -> {column:
    run number per row, -1 where none}. The first 64 such columns in sheet order: a crafted wide sheet stays fast."""
    out = {}
    for c in [c for c, t in column_types.items() if t in ("text", "id")][:64]:
        if len(out) == 3:  # a sheet has one record column, two at most (an order and its invoice): 3 bounds the work
            break
        v = df[c].astype(str).str.strip().where(~skip & ~_blank(df[c]))
        if v.isna().all():
            continue
        start = (v != v.shift()).cumsum().where(v.notna())
        runs = start.groupby(v).nunique()
        size = v.value_counts()
        multi = size[size >= 2]
        if (runs > 1).any() or len(multi) < RECORDS or multi.median() > 10 or multi.sum() < 0.5 * (~skip).sum():
            continue
        out[c] = np.where(v.isin(multi.index), start.fillna(-1), -1).astype(int)
    return out


def _shown(v):
    """A cell as a sentence quotes it: a date as its day, a number as typed, text cut short."""
    return f"{v:%Y-%m-%d}" if isinstance(v, pd.Timestamp) else say(v) if pd.api.types.is_number(v) else _short(v)


def same_in_record(df, column_types, skip, records, computed=()):
    """AH-198: a column the same on every line of a record (an entry's posting date), in every record of 2+ lines but
    max(1, 1%): the one line of a record of 3+ that differs from its other lines, which agree, is wrong (a journal
    entry's third line posted two weeks earlier). Never the record's own column, one that differs in many, a formula's
    (its inputs are judged) nor a blank (the blanks check judges those)."""
    out = [[] for _ in range(len(df))]
    for g, run in records.items():
        keep = run >= 0
        for c in [c for c in df.columns if c != g and c in column_types and c not in computed][:200]:
            v = df[c].astype(str).str.strip().where(~_blank(df[c])).to_numpy(object)
            v[pd.isna(v)] = None
            per = pd.Series(v[keep]).groupby(run[keep])
            kinds = per.nunique(dropna=False)
            off = kinds.index[kinds > 1]
            if len(kinds) < RECORDS or len(off) > max(1, 0.01 * len(kinds)) or pd.Series(v[keep]).nunique() < 2:
                continue
            for r in off:
                rows = np.flatnonzero(run == r)
                counts = collections.Counter(v[rows])
                (usual, _), *rest = counts.most_common()
                if len(rows) >= 3 and len(rest) == 1 and rest[0][1] == 1 and None not in counts:
                    i = next(i for i in rows if v[i] != usual)
                    out[i].append(Why(f"{c} {_shown(df[c].iat[i])} differs from the other lines of {g} "
                                      f"{_short(df[g].iat[i])}, which all have {_shown(df[c].iat[rows[0] if rows[0] != i else rows[1]])}", c))
    return out


KEY_GROUPS = 10  # groups of 2+ rows a key must hold before a column is read as one value for each of them
KEY_OFF = 0.05  # ...and at most max(1, this share) of its groups of 2+ rows with more than one value
KEY_CAP = 2  # ...and never more than 2: an id whose 1,526 items kept 5 second names, a player id 173 positions, an
# album id 122 featured artists, is how those tables are, never 173 slips (public tables, AH-198 fix round 2)
KEYS = 8  # key columns read, in sheet order, each against the first 64 columns: a crafted wide sheet stays fast


def same_by_key(df, column_types, skip, computed=None):
    """AH-198 fix round 2: a column one value for each value of a key column (a part's unit cost, an account's name, a
    child's level under its parent) in all but max(1, KEY_OFF), at most KEY_CAP, of the key's KEY_GROUPS+ groups of 2+
    rows: in a group with one other value, written once against 2+ rows that agree, that cell is wrong (a part costed
    0.4 on one line of its 12, 0.04 on the rest). The key a code; never a blank or a word for no value, a formula's
    cell, a column of 2 values (a flag), a key whose values each sit in one run (a record's lines: same_in_record
    reads those, from 20 records) nor a protected key."""
    out = [[] for _ in range(len(df))]
    computed, prot = computed or {}, set(fairness.protected(column_types))
    cols = [c for c in column_types][:64]
    said = {c: df[c].astype(str).str.strip().where(~skip & ~_blank(df[c])) for c in cols}
    # a key is a code (P-10222, 2000, S01-101: 90% of its values with a digit and no space): a name is no key, two people
    # or two carousels share one, nor a date, which two presidents' nominations shared (public tables, AH-198 fix round 2)
    code = lambda v: v.str.contains(r"\d").mean() >= 0.9 and not v.str.contains(r"\s").mean() > 0.1 \
        and not v.str.fullmatch(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}").mean() > 0.1
    keys = [k for k, t in column_types.items() if t in ("text", "id") and k not in prot and k in said
            and said[k].notna().any() and code(said[k].dropna())]
    said = {c: v.where(~v.fillna("").str.fullmatch(NO_VALUE_WORD)) for c, v in said.items()}  # "NA", "-", Unknown: no value
    found = 0
    for k in keys:
        if found == KEYS:
            break
        kc = pd.factorize(said[k])[0]
        size = np.bincount(kc[kc >= 0]) if (kc >= 0).any() else np.zeros(0, int)
        at = kc[kc >= 0]
        runs = np.bincount(at[np.r_[True, at[1:] != at[:-1]]], minlength=len(size))  # each value's runs down the sheet
        if (size >= 2).sum() < KEY_GROUPS or (runs == 1).all():  # one run each: a record's lines, same_in_record's
            continue
        found += 1
        for a in cols:
            if a == k or said[a].nunique() < 3:
                continue
            ac = pd.factorize(said[a])[0]
            both = (kc >= 0) & (ac >= 0) & ~computed.get(a, np.zeros(len(df), bool))
            pair = pd.DataFrame({"k": kc[both], "a": ac[both], "i": np.flatnonzero(both)})
            n = pair.groupby("k")["a"].agg(["size", "nunique"])
            multi = n[n["size"] >= 2]
            off = multi.index[multi["nunique"] > 1]
            if len(multi) < KEY_GROUPS or len(off) > min(KEY_CAP, max(1, KEY_OFF * len(multi))):
                continue
            for g in off:
                rows = pair[pair["k"] == g]
                counts = rows["a"].value_counts()
                if len(counts) != 2 or counts.iloc[1] != 1 or counts.iloc[0] < 2:
                    continue
                i = int(rows["i"][rows["a"] == counts.index[1]].iloc[0])
                usual = df[a].iat[int(rows["i"][rows["a"] == counts.index[0]].iloc[0])]
                out[i].append(Why(f"{a} {_shown(df[a].iat[i])} differs from the other {counts.iloc[0]} rows of {k} "
                                  f"{_short(df[k].iat[i])}, which all have {_shown(usual)} ({a} is one value for each {k} "
                                  f"in {(multi['nunique'] == 1).sum()} of {len(multi)})", a))
    return out


STEADY = 1.2  # a record's values this close (largest over smallest) are one entity's own size: a subject's weight
READ_BACK = 1.05  # a value one slip reads back inside its record's range, give or take 5%
# a decimal point or zeros, or a minus sign: a unit read back too (pounds, miles, inches...) met a county's honest
# populations of other years 1.6 or 2.2 times apart by chance (public tables, AH-198 fix round 2)
SCALES = (lambda v: v * 10, lambda v: v / 10, lambda v: v * 100, lambda v: v / 100, lambda v: v * 1000, lambda v: v / 1000,
          lambda v: -v)


def own_scale(df, column_types, skip, records, computed=None):
    """AH-198 fix round 2: a number column steady inside each record (its 3+ values within STEADY of each other in 90% of
    RECORDS+ records: a subject's weight, a part's price) holds one entity's own size. A value off its record's other
    values, which agree, and read back among them by a slip of the decimal point or a minus sign (SCALES), is that slip
    (an income of 576,510 on a line of its record whose others read 57,651). Never a formula's cell; never a fix: which
    of the entity's values it was is unknown. In sheet order: the first 50 number columns."""
    out = [[] for _ in range(len(df))]
    computed = computed or {}
    for g, run in records.items():
        for c in [c for c, t in column_types.items() if t == "number" and 2 * computed.get(c, np.zeros(1)).sum() <= len(df)][:50]:
            x = pd.to_numeric(df[c], errors="coerce").where(~skip & (run >= 0) & ~computed.get(c, np.zeros(len(df), bool)))
            have = x.notna().to_numpy() & (x != 0).to_numpy()
            per = pd.Series(x[have].abs().to_numpy()).groupby(run[have])
            size = per.size()
            ratio = (per.max() / per.min())[size >= 3]
            if len(ratio) < RECORDS or (ratio <= STEADY).mean() < 0.9:
                continue
            for r in ratio.index[ratio > STEADY]:
                rows = np.flatnonzero((run == r) & have)
                for i in rows:
                    rest = x.iloc[[k for k in rows if k != i]].to_numpy(dtype=float)
                    lo, hi, v = rest.min(), rest.max(), float(x.iat[i])
                    if len(rest) < 2 or lo <= 0 or hi / lo > STEADY:
                        continue
                    if any(lo / READ_BACK <= f(v) <= hi * READ_BACK for f in SCALES):
                        out[i].append(Why(f"{c} {say(v)} is {abs(v) / np.median(rest):.1f} times the other {c} values of {g} "
                                          f"{_short(df[g].iat[i])} ({say(lo)} to {say(hi)}): a slip of the decimal point or the sign", c))
    return out


def coded_spellings(df, column_types, skip, maybe):
    """AH-198: a possible misspelling (spellings' guess, maybe = {column: usual spelling} per row) its row's own code
    proves: another column whose every value names one label of this column (Account 2000 is "Accounts Payable" on its
    10+ codes of 2+ rows but max(1, 1%) besides the row's own), and whose other rows of this code all read the usual
    spelling. "Acounts Payable" on Account 2000 is then no other payee, but a slip. Only the cells the spelling check
    already guessed at."""
    out = [[] for _ in range(len(df))]
    seen = {}
    for i in (i for i in range(len(df)) if maybe[i]):
        for col, usual in maybe[i].items():
            for k, t in list(column_types.items())[:64]:  # the first 64 columns: a crafted wide sheet stays fast
                if k == col or t not in ("text", "id", "number") or pd.isna(df[k].iat[i]):
                    continue
                if (k, col) not in seen:
                    both = ~skip & ~_blank(df[k]) & ~_blank(df[col])
                    kinds = df[col][both].astype(str).str.strip().groupby(df[k][both]).agg(["nunique", "size"])
                    multi = kinds[kinds["size"] >= 2]
                    seen[k, col] = (len(multi) >= 10, set(multi.index[multi["nunique"] > 1]), max(1, 0.01 * len(multi)))
                # ...besides the row's own code, whose second name is the slip judged (AH-211: "Finannce" on an employee,
                # and another employee moved to another department for one period, episode 20)
                enough, off, allowed = seen[k, col]
                if not enough or len(off - {df[k].iat[i]}) > allowed:
                    continue
                same = df[col][(df[k] == df[k].iat[i]) & ~skip & (df.index != df.index[i])].astype(str).str.strip()
                if len(same) >= 2 and (same == usual).all():
                    out[i].append(Why(f'{col} "{_short(df[col].iat[i])}" differs from the other rows of {k} '
                                      f'{_shown(df[k].iat[i])}, which all read "{_short(usual)}"', col))
                    break
    return out


SCALE_FIT = 0.5  # share of a column's spread (of its log sizes) its category explains before the category sets its scale
SCALE_SPAN = 10  # ...and the categories' usual sizes this many times apart: potassium near 4 beside a CRP near 50


def by_scale(df, column_types, skip, k, computed=(), voted=()):
    """AH-198: a long sheet keeps many quantities in one column, a text column saying which (a lab's Result by Test, a
    freight amount by its currency, a weight by the shipment's mode). Judged as a whole, potassium 44 (for 4.4) sat among
    sodium near 140, and a courier parcel of 1700 kg among containers. Where one text column of 2-50 labels, 10+ rows a
    label on average and never a protected one, explains SCALE_FIT of the column's log sizes and its labels' usual sizes
    are SCALE_SPAN apart, each label's 20+ values get their own limits, and a value past them votes only with a slip of
    zeros or the decimal point behind it (detectors.likely_value): a real critical potassium of 6.8 has none. Never a
    fix: a gram typed for a kilo looks like 100 or 1000 the same. Never a formula's cell, nor one the limits named.
    In sheet order: 16 label columns of the first 64, the first 50 number columns."""
    from anomaly_hunter.engine.detectors import _crossed, _signed, column_stats, likely_value
    from anomaly_hunter.engine.limits import _limits  # limits imports this module: here, never at the top

    out = [[] for _ in range(len(df))]
    prot = set(fairness.protected(column_types))
    labels = {g: df[g].astype(str).str.strip().where(~skip & ~_blank(df[g])) for g, t in list(column_types.items())[:64]
              if t == "text" and g not in prot}  # the first 64 columns, then 16 label columns at most below
    labels = dict(list({g: lab for g, lab in labels.items() if 2 <= lab.nunique() <= 50 and lab.count() >= 10 * lab.nunique()}.items())[:16])
    for c in [c for c, t in column_types.items() if t == "number" and c not in computed][:50]:
        x = pd.to_numeric(df[c], errors="coerce").where(~skip)
        ok = x.notna() & (x != 0)
        if ok.sum() < 40:
            continue
        lx = np.log10(x[ok].abs())
        spread_all = ((lx - lx.mean()) ** 2).sum()
        best = None
        for g, lab in labels.items():
            have = ok & lab.notna()
            if have.sum() < 0.9 * ok.sum() or not spread_all:
                continue
            fit = 1 - (lx[have] - lx[have].groupby(lab[have]).transform("mean")).pow(2).sum() / spread_all
            med = x[have].abs().groupby(lab[have]).median()
            if fit >= SCALE_FIT and med.max() >= SCALE_SPAN * med.min() and (best is None or fit > best[0]):
                best = (fit, g)
        if best is None:
            continue
        g = best[1]
        for name, idx in x.groupby(labels[g]).groups.items():
            v = x[idx].dropna()
            if len(v) < 20:
                continue
            b_lo, b_hi, w_lo, w_hi = _limits(v, k, _signed(c, df.columns))
            st = column_stats(v.to_numpy(dtype=float))
            for i, y in v.items():
                if (lim := _crossed(y, w_lo, w_hi)) is None or c in voted[i]:
                    continue
                fix = likely_value(y, st, b_lo, b_hi)
                if fix is not None and fix != -y:
                    out[i].append(Why(f"{c} {say(y)} is far outside the other {c} values for {g} {_short(name)} (weird limit "
                                      f"{lim:g}), {max(abs(y / fix), abs(fix / y)):.0f} times {'a usual one' if abs(y) > abs(fix) else 'smaller than a usual one'}: "
                                      "a slip of zeros or the decimal point", c))
    return out


def _swaps(v):
    """Every value two neighbouring digits of v swapped give, as typed (6747.67 -> 7647.67, 6477.67, ...)."""
    t = say(v)
    return {float(t[:k] + t[k + 1] + t[k] + t[k + 2:]) for k in range(len(t) - 1)
            if t[k].isdigit() and t[k + 1].isdigit() and t[k] != t[k + 1]}


BALANCE_OFF = 0.02  # records of a pair that may be off, at most max(1, this share): 3 slips in a 181-entry journal


def _balanced(df, column_types, skip, records, computed=None):
    """Two number columns whose sums agree in every record of 2+ lines but max(1, BALANCE_OFF) (an entry's debits and
    credits): RECORDS+ records with amounts, the two seldom filled on one line (never a pair, `pairs`), neither column
    mostly formulas (a journal's VAT and payable lines are formulas, its total rows SUMs: their values still add).
    -> [(record column, run per row, a, b, x, the records' sums of a and b)]."""
    computed = computed or {}
    cols = [c for c in numbers(column_types) if 2 * computed.get(c, np.zeros(1)).sum() <= len(df)][:BALANCE_COLS]
    x = {c: pd.to_numeric(df[c], errors="coerce").where(~skip) for c in cols}
    out = []
    for g, run in records.items():
        keep = run >= 0
        total = {c: x[c][keep].groupby(run[keep]).sum() for c in cols}
        for a, b in itertools.combinations(cols, 2):
            both = (x[a].notna() & x[b].notna())[keep]
            if both.mean() > 0.5 or len(total[a]) < RECORDS or (total[a] != 0).sum() < RECORDS:  # never all 0
                continue
            diff = (total[a] - total[b]).round(6)
            if (diff.abs() >= 0.005).sum() <= max(1, BALANCE_OFF * len(diff)):
                out.append((g, run, a, b, x, total[a], total[b]))
    return out


def balances(df, column_types, skip, records, computed=None):
    """AH-198: two number columns whose sums agree in every record but a few (`_balanced`: an entry's debits and
    credits): a record off is one slip, and where swapping two neighbouring digits of one of its typed cells makes it
    agree, that cell is the slip ("likely" the swapped value: the record's own sums prove it). Where two cells could be
    swapped (a receipt's 12,952.36 debit against its 12,592.36 credit), the one whose value the sheet writes again outside
    the record (the invoice's 12,592.36) is corroborated, and the other is the slip (AH-198 fix round 2). A record off
    with no one such cell says nothing: which line is wrong is unknown. -> (reasons, likely)."""
    out, likely = [[] for _ in range(len(df))], [{} for _ in range(len(df))]
    computed = computed or {}
    typed = lambda c, i: not computed.get(c, np.zeros(len(df), bool))[i]
    for g, run, a, b, x, ta, tb in _balanced(df, column_types, skip, records, computed):
        diff = (ta - tb).round(6)
        allx = np.concatenate([x[c].to_numpy(dtype=float) for c in x])
        for r in diff.index[diff.abs() >= 0.005]:
            d, rows = diff[r], np.flatnonzero(run == r)
            found = [(i, c, w) for c, sign in ((a, -1), (b, 1)) for i in rows if pd.notna(x[c].iat[i]) and typed(c, i)
                     for w in _swaps(x[c].iat[i]) if abs(x[c].iat[i] + sign * d - w) < 0.005]
            if len(found) > 1:  # written again outside the record: the other side's real amount
                mine = np.concatenate([rows + k * len(df) for k in range(len(x))])
                elsewhere = lambda v: np.isclose(np.delete(allx, mine), v, rtol=0, atol=0.005).any()
                found = [f for f in found if not elsewhere(x[f[1]].iat[f[0]])]
            if len(found) == 1:
                i, c, w = found[0]
                out[i].append(Why(f"{c} {say(x[c].iat[i])} leaves {g} {_short(df[g].iat[i])} off by {abs(d):.10g} ({a} "
                                  f"{ta[r]:.10g}, {b} {tb[r]:.10g}), where every other {g} agrees: two digits "
                                  f"swapped (likely {say(w)})", c))
                likely[i][c] = w
    return out, likely


def fractions(df, column_types, skip):
    """A ratio above 100% (Credit_Utilization 1.026) in a column of fractions: 98%+ of its values between 0 and 1, most
    of them not whole numbers (a 0/1 flag or a count is no fraction). Worth a check, not wrong: an over-limit card exists,
    a slip is likelier. Below 0 is the limits check's (a column that never goes negative)."""
    out = [[] for _ in range(len(df))]
    for col in numbers(column_types):
        x = df[col][~skip].dropna().astype(float)
        inside = x.between(0, 1)
        if len(x) < 20 or inside.all() or inside.mean() < 0.98 or (x[inside] == x[inside].round()).mean() > 0.5:
            continue
        for i in x.index[x > 1]:
            out[i].append(Why(f"{col} {say(x[i])} is above 100% - the rest of the column stays between 0 and 1", col))
    return out


def codes(df, column_types, skip):
    """A column's top value is all 9s (999, 9999, 99999) and over twice the next one: a code for "missing" or "too big to
    record" (census capital gains stop at 41,310, then 244 people have 99999), not an amount - it wrecks every average.
    Repeats don't hide it: the code is typed the same way each time. -> (reasons, notes): one written 5+ times through 4
    of the 5 fifths of the sheet is one note, like a negative code (AH-142: the real census's 99999, 148 to 244 times in
    every fifth, was 551 Medium rows on 3 copies); a block of them is still each a code to check."""
    out, notes = [[] for _ in range(len(df))], [[] for _ in range(len(df))]
    for col in numbers(column_types):
        x = df[col][~skip].dropna().astype(float)
        top = np.sort(x.unique())[-2:]
        if len(x) < 20 or len(top) < 2 or not top[1].is_integer() or top[1] < 999 or set(str(int(top[1]))) != {"9"} \
                or top[1] < 2 * top[0]:
            continue
        hit = x.index[x == top[1]]
        if len(hit) >= 5 and _spread(df.index.get_indexer(hit), len(df)):
            notes[hit[0]].append(Why(f"{col} {say(top[1])} is written {len(hit)} times: the column's code for no value or "
                                     f"too big to record", col))
            continue
        for i in hit:
            out[i].append(Why(f"{col} {say(top[1])} looks like a code, not a real value (all 9s, over twice the next "
                              f"highest, {say(top[0])})", col))
    return out, notes


def shifted(df, column_types, skip):
    """A text value typed into the wrong column ("East" in Item): once in its own column, 3+ times in another one, and
    the two columns otherwise share under 20% of their values (Origin/Destination, Home/Away share most: left alone).
    Category-like columns only (<= 50 distinct). Placeholders (N/A, ?) are the placeholder check's. -> reasons per row
    (worth a check, never auto-fixed). Values that need MEANING to judge ("London" among products) are the AI text check's."""
    out = [[] for _ in range(len(df))]
    keys = {}
    for col, t in column_types.items():
        if t == "text":
            s = df[col][~skip].map(lambda v: " ".join(str(v).split()).casefold())
            s = s[(s != "") & ~s.str[:1].isin(list("=+-@")) & ~s.str.fullmatch(PLACEHOLDER)]
            if s.nunique() <= 50 and len(keys) < 100:  # every pair of columns: 400 crafted ones took 44 s (2026-10-16)
                keys[col] = s
    counts = {c: s.value_counts() for c, s in keys.items()}
    usual = {c: set(n.index[n >= 2]) for c, n in counts.items()}  # shared vocabulary: one-offs are suspects, not evidence
    for a, sa in keys.items():
        for v in counts[a].index[counts[a] == 1]:
            for b in keys:
                if b != a and counts[b].get(v, 0) >= 3 and len(usual[a] & usual[b]) < 0.2 * len(usual[a] | usual[b]):
                    i = sa.index[sa == v][0]
                    out[i].append(Why(f'{a} "{_short(df[a][i])}" looks like {"an" if b[:1].lower() in "aeiou" else "a"} {b} value', a))
                    break
    return out


OWN_CELL = re.compile(r"(?<![\w\]!.$'])R(?:\[0\])?C(?:\[0\])?(?![\w\[])")  # RC, R[0]C, RC[0]: this row and column
SAME_FORMULA = 0.8  # Excel's own "inconsistent formula" check, read down a column: this share of its filled cells


VARIANT = 5  # rows a second formula of a column is written on before it is the column's own


def outside_list(df, skip, errors_log, invalid=None):
    """AH-213: the cells Excel itself says break their data validation (a drop-down list's choices: "Reciept" in a list
    of Receipt, Issue, Return), as the pane reads them (Range.getDataValidationInvalidCellsOrNullObject), [row, column]
    of this table. Excel knows the list; the engine only says it, the value as typed, never a fix. -> reasons per row."""
    out, raw = [[] for _ in range(len(df))], {(i, c): r for i, c, r in errors_log}
    for i, j in sorted({(i, j) for i, j in invalid or ()}):
        col = df.columns[j]
        v = raw.get((i, col), df[col].iat[i])
        if not skip[i] and not pd.isna(v) and str(v).strip():
            said = f'"{_short(v)}"' if isinstance(v, str) else _shown(v)
            out[i].append(Why(f"{col} {said} is not one of the choices its drop-down list allows", col))
    return out


# AH-213: a subtotal is a formula of the rows above it in its own column, one range: =SUM(R[-9]C:R[-1]C),
# =SUBTOTAL(9,R[-9]C:R[-1]C), =AVERAGE(...) (SUBTOTAL's 1 and 101 average, 9 and 109 add)
AGGREGATE = re.compile(r"=(?:(SUM|AVERAGE)\(|SUBTOTAL\((1|9|101|109),)R\[-(\d+)\]C:R\[-(\d+)\]C\)")
ABOVE = re.compile(r"R\[-\d+\]")  # a reference to a row above, in R1C1
FULL = 2  # other subtotals of the column that add every row of their group: then adding them all is the column's way


def subtotals(df, skip, grid=None):
    """AH-213: a subtotal that leaves out a row of its own group, a total that adds subtotals and the rows they already
    add, and a subtotal typed over. The layout reader sends subtotal rows blank (AH-212), so their mistakes went unseen:
    9 planted ones on the complex bench's tuning episodes. Read from the pane's R1C1 text, never from the values alone. A
    row's group runs up from it to the nearest row that is blank, a totals row (skip) or worked out from rows above (a
    subtotal, a gross profit =R[-6]C-R[-1]C, a running balance: a column of those has no group to judge). A subtotal
    that leaves out rows of its group is judged only where FULL other subtotals of the column add all of theirs (an
    opening balance a Total movements leaves out is the layout); a SUBTOTAL skips the SUBTOTALs inside its range, as
    Excel does (a grand total of SUBTOTAL over the whole column counts nothing twice). -> reasons per row."""
    n, found = len(df), [{} for _ in range(len(df))]  # row -> {what is wrong: [(column, sentence)]}
    for j, col in enumerate(df.columns if grid else ()):
        f = [str(row[j]).replace(" ", "") if row[j] else None for row in grid]
        x = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        has = np.isfinite(x)
        agg = {}  # row -> (first row added, last row added, adds: SUM or SUBTOTAL 9/109, a SUBTOTAL)
        for i, v in enumerate(f):
            if v and (m := AGGREGATE.fullmatch(v)) and 0 < int(m[4]) <= int(m[3]) <= i:
                agg[i] = (i - int(m[3]), i - int(m[4]), m[1] == "SUM" or m[2] in ("9", "109"), m[1] is None)
        edge = [bool(skip[i] or i in agg or f[i] and ABOVE.search(f[i])) for i in range(n)]

        def group(i):
            t = i
            while t > 0 and not edge[t - 1]:
                t -= 1
            return t
        kind = lambda r: f[r] or "typed"  # a row's way of writing the column
        inside, left = {}, {}  # each subtotal within its group: the group's first row; the rows like its own it leaves out
        for i, (top, bot, _, _) in agg.items():
            if top >= (t := group(i)) and has[top:bot + 1].sum() >= 2:
                like = collections.Counter(kind(r) for r in range(top, bot + 1) if has[r]).most_common(1)[0][0]
                inside[i], left[i] = t, [r for r in [*range(t, top), *range(bot + 1, i)] if has[r] and kind(r) == like]
        full = sum(not lost for lost in left.values())
        adds = sum(not lost and agg[i][2] for i, lost in left.items())  # ...of them, those that add
        for i, lost in left.items():
            if lost and full >= FULL:
                where = ("the row right above it" if lost == [i - 1] else "its first row" if lost == [inside[i]]
                         else f"{len(lost)} of them")
                word = "subtotal" if agg[i][2] else "average"
                found[i].setdefault(("left", *(i - r for r in lost)), []).append((col, (
                    f"The {word} in {col} adds {int(has[agg[i][0]:agg[i][1] + 1].sum())} of the {int(has[inside[i]:i].sum())} "
                    f"rows of its group and leaves out {where}")))
        for i, (top, bot, summed, sub) in agg.items():
            inner = [s for s in inside if top <= agg[s][0] and agg[s][1] <= bot and agg[s][2] and not (sub and agg[s][3])]
            twice = {r for s in inner for r in range(agg[s][0], agg[s][1] + 1) if has[r]}
            if summed and i not in inside and twice:
                many = len(inner) > 1
                found[i].setdefault(("twice", *(i - s for s in inner)), []).append((col, (
                    f"The total in {col} adds {len(inner)} subtotal{'s' if many else ''} and the {len(twice)} rows "
                    f"{'they' if many else 'it'} already add{'' if many else 's'}, so those rows count twice")))
        for i in range(n):  # a subtotal typed over: a totals row with a number and no formula, where the others add up
            if skip[i] and f[i] is None and has[i] and adds >= FULL and has[(t := group(i)):i].sum() >= 2:
                part = x[t:i][has[t:i]]
                total = round(float(part.sum()), _decimals(part))
                if abs(x[i] - total) > _cent(part) + 0.5 * 10.0 ** -_decimals(x[i:i + 1]):
                    found[i][("typed", col)] = [(col, f"{col} {say(x[i])} is typed where its other subtotals are formulas, "
                                                         f"and the rows of its group add up to {say(total)}")]
    # one slip a row: a subtotal filled right across its row leaves out the same rows in every column, said once, on the
    # first (the complex bench's planted skips were whole rows, each keyed to its first cell)
    also = lambda k: f", as {'do' if k > 1 else 'does'} {k} other column{'s' if k > 1 else ''} of this row" if k else ""
    return [[Why(said[0][1] + also(len(said) - 1), said[0][0]) for said in row.values()] for row in found]


def _role(df, column_types, skip, filled, off):
    """The rows of `off` (rows whose formula is not the column's usual one) that are every row of one label of a text
    column (5+ rows, never those of a label off writes partly): the label's own formula, a role, never a break."""
    out = set()
    for g in [c for c, t in column_types.items() if t == "text"][:64]:  # the first 64: a crafted wide sheet stays fast
        lab = df[g].astype(str).str.strip().where(~skip & ~_blank(df[g])).to_numpy(object)
        rows = collections.defaultdict(set)
        for i in filled:
            if not pd.isna(lab[i]):
                rows[lab[i]].add(i)
        out |= set().union(*(r for r in rows.values() if len(r) >= VARIANT and r <= off))
    return out


ROLE_ROWS = 10  # rows of a label that all hold a formula in a column but one typed: the label's own formula, typed over


def _typed_in_role(df, column_types, skip, filled, f):
    """-> (row, label column, label) for each typed cell of `filled` that is the only typed one among ROLE_ROWS+ filled
    rows of its label, in the first text column that shows it (the first 64 text columns)."""
    out, seen = [], set()
    for g in [c for c, t in column_types.items() if t == "text"][:64]:
        lab = df[g].astype(str).str.strip().where(~skip & ~_blank(df[g])).to_numpy(object)
        rows = collections.defaultdict(list)
        for i in filled:
            if not pd.isna(lab[i]):
                rows[lab[i]].append(i)
        for name, idx in rows.items():
            typed = [i for i in idx if f[i] is None]
            if len(idx) >= ROLE_ROWS and len(typed) == 1 and typed[0] not in seen:
                seen.add(typed[0])
                out.append((typed[0], g, name))
    return out


def formulas(df, column_types, skip, grid=None):
    """AH-152: a column worked out by one formula (Total =RC[-2]*RC[-1] in R1C1, the same text on every row) where a row
    holds a typed value, or another formula (=RC[-2]*R[1]C[-1], one row off). The values alone never show it: a typed
    250 that equals Qty x Price today is wrong the day Qty changes. grid = each cell's R1C1 formula or None, as the pane
    reads it; 80%+ of the column's filled cells, and 5+, must share one formula. A totals row's SUM is left out (skip).
    -> (reasons, fix): fix[i] = {column: the shared formula}, the card's fix, known from the column, never invented."""
    out, fix = [[] for _ in range(len(df))], [{} for _ in range(len(df))]
    if not grid:
        return out, fix
    for j, col in enumerate(df.columns):
        f, blank = [row[j] for row in grid], _blank(df[col]).to_numpy()
        filled = [i for i in range(len(df)) if not skip[i] and (f[i] is not None or not blank[i])]
        # AH-198, Excel's own circular reference: a formula that names its own cell (=RC, =R[0]C[0]) shows 0 or its last
        # value, never its inputs', in a column of formulas or not (a bill of materials' rows each reach another row)
        own = {i for i in filled if f[i] is not None and OWN_CELL.search(re.sub(r'"[^"]*"', "", f[i]))}  # never in a string
        for i in own:
            out[i].append(Why(f"{col} refers to its own cell (a circular reference)", col))
        counts = collections.Counter(f[i] for i in filled if f[i] is not None)
        top = counts.most_common(1)
        if not top or top[0][1] < 5 or top[0][1] < SAME_FORMULA * len(filled):
            # AH-198 fix round 2, by role: where no one formula holds the column (a journal's Debit is typed, summed on its
            # total lines, worked out on its receivable lines), a typed value on the one row of a label of ROLE_ROWS+ rows
            # whose others all use a formula there (the receivable debited by hand) is that label's formula typed over
            for i, g, lab in _typed_in_role(df, column_types, skip, filled, f):
                v = df[col].iat[i]
                out[i].append(Why(f"{col} {_shown(v)} is typed where the other rows of {g} {_short(lab)} use a formula", col))
            continue
        # AH-198 fix round 2: a second formula the column writes on VARIANT+ rows is its own, as a spelling written 5+
        # times is the source's (62 yen invoices rounded to whole yen among 406 to the cent), and so is any formula on
        # every row of a label, those rows only (each assembly's roll-up, never a part's)
        variant = {i for i in filled if f[i] is not None and counts[f[i]] >= VARIANT} | _role(df, column_types, skip, filled, {
            i for i in filled if f[i] is not None and f[i] != top[0][0]})
        for i in filled:
            if i in variant - own:
                continue
            if f[i] is None:
                v = df[col].iat[i]
                said = f"{say(v)} is a typed number" if pd.api.types.is_number(v) and not isinstance(v, (bool, np.bool_)) \
                    else f'"{_short(v)}" is typed text'
                out[i].append(Why(f"{col} {said} where the column's other rows use a formula", col))
            elif f[i] != top[0][0] and i not in own:
                out[i].append(Why(f"{col} uses a different formula from the other rows of its column", col))
            if f[i] != top[0][0]:
                fix[i][col] = top[0][0]
    return out, fix


COPY_COLS = 300  # number columns compared, in sheet order: a crafted wide sheet costs at most 300 hashes


def repeated_columns(df, column_types, skip, grid=None):
    """AH-182: two number columns equal row for row, blank on the same rows: one series pasted twice (a student's data
    series; Pruitt's spider papers and a 2016 Cell paper retracted for copied blocks of numbers). Each needs 10+ numbers
    and 5+ distinct values, never in order (a time axis or an ID is no measurement) nor mostly formulas (=B2 is a copy
    by design). One note (worth a check) on the first row both fill: which copy is wrong is unknown. On 129 public tables
    one pair matched, a board-game table's max_playtime = playing_time, as the source has it."""
    out, seen = [[] for _ in range(len(df))], {}
    for j, col in [(j, c) for j, c in enumerate(df.columns) if column_types.get(c) == "number"][:COPY_COLS]:
        x = np.where(skip, np.nan, pd.to_numeric(df[col], errors="coerce").to_numpy(float))
        v = x[~np.isnan(x)]
        d = np.diff(v)
        if len(v) < 10 or len(np.unique(v)) < 5 or (d >= 0).all() or (d <= 0).all() \
                or grid and 2 * sum(row[j] is not None for row in grid) > len(v):
            continue
        first = seen.setdefault(hashlib.sha256(np.nan_to_num(x, nan=np.inf).tobytes()).digest(), col)
        if first != col:
            out[int(np.flatnonzero(~np.isnan(x))[0])].append(
                Why(f"{col} is the same {len(v):,} numbers as {first}, row for row: was one column pasted twice?", first, col))
    return out


GENE = re.compile(r"[A-Za-z]+[A-Za-z0-9.-]*")  # TP53, BRCA1, Sept2, HLA-DRB1: letters, then letters, digits, - and .
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
AS_DATE = re.compile(rf"\d{{1,2}}-{MONTH}(?:-\d{{2,4}})?|{MONTH}-\d{{1,4}}|\d{{4}}-\d\d-\d\d(?:[T ][\d:.]+)?", re.I)
SERIALS = (36526, 73050)  # 2000-01-01 to 2099-12-31 as Excel's date serials: a date cell in a text column comes as one


def gene_dates(df, column_types, skip):
    """AH-182: Excel turns gene names into dates when they are typed or opened from a CSV (SEPT2 -> 2-Sep, MARCH1 ->
    1-Mar): 19.6% of papers with Excel gene lists (Ziemann 2016), 30.9% in 2014-2020 (Abeysooriya 2021). In a text column
    of gene symbols (20+ labels of 2 to 15 characters with a digit or in capitals, 90%+ of its filled cells, half of
    them with a digit), a cell that is a date, or a whole number 36526 to 73050 (its serial), is no gene. Never a fix:
    the old name is unknown."""
    out = [[] for _ in range(len(df))]
    for col, t in column_types.items():
        if t != "text":
            continue
        s = df[col][~skip & ~_blank(df[col]).to_numpy()].astype(str).str.strip()
        date = s.str.fullmatch(AS_DATE)
        serial = pd.to_numeric(s.where(s.str.fullmatch(r"\d{5}(?:\.0+)?")), errors="coerce").between(*SERIALS)
        digit = s.str.contains(r"\d")
        gene = ~date & s.str.fullmatch(GENE) & s.str.len().between(2, 15) & (digit | (s == s.str.upper()))
        # ...and half of them with a digit (TP53, BRCA1; HGNC's symbols mostly are): capitals alone were US states, whose
        # stray ZIP and ISO date were 12 "dates among gene names" on 129 public tables (AH-182 build)
        if gene.sum() < 20 or gene.mean() < 0.9 or 2 * (gene & digit).sum() < gene.sum():
            continue
        for i in s.index[date]:
            out[i].append(Why(f'{col} "{s[i]}" is a date among gene names: Excel turns names such as SEPT2 or MARCH1 into '
                              "dates when they are typed or opened from a CSV", col))
        for i in s.index[serial]:
            out[i].append(Why(f"{col} {say(float(s[i]))} is the date {_serial(s[i])} as Excel stores it, a date among gene "
                              "names: Excel turns names such as SEPT2 or MARCH1 into dates when they are typed or opened "
                              "from a CSV", col))
    return out


def knobs(strength=5):
    """How hard to look, 0-10 -> (level, k). k = how many robust spreads out a value must be to count as weird.
    5 = the tuned default (k 6, bench 51/51). Each step up lowers the bar ~10% and may add a check, so a row flagged
    at s stays flagged at s+1. 0: hygiene + obvious typos; 1+: values past their column's range; 3+: breaks in a
    series; 5+: odd mixes across columns; 7+: a value past its usual limit that few others pass is worth a check (Low;
    "few" = detectors.FEW, and the sentence says how many). The floor (k 3.5 at 10) stays above the baseline band of 3.
    k alone made 5 and 10 flag the same sure mistakes on every sheet John would scan (AH-14)."""
    s = min(10, max(0, int(strength)))
    return s, 6 * 0.9 ** (s - 5)


ALONE = 7  # from this level, a value past its usual limit that few others pass is listed (Low), not only noted
# AH-205: the kind of check behind each reason, one word, so the pane can stop one kind in one column ("Stop checking
# spelling in Glass") and what a Dismiss teaches is said of the checks it can teach. The checks of one cell's own value:
# a value the user dismissed there is accepted, in that column, on every row. Never a check of a row's arithmetic, an
# order, a record, a formula, a duplicate, a blank or a value read against its row's key, label or neighbours: the same
# value is wrong in the next row (accept must never silence a sum)
KINDS = ("duplicate", "type", "blank", "placeholder", "code", "far_date", "sum", "spelling", "lost_zero", "date_form",
         "formula", "order", "gene_date", "date_order", "record", "balance", "scale", "key", "own_scale", "shifted",
         "fraction", "whole_number", "named_bound", "repeated_column", "limits", "series", "combination", "subtotal",
         "validation")
ONE_CELL = frozenset(("limits", "spelling", "type", "code", "far_date", "date_form", "lost_zero", "placeholder",
                      "gene_date", "fraction", "whole_number", "named_bound", "shifted", "validation"))
DETECTOR_KINDS = {"limits": "limits", "sequence": "series", "ecod": "combination"}


def _about(reason):
    """The column a reason is about: the first it names (the cell the pane colours first), or None."""
    return (getattr(reason, "cols", ()) or (None,))[0]


def score(df, column_types, errors_log, limits, order_by, strength=5, saved=(), grid=None, learned=None, invalid=None):
    """-> (rows, status). Severity = votes: 1 Low, 2 Medium, 3+ High. Weird limit or hygiene hit = at least Medium.
    Totals/summary rows are left out of every check (their numbers would distort the rest) and say so.
    learned (AH-205): (accepted, ignored, dismissed): the cells {(row, column)} holding a value the user dismissed in that
    column, the [kind, column] pairs the user stopped, and the rows left as they are (dismissed). A reason they mute is
    dropped before severity is decided. invalid (AH-213): [row, column] of each cell Excel says breaks its drop-down list."""
    n, skip = len(df), summary_rows(df)
    empty = df[[c for c in df.columns if c != "source_file"]].apply(_blank).all(axis=1).to_numpy()  # before totals are blanked
    tot = subtotals(df, skip, grid)  # AH-213: the totals rows themselves, judged by their formulas, before they are blanked
    df = df.copy()
    if nums := [c for c, t in column_types.items() if t in ("number", "id")]:  # (pandas 3 fails on an empty column list)
        df.loc[skip, nums] = np.nan
    errors_log = [e for e in errors_log if not skip[e[0]]]
    s, k = knobs(strength)
    # the row's own arithmetic first: a value in a cell of a rule that holds on its row is confirmed by it, never a slip
    # the limits vote on or offer a typo for (AH-74, see confirm)
    held = {}
    paired, solved, fits = pairs(df, column_types, skip, limits, held, grid)
    add = [list(dict.fromkeys(s + m)) for s, m in zip(sums(df, column_types, skip, held), paired, strict=True)]
    # a formula's value is worked out from its inputs: its odd value is theirs, so the limits never judge or name it (Net
    # =Debit-Credit said every big debit twice), and a column of formulas adds nothing to a mix of values (AH-198)
    computed = {c: np.array([row[j] is not None for row in grid]) for j, c in enumerate(df.columns)
                if grid and any(row[j] is not None for row in grid)}
    records = _records(df, column_types, skip)  # AH-198: a journal entry's lines, an order's items
    # ...and a record's own arithmetic: an amount in an entry whose debits equal its credits is no lone slip, which would
    # break the balance (a 1,184,000 machine bought, "likely 11840", AH-198 fix round 2)
    for g, run, a, b, _, ta, tb in _balanced(df, column_types, skip, records, computed):
        agree = (ta - tb).round(6).abs() < 0.005
        confirm(held, len(df), np.flatnonzero(np.isin(run, agree.index[agree])), f"{g}'s {a} and {b} agree", (a, b))
    in_step(df, column_types, skip, limits, _reads(grid, list(df.columns)), held)  # AH-208: a big row, not a slip
    # saved: the columns whose limits the user set - their limits win, so nothing is listed past the data's own band
    lim = limits_detector(df, column_types, limits, typos_only=s < 1, listing=s >= ALONE,
                          quiet=set(fairness.protected(column_types)) | set(saved), held=held, computed=computed)
    # protected columns (Age, Gender, Location...) are checked for slips like any column (limits, blanks, spellings), but
    # never used to judge whether a person is unusual: a 74-year-old is not an anomaly for being 74 (fairness blueprint)
    judged = {c: t for c, t in column_types.items() if c not in fairness.protected(column_types)
              and not (c in computed and 2 * computed[c].sum() > n)}
    # the sentence and the card name one value. Where the row's arithmetic and a typo pattern disagree, the typo wins only
    # when the rule holds with it within its own rounding: "Spend -3314.28 (likely 3314.28)" had a card of 3314.7, worked
    # out from a CPC rounded to the cent; else the arithmetic, said in the sentence too: "OnHand 1500 (likely 150)" had a
    # card of 15, StockValue 426.3 = 15 x 28.42 (AH-128)
    for i in range(n):
        for col, v in list(solved[i].items()):
            for kind in ("likely", "maybe"):
                if (old := lim[kind][i].get(col)) is None or old == v:
                    continue
                if fits[i][col](old):
                    del solved[i][col]
                    break
                del lim[kind][i][col]
                lim["reasons"][i] = [Why(r.replace(f" ({kind} {say(old)})", f" (likely {say(v)})"), *r.cols)
                                     if r.startswith(f"{col} weird limit is") else r for r in lim["reasons"][i]]
    dets = {"limits": lim,
            "sequence": sequence_detector(df, judged, order_by, k) if s >= 3 else _result(n, "strength below 3"),
            "ecod": ecod_detector(df, judged, k, limits) if s >= 5 else _result(n, "strength below 5")}
    # DBSCAN cut 2026-10-07: 90s/100k rows, 81% false alarms, bench same without it
    ran = [d for d in dets.values() if d["ran"]]
    (dup, repeats), (typ, typ_coded), (blank, spread) = duplicates(df, errors_log, column_types, skip), type_errors(df, errors_log, column_types), blanks(df, column_types, skip, errors_log, computed=computed)
    (hole, coded), far = placeholders(df, column_types, skip), far_dates(df, column_types, skip)
    zeros = lost_zeros(df, column_types, skip)
    above = order(df, column_types, skip)  # AH-178: a 10th percentile above its 90th, a Low above its High
    before = date_order(df, column_types, skip, far, records)  # AH-198: delivered before it shipped
    same = same_in_record(df, column_types, skip, records, computed)
    owed, owed_fix = balances(df, column_types, skip, records, computed)
    scaled = by_scale(df, column_types, skip, k, computed, [{c for r in said for c in r.cols} for said in lim["reasons"]])
    calc, calc_fix = formulas(df, column_types, skip, grid)  # AH-152: a typed value or another formula among a column's formulas
    # ...and where it pins the broken cell, a sum about that cell names it alone: its inputs are fine (AH-198). A part of
    # the sum too, not only its total: Net Pay typed over =Gross-Fed-SS-Medicare made "Gross Pay does not add up" name
    # Gross Pay and three deductions that were right (8 valid cells in 2 payrolls, AH-211 episodes 17 and 20)
    for i, said in enumerate(calc):
        pinned = {c for r in said for c in r.cols}
        add[i] = [Why(r, *[c for c in r.cols if c in pinned]) if " does not add up" in r and pinned & set(r.cols) else r
                  for r in add[i]]
    genes = gene_dates(df, column_types, skip)  # AH-182: a gene name Excel turned into a date
    forms, many_forms = date_forms(df, column_types, skip)
    code, coded_top = codes(df, column_types, skip)
    spell, spell_fix, missed, spell_maybe, spell_exact = spellings(df, column_types, skip)
    proven = coded_spellings(df, column_types, skip, spell_maybe)  # AH-198: "Acounts Payable" on Account 2000
    keyed = same_by_key(df, column_types, skip, computed)  # AH-198 fix round 2: a part's one unit cost
    gaps, explained = group_gaps(df, column_types, skip, computed)  # AH-208: a close date on one open claim
    # ...and a blank its label's slip explains is that slip, never a cell left out too (AH-211)
    blank = [[r for r in said if _about(r) not in explained[i]] for i, said in enumerate(blank)]
    own = own_scale(df, column_types, skip, records, computed)  # ...a x10 in one entity
    # each list of reasons with its kind (AH-205), in the order the row's sentence says them
    hyg = [("duplicate", dup), ("type", typ), ("blank", blank), ("placeholder", hole), ("code", code), ("far_date", far),
           ("sum", add), ("spelling", spell), ("lost_zero", zeros), ("date_form", forms), ("formula", calc), ("order", above),
           ("gene_date", genes), ("date_order", before), ("record", same), ("balance", owed), ("scale", scaled),
           ("spelling", proven), ("key", keyed), ("own_scale", own), ("blank", gaps), ("subtotal", tot),
           ("validation", outside_list(df, skip, errors_log, invalid))]
    # all "worth a check" (Low): a lone top value (AH-29), one its row's arithmetic confirms (AH-74), a placeholder code
    # (AH-45), many repeats (AH-48), a date column of many forms (AH-76), a column pasted twice (AH-182)
    notes = [("spelling", missed), ("shifted", shifted(df, column_types, skip)), ("fraction", fractions(df, column_types, skip)),
             ("whole_number", whole_numbers(df, column_types, skip)), ("named_bound", named_bounds(df, column_types, skip)),
             ("blank", spread), ("limits", lim["top_reasons"]), ("limits", lim["held_reasons"]), ("placeholder", coded),
             ("type", typ_coded), ("duplicate", repeats), ("date_form", many_forms), ("code", coded_top),
             ("repeated_column", repeated_columns(df, column_types, skip, grid))]
    if s >= ALONE:
        notes.append(("limits", lim["alone_reasons"]))
    touched = set()  # rows a learned rule took a reason from: their fixes are kept only for the cells still named
    if learned:
        accepted, ignored, dismissed = learned

        def keep(kind, i, said):
            if i in dismissed:
                return said
            out = [r for r in said if not ((kind, _about(r)) in ignored or kind in ONE_CELL and (i, _about(r)) in accepted)]
            if len(out) < len(said):
                touched.add(i)
            return out
        hyg = [(kind, [keep(kind, i, said) for i, said in enumerate(lists)]) for kind, lists in hyg]
        notes = [(kind, [keep(kind, i, said) for i, said in enumerate(lists)]) for kind, lists in notes]
        lim["noted_reasons"] = [keep("limits", i, said) for i, said in enumerate(lim["noted_reasons"])]
        for name, d in dets.items():  # a detector whose every reason on a row was muted no longer votes there
            if d["ran"]:
                left = [keep(DETECTOR_KINDS[name], i, said) for i, said in enumerate(d["reasons"])]
                d["votes"] = np.array([bool(v) and (bool(k) or not said) for v, k, said in zip(d["votes"], left, d["reasons"], strict=True)])
                d["reasons"] = left
    missed = [[r for _, lists in notes for r in lists[i]] for i in range(n)]
    rows = []

    typed = df.attrs.get("typed", {})

    def as_typed(said, i):
        """A percent typed as text is quoted with its own words beside the number it holds: Pulitzer's "+22%" was said
        as 0.22 and "-100%" as -1, numbers the user never typed (round 37, AH-56). The limits stay in the held units.
        Not a sum's sentence: the pane reads its total and rule back from it (fix.addUps)."""
        out = []
        for r in said:
            for c in getattr(r, "cols", ()) if " does not add up: " not in r else ():
                raw = typed.get(c, {}).get(df.index[i])
                if raw is not None and pd.notna(df[c].iat[i]):
                    v = re.escape(say(df[c].iat[i]))
                    text = re.sub(rf"((?:^|; |\b){re.escape(str(c))} |this is ){v}(?![\d.])", lambda m: f"{m[0]} ({raw} as typed)", r, count=1)
                    r = Why(text, *r.cols) if text != r else r
            out.append(r)
        return out

    def cells(said):  # the columns the row's reasons are about, in sheet order: the pane colours those cells, no other
        named = {c for r in said for c in getattr(r, "cols", ())}
        return [c for c in df.columns if c in named]

    def lone(i, v):
        """AH-198 fix round 2, weak evidence: the limits' one vote, one cell past its weird limit with no other reason on
        the row and no slip that reads it back inside its usual limits (`unexplained`): a trial's fever of 39.2 C among
        35.8-37.6 was Medium, "probably wrong". Worth a check (Low): one real extreme looks the same. On both benches
        no planted mistake and no clean row moved: each planted slip has a decimal point, a sign or a unit behind it."""
        if v != 1 or len(lim["reasons"][i]) != 1 or lim["likely"][i] or lim["maybe"][i] or solved[i] or missed[i]:
            return False
        col = lim["reasons"][i][0].cols[0]
        return bool(limits.get(col)) and unexplained(float(df[col].iat[i]), *limits[col][:4],
                                                     middle=tuple(np.nanquantile(df[col].to_numpy(dtype=float), [0.1, 0.9])))

    tot = dict(hyg)["subtotal"]  # as learned left it
    for i in range(n):
        if skip[i] and not tot[i]:  # a totals row is said only where its own formula is wrong (AH-213)
            rows.append({"severity": None, "bucket": None, "reason": "" if empty[i] else "Totals/summary row - not checked",
                         "magnitude": 0.0})
            continue
        voted = [d for d in ran if d["votes"][i] and not skip[i]]
        hygiene = [r for _, lists in hyg for r in lists[i]]
        if not voted and not hygiene and not missed[i]:
            noted = as_typed(lim["noted_reasons"][i], i)
            rows.append({"severity": "Noted" if noted else None, "bucket": None,
                         "reason": "; ".join(noted), "magnitude": 0.0, "cells": cells(noted)})
            continue
        v, weird = len(voted), bool(lim["votes"][i])
        said = as_typed(list(dict.fromkeys(hygiene + missed[i] + [r for d in voted for r in d["reasons"][i]])), i)  # dedupe, keep order
        # AH-205: [kind, column] for each reason, once, in the sentence's order (the column the reason is about, first)
        kinds = list(dict.fromkeys((kind, _about(r)) for kind, r in
                                   [(kind, r) for kind, lists in hyg + notes for r in lists[i]] +
                                   [(DETECTOR_KINDS[name], r) for name, d in dets.items() if d["ran"] and d["votes"][i] for r in d["reasons"][i]]))
        named = set(cells(said)) if i in touched else None  # a learned rule took a reason: fixes only for cells still named
        only = lambda fixes, named=named: fixes if named is None else {c: x for c, x in fixes.items() if c in named}
        rows.append({  # a possible misspelling alone is "worth a check" (Low): it may be a real name
            "severity": "High" if v >= 3 else "Medium" if v == 2 or weird and not lone(i, v) or hygiene else "Low",
            "bucket": "Duplicates" if dup[i] else "Irregularities" if weird or hygiene or missed[i] else "Behavioral",
            "reason": (f"Flagged by {v} of {len(ran)}: " if v else "") + "; ".join(said),
            "cells": cells(said),
            "magnitude": float(max((d["magnitude"][i] for d in voted), default=0.0)),
            "likely": only({**lim["likely"][i], **solved[i], **spell_fix[i], **owed_fix[i]}),  # the row's own arithmetic beats a typo pattern
            "maybe": only({**lim["maybe"][i], **spell_maybe[i]}),  # misspelling, or a typo the numbers cannot prove: a guess the user confirms
            "exact": only(spell_exact[i]),  # capitals/spaces where the usual spelling is 5x as common: safe to auto-fix
            "formula": only(calc_fix[i]),  # AH-152: the column's own R1C1 formula for a cell that broke it: the card writes it back
            "kinds": [list(p) for p in kinds],
        })
    status = {k: "ran" if d["ran"] else f"sat out: {d['sit_out_reason']}" for k, d in dets.items()}
    return rows, status
