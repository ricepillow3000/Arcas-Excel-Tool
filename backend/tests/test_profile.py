"""AH-169 (John, 2026-11-16, "on the PC only"): before Find problems the pane says what the sheet looks like and what the
scan will check. /profile works it out on this PC from the engine's own readings (no AI, no network), in plain words, and
never promises a check the scan won't run."""
import datetime

from test_plain_words import BANNED, DASHES, SPACED

from anomaly_hunter.server import create_app

APP = create_app()


def profile(columns, rows):
    r = APP.test_client().post("/profile", json={"columns": columns, "rows": rows})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _survey(n=120):
    rows = [["F" if k % 2 else "M", 20 + k % 50, "Yes" if k % 3 else "No", ["Daily", "Weekly", "Never"][k % 3],
             "Yes" if k % 4 else "No", 30000 + 997 * k] for k in range(n)]
    return ["Sex", "Age", "Do you own a car?", "How often do you shop online?", "Would you recommend us to a friend?",
            "Income"], rows


def _monthly(n=48):
    day = datetime.date(2020, 1, 1)
    return ["Month", "Sales"], [[(day.replace(year=2020 + k // 12, month=k % 12 + 1)).isoformat(), 100 + k] for k in range(n)]


def _ledger(n=120):
    return ["Date", "Item", "Amount"], [[f"2024-01-{1 + k % 5:02d}", f"Pen {k % 7}", 10 + k % 13] for k in range(n)]


def test_a_survey_of_people_says_so_and_what_fairness_will_compare():
    got = profile(*_survey())
    assert got["lines"][0] == "This sheet looks like a survey of people."
    assert got["about"]["people"] and got["about"]["survey"]
    assert "Sex" in got["about"]["groups"]
    fair = [line for line in got["lines"] if line.startswith("Fairness will compare")]
    assert fair and "flagged rows" in fair[0] and "across Sex" in fair[0], got["lines"]


def test_a_list_of_people_a_time_series_a_list_of_transactions_and_a_plain_table_each_say_so():
    people = profile(["Name", "Sex", "Approved"], [[f"P{k}", "F" if k % 2 else "M", "Yes" if k % 3 else "No"] for k in range(60)])
    assert people["lines"][0] == "This sheet looks like a list of people."
    series = profile(*_monthly())
    assert series["lines"][0] == "This sheet looks like a time series by Month." and series["about"]["series"] == "Month"
    ledger = profile(*_ledger())
    assert ledger["lines"][0] == "This sheet looks like a list of transactions (many rows share each Date)."
    assert ledger["about"]["ledger"] and ledger["about"]["series"] is None
    table = profile(["Item", "Units", "Price"], [[f"Pen {k}", 10 + k % 5, 2.5] for k in range(40)])
    assert table["lines"][0] == "This sheet looks like a table."


def test_a_sheet_not_about_people_says_no_fairness_check_will_run():
    got = profile(*_monthly())
    assert "No column says who the rows are, so no fairness check will run." in got["lines"]
    assert got["about"]["people"] is False and got["about"]["groups"] == []


def test_totals_dates_codes_kept_as_typed_and_words_for_no_value_are_each_named():
    rows = [[f"2024-01-{1 + k % 28:02d}", f"0{2100 + k % 50}", k % 9, 1 + k % 4, 2 + k % 3, (k % 9) + (1 + k % 4) + (2 + k % 3),
             "NA" if k % 10 == 0 else 1000 + k, -99 if k % 8 == 0 else 50 + k % 40] for k in range(80)]
    got = profile(["Order date", "ZIP", "A", "B", "C", "Total", "Income", "Score"], rows)
    lines = got["lines"]
    assert "Totals to check: Total." in lines
    assert "Dates in: Order date." in lines
    assert "Kept as typed, not as numbers: ZIP." in lines
    assert 'Written for no value: "NA" in Income and -99 in Score.' in lines, lines
    about = got["about"]
    assert about["totals"] == ["Total"] and about["dates"] == ["Order date"]
    assert about["no_value"] == {"Income": "NA"} and about["codes"] == {"Score": -99}


def test_every_line_is_plain_and_there_are_at_most_six():
    for sheet in (_survey(), _monthly(), _ledger()):
        lines = profile(*sheet)["lines"]
        assert 1 <= len(lines) <= 6
        for line in lines:
            assert line[0].isupper() and line.endswith(".") and not DASHES.search(line) and not SPACED.search(line)
            assert not BANNED.search(line), line


def test_the_same_sheet_gets_the_same_answer_every_time():
    assert profile(*_survey()) == profile(*_survey())


def test_the_groups_it_names_are_the_ones_the_scans_fairness_report_compares():
    c = APP.test_client()
    for cols, rows in (_survey(), _monthly(), _ledger(),
                       (["Name", "Sex", "Age", "Approved"], [[f"P{k}", "F" if k % 2 else "M", 20 + k, "Yes" if k % 3 else "No"] for k in range(80)])):
        scan = c.post("/scan", json={"columns": cols, "rows": rows}).get_json()
        assert sorted(profile(cols, rows)["about"]["groups"]) == sorted(scan["fairness"]["protected"]), cols


def test_the_series_it_names_is_the_one_the_scans_sequence_check_reads():
    c = APP.test_client()
    for cols, rows in (_monthly(), _ledger()):
        ran = c.post("/scan", json={"columns": cols, "rows": rows}).get_json()["summary"]["detectors"]["sequence"] == "ran"
        assert (profile(cols, rows)["about"]["series"] is not None) == ran, cols


def test_a_profile_never_opens_a_connection_off_this_pc(monkeypatch):
    # as test_a_scan_never_opens_a_connection_off_this_pc: the pane says the profile is worked out on this PC
    import socket
    import urllib.request
    tried = []

    def refuse(*a, **k):
        tried.append(a[1:2] or a[:1])
        raise OSError("a profile tried to open a connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert profile(*_survey())["about"]["people"]
    assert tried == []


def test_a_bad_body_is_a_clear_400_as_on_scan():
    c = APP.test_client()
    for body in ({}, {"columns": [], "rows": []}, {"columns": ["A"], "rows": [[1, 2]]}, {"columns": ["A"], "rows": [[{"x": 1}]]}):
        r = c.post("/profile", json=body)
        assert r.status_code == 400 and r.get_json()["error"], body


def test_an_answer_with_a_few_na_cells_is_named_as_an_outcome_as_the_scans_report_reads_it():
    # AH-172 reads an answer's "NA" as no value, so Yes/No/NA is an outcome the report compares: the profile must say so
    cols, rows = _survey()
    for k in range(0, len(rows), 10):
        rows[k][2] = "NA"
    assert "Do you own a car?" in profile(cols, rows)["about"]["outcomes"]
