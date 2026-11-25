"""What the sheet looks like and what a scan will check, said before the scan (AH-169, John 2026-11-16: "on the PC
only"). Read with the scan's own functions, so it never promises a check the scan won't run; it explains and changes
nothing the scan finds."""
from anomaly_hunter.engine import fairness
from anomaly_hunter.engine.detectors import series_gate
from anomaly_hunter.engine.load import load_from_records, numbers
from anomaly_hunter.engine.pipeline import _survey, named_totals, scale_groups, summary_rows


def _names(cols, most=5):
    """"A, B and C"; past `most`, "A, B, C, D, E and 3 more"."""
    cols = [str(c) for c in cols]
    if len(cols) > most:
        cols = cols[:most] + [f"{len(cols) - most} more"]
    return cols[0] if len(cols) == 1 else ", ".join(cols[:-1]) + " and " + cols[-1]


def profile(columns, rows):
    """-> {"lines": [at most 6 plain sentences], "about": {the same, as fields}}."""
    df, types, _ = load_from_records(columns, rows)
    _, fdf, ftypes, prot = fairness.people(df, types)
    # what report() compares across the groups besides the flagged rows (none without a group: it compares nothing)
    outcomes = list(dict.fromkeys(v[2] for v in fairness._outcomes(fdf, ftypes, prot)[0].values())) if prot else []
    amounts = list(dict.fromkeys(v[2] for v in fairness._amounts(fdf, ftypes, prot).values())) if prot else []
    # the sequence check reads the columns that are not protected (pipeline.score's `judged`)
    judged = {c: t for c, t in types.items() if c not in fairness.protected(types)}
    by, _, _, _, why = series_gate(df, judged)
    ledger = bool(why and why.startswith("not a time series (many rows share"))
    nums = numbers(types)
    about = {"people": bool(prot), "survey": _survey(list(types)), "series": None if why else by, "ledger": ledger,
             "groups": list(prot), "outcomes": outcomes, "amounts": amounts,
             "totals": named_totals(nums) if len(nums) > 3 else [],  # pipeline._totals reads 4+ number columns
             "dates": [c for c, t in types.items() if t == "date"], "ids": [c for c, t in types.items() if t == "id"],
             "no_value": {c: w for c, (_, w) in df.attrs["no_value"].items()},
             "codes": {c: int(code) for c, (_, code) in df.attrs["codes"].items()},
             # AH-223 ("show why"): a column whose groups each keep their own normal, and the column that names them
             "by_group": {c: g for c, (g, _, _) in scale_groups(df, types, summary_rows(df)).items()}}
    kind = ("a survey of people" if about["people"] and about["survey"] else "a survey" if about["survey"]
            else "a list of people" if about["people"] else f"a time series by {by}" if about["series"]
            else f"a list of transactions (many rows share each {by})" if ledger else "a table")
    lines = [f"This sheet looks like {kind}." + "".join(
        f" {_names([c for c, h in about['by_group'].items() if h == g])} judged within each {g}."
        for g in dict.fromkeys(about["by_group"].values()))]
    lines.append(f"Fairness will compare {_names(['flagged rows', *outcomes, *amounts])} across {_names(prot)}." if prot
                 else "No column says who the rows are, so no fairness check will run.")
    if about["totals"]:
        lines.append(f"Totals to check: {_names(about['totals'])}.")
    if about["dates"]:
        lines.append(f"Dates in: {_names(about['dates'])}.")
    if padded := list(df.attrs["padded"]):
        lines.append(f"Kept as typed, not as numbers: {_names(padded)}.")
    said = [f'"{w}" in {c}' for c, w in about["no_value"].items()] + [f"{code} in {c}" for c, code in about["codes"].items()]
    if said:
        lines.append(f"Written for no value: {_names(said)}.")
    return {"lines": lines, "about": about}
