"""AH-217 (John, 2026-11-21: "AI proposes, the no-AI engine verifies, then enforces locally for free"): a subject rule
that held on the sheet is kept by the pane (its kind and the headers it names) and sent back with every /scan as
`rules`; the engine judges it again on that scan's rows with the same code as /rules (rules.check), with no AI, and a
row against it is a finding of the scan (kind "rule"), Medium as a sum's or an order's."""
import pytest

from anomaly_hunter.ai import client
from anomaly_hunter.engine import rules
from anomaly_hunter.engine.pipeline import KINDS
from anomaly_hunter.server import create_app
from test_subject_rules import journal

MAX_RULES, HEADER, LIST = 20, 100, 200  # written out: a mutant of the engine's own numbers must not move the test with it
NET = {"kind": "sum", "target": "Net", "plus": ["Debit"], "minus": ["Credit"]}


def scan(columns, rows, **extra):
    r = create_app().test_client().post("/scan", json={"columns": columns, "rows": rows, **extra})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def flagged(out):
    return {i: row for i, row in enumerate(out["rows"]) if row["severity"]}


def test_a_scan_with_no_rules_or_an_empty_list_answers_exactly_as_before():
    cols, data = journal(30, wrong={7})
    assert scan(cols, data) == scan(cols, data, rules=[]) == scan(cols, data, rules=None)


def test_a_kept_rule_flags_the_row_against_it_as_rules_does_with_no_ai(monkeypatch):
    # the same sheet through /rules (its AI stubbed to name the rule) and through /scan with the rule kept: one sentence,
    # one cell. With no rule kept the scan's own checks never see this row (a blank side read as 0)
    cols, data = journal(30, wrong={7})
    monkeypatch.setattr(client, "api_key_configured", lambda: True)
    monkeypatch.setattr(client, "subject_rules", lambda heads: ([{**NET, "why": "double entry"}], len(heads)))
    asked = create_app().test_client().post("/rules", json={"columns": cols, "rows": data}).get_json()
    assert 7 not in flagged(scan(cols, data))

    def no_ai(*a, **k):
        raise AssertionError("a scan asked the AI")
    monkeypatch.setattr(client, "subject_rules", no_ai)
    monkeypatch.setattr(client, "_ask", no_ai)
    got = flagged(scan(cols, data, rules=[NET]))
    assert list(got) == [7] and [(x["row"], x["reason"]) for x in asked["rows"]] == [(7, got[7]["reason"])]
    assert got[7]["cells"] == ["Net"] == [cols[j] for j in asked["rows"][0]["cells"]]
    assert (got[7]["severity"], got[7]["kinds"]) == ("Medium", [["rule", "Net"]])


def test_a_kept_rule_that_no_longer_holds_on_todays_sheet_flags_nothing():
    # 19 of 20 rows: a rule with one row against it; 18 of 20 (another row typed off since it was kept): no rule at all
    assert list(flagged(scan(*journal(20, wrong={4}), rules=[NET]))) == [4]
    assert flagged(scan(*journal(20, wrong={4, 9}), rules=[NET])) == {}


def test_a_kept_rule_naming_a_header_the_sheet_no_longer_has_is_skipped_silently():
    cols, data = journal(30, wrong={7})
    cols = ["Entry", "Debit", "Credit", "Net amount"]
    assert scan(cols, data, rules=[NET]) == scan(cols, data)


def test_stop_checking_mutes_a_kept_rule_in_its_column_and_an_accepted_value_never_does():
    cols, data = journal(30, wrong={7})
    assert flagged(scan(cols, data, rules=[NET], learned={"ignore": [["rule", "Net"]]})) == {}
    # a Dismiss teaches only checks of one cell's own value: the same Net is wrong on another row, as a sum's is
    assert list(flagged(scan(cols, data, rules=[NET], learned={"accept": [["Net", rules.say(data[7][3])]]}))) == [7]
    assert "rule" in KINDS


def test_a_scan_with_kept_rules_never_opens_a_connection_off_this_pc(monkeypatch):
    import socket
    import urllib.request
    tried = []

    def refuse(*a, **k):
        tried.append(a[1:2] or a[:1])
        raise OSError("a scan tried to open a connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(client, "api_key_configured", lambda: True)  # a key set changes nothing: a scan never asks
    assert list(flagged(scan(*journal(30, wrong={7}), rules=[NET]))) == [7]
    assert tried == []


ORDER = {"kind": "order", "first": "Debit", "then": "Net"}
HOSTILE = [
    "Net", {"kind": "sum"}, [NET] * (MAX_RULES + 1), [{**NET, "kind": "total"}], [{**NET, "kind": ["sum"]}], [{**NET, "why": "x"}],
    [{**NET, "said": "Net = Debit"}], [{"target": "Net", "plus": ["Debit"]}], [{**NET, "target": 7}], [{**NET, "plus": "Debit"}],
    [{**NET, "plus": ["Debit", None]}], [{**NET, "target": "N" * (HEADER + 1)}], [{**NET, "minus": ["C" * (HEADER + 1)]}],
    [{**NET, "plus": ["Debit"] * (LIST + 1)}], ["sum"], [None], [{**ORDER, "__proto__": "x"}],
]


@pytest.mark.parametrize("kept", HOSTILE)
def test_kept_rules_of_the_wrong_shape_or_too_many_are_a_clear_400_before_any_work(kept):
    cols, data = journal(30, wrong={7})
    r = create_app().test_client().post("/scan", json={"columns": cols, "rows": data, "rules": kept})
    assert r.status_code == 400 and "'rules'" in r.get_json()["error"], r.get_json()


def test_kept_rules_at_their_very_limits_are_allowed():
    cols, data = journal(30, wrong={7})
    kept = [{"kind": "order", "first": "D" * HEADER, "then": "Net"}, {**NET, "plus": ["Debit"] * LIST}] * (MAX_RULES // 2 - 1)
    kept += [{**NET, "id": None}, ORDER]
    assert len(kept) == MAX_RULES
    # the long header and the list naming Debit twice are no rule of this sheet (skipped); NET still flags row 7
    assert list(flagged(scan(cols, data, rules=kept))) == [7]
    assert {k for r in kept for k in r} <= {"kind", *rules.NAMES, *rules.LISTS} and set(rules.KINDS) == {"sum", "product", "order", "zero_after", "rollup"}
