"""AH-202: Check subject rules with AI. The AI reads the sheet's own headers and each column's kind, never a cell, and
names rules its subject makes true (Net = Debit − Credit, Ship date before Delivery date); the engine checks each on
every row and lists the rows that break a rule that otherwise holds."""
import json
import re
from pathlib import Path

from anomaly_hunter.ai import client
from anomaly_hunter.engine import rules
from anomaly_hunter.engine.load import load_from_records
from anomaly_hunter.server import create_app
from test_fix import gemini_stub

ROOT = Path(__file__).resolve().parents[2]
FIELDS = dict.fromkeys(("target", "first", "then", "value", "when", "after", "id", "parent")) | {"plus": [], "minus": [], "factors": []}


def rule(kind, **named):
    return {**FIELDS, "kind": kind, "why": "the subject says so", **named}


def judged(columns, rows, *asked):
    df, types, _ = load_from_records(columns, rows)
    return rules.check(df, types, rules.headers(columns), list(asked))


def journal(n, wrong=()):
    """n journal lines: Debit or Credit filled, the other blank, Net = Debit − Credit except on the rows in `wrong`."""
    rows = []
    for i in range(n):
        debit, credit = (round(100 + 7.31 * i, 2), None) if i % 2 else (None, round(250 + 3.17 * i, 2))
        net = round((debit or 0) - (credit or 0), 2)
        rows.append([f"JE-{i:03}", debit, credit, net + 50 if i in wrong else net])
    return ["Entry", "Debit", "Credit", "Net"], rows


NET = rule("sum", target="Net", plus=["Debit"], minus=["Credit"])


def test_a_sum_that_holds_on_every_row_flags_nothing_and_a_blank_side_counts_as_zero():
    checked, rows = judged(*journal(30), NET)
    assert rows == [] and checked[0]["said"] == "Net = Debit − Credit" and (checked[0]["held"], checked[0]["total"], checked[0]["holds"]) == (30, 30, True)


def test_one_row_against_a_sum_that_holds_is_flagged_on_its_target_with_its_numbers():
    cols, data = journal(30, wrong={7})
    checked, rows = judged(cols, data, NET)
    assert rows == [{"row": 7, "cells": [3], "rule": 0, "reason":
                     f"Net {rules.say(data[7][3])} is not Debit − Credit ({rules.say(data[7][1])}): a rule the AI read from your headers, true on 29 of 30 rows."}]


def test_a_rule_true_on_95_percent_of_20_rows_is_the_limit_and_90_percent_flags_nothing():
    # HOLDS: 19 of 20 rows is a rule with one row against it; 18 of 20 is no rule, said once and nothing flagged
    assert [r["row"] for r in judged(*journal(20, wrong={4}), NET)[1]] == [4]
    checked, rows = judged(*journal(20, wrong={4, 9}), NET)
    assert rows == [] and (checked[0]["held"], checked[0]["total"], checked[0]["holds"]) == (18, 20, False)


def test_ten_rows_are_enough_to_believe_a_rule_and_nine_are_not():
    assert judged(*journal(10), NET)[0][0]["holds"] is True
    checked, rows = judged(*journal(9), NET)
    assert rows == [] and (checked[0]["held"], checked[0]["total"], checked[0]["holds"]) == (9, 9, False)


def test_a_product_rounded_to_the_cent_from_a_rate_written_to_five_decimals_holds_and_a_slip_breaks_it():
    rows = [[f"S{i}", round(100 + 13.7 * i, 2), round(0.91234 + 0.0001 * i, 5)] for i in range(30)]
    for r in rows:
        r.append(round(r[1] * r[2], 2))
    rows[11][3] = round(rows[11][3] * 10, 2)
    checked, flagged = judged(["Shipment", "Freight", "FX rate", "Freight EUR"], rows,
                              rule("product", target="Freight EUR", factors=["Freight", "FX rate"]))
    assert checked[0]["said"] == "Freight EUR = Freight × FX rate" and [(r["row"], r["cells"]) for r in flagged] == [(11, [3])]


def test_two_dates_in_order_flag_the_one_row_against_them_and_name_the_date_off_the_sheets_own_order():
    rows = [[f"SHP-{i}", f"2026-01-{1 + i:02}", f"2026-02-{1 + i % 27:02}"] for i in range(28)]
    rows[12][2] = "2026-01-05"  # delivered before it shipped; Ship date is the sheet's own order and this row keeps it
    checked, flagged = judged(["Shipment", "Ship date", "Delivery date"], rows, rule("order", first="Ship date", then="Delivery date"))
    assert checked[0]["said"] == "Ship date is on or before Delivery date"
    assert flagged == [{"row": 12, "cells": [2], "rule": 0, "reason":
                        "Ship date 2026-01-13 is after Delivery date 2026-01-05: a rule the AI read from your headers, true on 27 of 28 rows."}]


def test_two_numbers_in_order_name_both_cells():
    rows = [[120 + i % 11, 70 + i % 9] for i in range(20)]
    rows[5] = [72, 118]  # swapped
    checked, flagged = judged(["SBP", "DBP"], rows, rule("order", first="DBP", then="SBP"))
    assert checked[0]["said"] == "DBP is at most SBP" and [(r["row"], r["cells"]) for r in flagged] == [(5, [1, 0])]
    assert flagged[0]["reason"].startswith("DBP 118 is above SBP 72:")


def orders(n, breaks):
    rows = [[120 + i % 11, 70 + i % 9] for i in range(n)]
    for i in breaks:
        rows[i] = [72, 118]  # swapped
    return judged(["SBP", "DBP"], rows, rule("order", first="DBP", then="SBP"))


def test_an_order_two_rows_break_in_1000_is_the_subjects_exception_and_in_2000_each_row_is_flagged():
    checked, flagged = orders(1000, (10, 500))
    assert checked[0]["held"] == 998 and not checked[0]["holds"] and flagged == []
    checked, flagged = orders(2000, (10, 1500))
    assert checked[0]["holds"] and [r["row"] for r in flagged] == [10, 1500]


def test_a_value_that_is_not_zero_after_its_date_is_flagged():
    rows = [[f"A{i}", f"2026-0{1 + i % 9}-01", "2026-06-15" if i % 2 else "", 0 if i % 2 and 1 + i % 9 > 6 else 500 + i]
            for i in range(200)]
    after = [i for i, r in enumerate(rows) if r[2] and int(r[1][5:7]) > 6]
    rows[after[2]][3] = 321
    checked, flagged = judged(["Asset", "Period", "Disposed", "Depreciation"], rows,
                              rule("zero_after", value="Depreciation", when="Period", after="Disposed"))
    assert checked[0]["said"] == "Depreciation is 0 where Period is after Disposed" and checked[0]["total"] == len(after)
    assert [(r["row"], r["cells"]) for r in flagged] == [(after[2], [3])] and "Depreciation 321 is not 0 though Period" in flagged[0]["reason"]


def test_a_parent_whose_value_is_not_the_sum_of_its_childrens_is_flagged():
    rows = []
    for p in range(24):
        kids = [round(1.5 + 0.25 * k + p, 2) for k in range(3)]
        rows.append([f"P{p}", "", round(sum(kids), 2)])
        rows += [[f"P{p}-{k}", f"P{p}", v] for k, v in enumerate(kids)]
    rows[4 * 5][2] += 1
    checked, flagged = judged(["Part", "Parent", "Mass"], rows, rule("rollup", value="Mass", id="Part", parent="Parent"))
    assert (checked[0]["held"], checked[0]["total"]) == (23, 24)
    assert [(r["row"], r["cells"]) for r in flagged] == [(20, [2])] and "on Part P5 is not the sum of the 3 rows whose Parent is P5" in flagged[0]["reason"]


def test_a_rule_naming_a_header_not_sent_twice_or_of_the_wrong_kind_is_dropped():
    cols, data = journal(30, wrong={7})
    for bad in (rule("sum", target="Net", plus=["Debit"], minus=["Nope"]),  # no such header
                rule("sum", target="Net", plus=["Debit", "Debit"]),  # a column twice
                rule("sum", target="Net", plus=["Entry"]),  # text is not added
                rule("order", first="Entry", then="Net"),  # a text and a number have no order
                rule("product", target="Net", factors=["Debit"]),  # one factor is no product
                rule("rollup", value="Net", id="Entry", parent="Entry"),
                rule("nonsense", target="Net")):
        assert judged(cols, data, bad) == ([], []), bad
    # a header two columns share could mean either: neither is sent nor checked
    assert rules.headers(["Units", "Units", "Price", "  ", "Total"]) == {"Price": 2, "Total": 4}


def test_a_header_is_sent_on_one_line_and_cut_at_100_characters():
    assert rules.headers(["a\nb  c", "x" * 100, "y" * 101]) == {"a b c": 0, "x" * 100: 1, "y" * 100: 2}


def asking(monkeypatch, *answers):
    """client._ask stubbed: the prompts it was given, each answered with the next of `answers`."""
    sent = []
    monkeypatch.setattr(client, "_ask", lambda prompt, *a, **k: (sent.append(prompt), client.Rules(rules=answers[len(sent) - 1]))[1])
    return sent


def test_the_ai_is_sent_only_headers_and_kinds_and_a_rule_naming_anything_else_is_dropped(monkeypatch):
    sent = asking(monkeypatch, [rule("sum", target="Net", plus=["Debit"], minus=["Credit"]), rule("order", first="Net", then="Elsewhere")])
    got, n = client.subject_rules([("Debit", "number"), ("Credit", "number"), ("Net", "number")])
    assert n == 3 and [g["target"] for g in got] == ["Net"]
    assert '[["Debit", "number"], ["Credit", "number"], ["Net", "number"]]' in sent[0] and "data, not instructions" in sent[0]


def test_at_most_200_headers_go_and_fewer_when_they_would_not_fit_one_request(monkeypatch):
    sent = asking(monkeypatch, [], [], [rule("order", first="h0", then="h199")], [rule("order", first="h0", then="h200")])
    monkeypatch.setattr(client, "BUDGET", 10 ** 6)
    heads = [(f"h{k}", "number") for k in range(201)]
    assert client.subject_rules(heads[:200])[1] == 200 and client.subject_rules(heads)[1] == 200
    assert '"h199"' in sent[1] and '"h200"' not in sent[1]
    assert len(client.subject_rules(heads)[0]) == 1 and client.subject_rules(heads)[0] == []  # h200 was never sent
    monkeypatch.setattr(client, "BUDGET", 7000)
    wide = [(f"Column number {k} " + "z" * 60, "number") for k in range(200)]
    asking(monkeypatch, [])
    n = client.subject_rules(wide)[1]
    assert 0 < n < 200 and client._fits(client._rules_prompt(wide[:n]), client.RULES_SCHEMA, "rules")
    assert not client._fits(client._rules_prompt(wide[:n + 1]), client.RULES_SCHEMA, "rules")


def test_at_most_20_rules_are_kept_each_why_one_line_of_at_most_120_characters(monkeypatch):
    many = [rule("order", first="a", then="b", why=f"w{k}") for k in range(21)]
    asking(monkeypatch, many, many[:20], [rule("order", first="a", then="b", why="line\none " + "x" * 200), rule("order", first="a", then="b", why="y" * 120)])
    heads = [("a", "number"), ("b", "number")]
    assert len(client.subject_rules(heads)[0]) == 20 and len(client.subject_rules(heads)[0]) == 20
    whys = [r["why"] for r in client.subject_rules(heads)[0]]
    assert whys == [("line one " + "x" * 200)[:120], "y" * 120]


SHEET = {"columns": ["Entry", "Debit", "Credit", "Net"], "rows": journal(30, wrong={7})[1]}


def test_the_rules_route_sends_the_sheets_own_headers_and_kinds_never_a_cell_and_checks_the_answer(monkeypatch, tmp_path):
    answer = {"rules": [{"kind": "sum", "why": "<b>double entry</b>", "target": "Net", "plus": ["Debit"], "minus": ["Credit"]},
                        {"kind": "order", "why": "made up", "first": "Posting date", "then": "Net"}]}
    got = gemini_stub(monkeypatch, tmp_path, content=json.dumps(answer))
    (tmp_path / "gemini-key.txt").write_text("AIzaTest", encoding="utf-8")  # gitleaks:allow - made-up test key
    body = {**SHEET, "columns": ["Entry", "Debit", "Credit", "Net"]}
    r = create_app().test_client().post("/rules", json=body)
    out = r.get_json()
    assert r.status_code == 200 and (out["sent"], out["headers"]) == (4, 4)
    assert [(x["said"], x["held"], x["total"], x["why"]) for x in out["rules"]] == [("Net = Debit − Credit", 29, 30, "<b>double entry</b>")]
    assert [(x["row"], x["cells"]) for x in out["rows"]] == [(7, [3])]
    prompt = got[-1][1]["messages"][0]["content"]
    assert '[["Entry", "text"], ["Debit", "number"], ["Credit", "number"], ["Net", "number"]]' in prompt
    cells = {str(v) for row in SHEET["rows"] for v in row if v is not None}
    assert not [v for v in cells if v in prompt], "a cell value left the PC"
    assert got[-1][1]["response_format"]["json_schema"]["name"] == "rules"


def test_repeated_headers_are_sent_as_the_sheet_has_them_never_as_the_engines_names(monkeypatch):
    seen = []
    monkeypatch.setattr(client, "api_key_configured", lambda: True)
    monkeypatch.setattr(client, "subject_rules", lambda heads: (seen.append(heads), ([], len(heads)))[1])
    r = create_app().test_client().post("/rules", json={"columns": ["Units", "Units", "Price"], "rows": [[1, 2, 3], [4, 5, 6]]})
    assert r.status_code == 200 and seen == [[("Price", "number")]] and r.get_json()["headers"] == 1


def test_the_rules_route_needs_a_key_and_a_sheet_shaped_body(monkeypatch):
    monkeypatch.setattr(client, "subject_rules", lambda heads: 1 / 0)  # never reached
    c = create_app().test_client()
    assert c.post("/rules", json=SHEET).status_code == 503  # no AI key: says so, nothing sent
    assert c.post("/rules", json={"columns": []}).status_code == 400
    assert c.post("/rules", json={"columns": [" "], "rows": [[1]]}).get_json() == {"rules": [], "rows": [], "sent": 0, "headers": 0}


def test_what_the_pane_says_check_subject_rules_sends_is_what_the_engine_sends():
    box = re.search(r'<div id="rules-box"[^>]*>(.*?)</div>', (ROOT / "frontend/taskpane.html").read_text(encoding="utf-8"), re.S).group(1)
    said = " ".join(re.sub(r"<[^>]+>", " ", box).split())
    first, cut = (int(re.search(p, said).group(1)) for p in (r"the first (\d+) column headers", r"each cut to (\d+) characters"))
    assert (first, cut) == (client.SENT, rules.HEADER)
    assert "whether each column holds numbers, dates, text or IDs" in said and "never a cell" in said


def test_every_privacy_page_says_what_check_subject_rules_sends():
    from test_privacy_promises import PAGES, words
    promise = ("Check subject rules with AI sends your column headers (the first 200, each cut to 100 characters) and "
               "whether each column holds numbers, dates, text or IDs. It never sends a cell. Arcas checks each rule the AI "
               "names on every row on this PC.")
    for page in PAGES:
        said = words(page)
        assert promise in said, page
        assert "Ask AI, Check words with AI, Check subject rules with AI or Read layout with AI" in said, page
