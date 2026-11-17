"""AH-182: gene names Excel turned into dates. SEPT2 becomes 2-Sep and MARCH1 becomes 1-Mar when typed or opened from a
CSV: 19.6% of papers with Excel gene lists (Ziemann 2016), 30.9% in 2014-2020 (Abeysooriya 2021), sometimes as a date
serial. In a text column of gene symbols (20+ such labels, 90%+ of its filled cells), a cell that is a date (2-Sep,
Sep-2, 02-Sep-2026, an ISO date) or a whole number 36526 to 73050 (a date serial in 2000-2099: the pane sends a date
cell in a non-date column as its serial) is flagged (Medium), never with a fix: the old name cannot be proven.
Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
GENES = ["TP53", "BRCA1", "BRCA2", "EGFR", "MYC", "KRAS", "PTEN", "AKT1", "CDK4", "MDM2", "ERBB2", "PIK3CA", "NRAS",
         "BRAF", "RB1", "APC", "VHL", "ATM", "CHEK2", "SMAD4", "NOTCH1", "JAK2", "FLT3", "IDH1", "IDH2", "TET2", "DNMT3A",
         "NPM1", "WT1", "GATA2", "RUNX1", "CEBPA", "ASXL1", "EZH2", "SF3B1", "U2AF1", "SRSF2", "ZRSR2", "STAG2", "BCOR"]
WHY = "a date among gene names: Excel turns names such as SEPT2 or MARCH1 into dates when they are typed or opened from a CSV"


def scan(genes, columns=("Gene", "log2FC")):
    rows = [[g, round(((i * 37) % 23 - 11) / 7, 3)] for i, g in enumerate(genes)]
    r = APP.post("/scan", json={"columns": list(columns), "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def dated(out):
    return {i: r["reason"] for i, r in enumerate(out) if WHY in r["reason"]}


def test_a_gene_excel_turned_into_a_date_is_flagged_saying_the_date_and_why():
    for typed in ("2-Sep", "Sep-2", "1-Mar", "02-Sep-2026", "2026-09-02"):
        out = scan(GENES[:30] + [typed] + GENES[30:])
        assert dated(out) == {30: f'Gene "{typed}" is {WHY}'}, typed
        assert out[30]["severity"] == "Medium" and out[30]["cells"] == ["Gene"]
        assert not out[30]["likely"] and not out[30]["maybe"], "the old name cannot be proven: never a fix"


def test_a_date_serial_from_2000_to_2099_is_flagged_with_the_date_it_reads_as():
    for serial, day in ((36526, "2000-01-01"), (73050, "2099-12-31"), (38962, "2006-09-02")):
        out = scan(GENES[:30] + [serial] + GENES[30:])
        assert dated(out) == {30: f"Gene {serial} is the date {day} as Excel stores it, {WHY}"}, serial
    for serial in (36525, 73051, 12, 2006):
        assert dated(scan(GENES[:30] + [serial] + GENES[30:])) == {}, serial


def test_twenty_gene_labels_are_enough_and_nineteen_are_not():
    assert dated(scan(GENES[:20] + ["2-Sep"]))
    assert dated(scan(GENES[:19] + ["2-Sep"])) == {}


def test_a_column_ninety_percent_gene_labels_is_read_and_eighty_nine_percent_is_not():
    words = [f"sample note {k}" for k in range(10)]  # not gene labels: spaces, lowercase
    gene = [f"{g}{k}" if k else g for k in range(3) for g in GENES][:90]
    assert dated(scan(gene + words[:9] + ["2-Sep"]))  # 90 of 100
    assert dated(scan(gene[:89] + words + ["2-Sep"])) == {}  # 89 of 100


def test_a_plain_number_column_of_five_digit_values_is_never_read_as_dates():
    rows = [[f"R{i}", 40000 + (i * 997) % 20000] for i in range(40)]
    r = APP.post("/scan", json={"columns": ["Ref", "Amount"], "rows": rows, "strength": 5}).get_json()["rows"]
    assert dated(r) == {}


def test_a_zip_or_a_product_code_column_is_never_read_as_gene_names():
    zips = [f"{40000 + (i * 997) % 20000:05d}" for i in range(39)] + ["38962"]
    assert dated(scan(zips, ("ZIP", "Sales"))) == {}
    codes = [f"{40100 + i}-{'ABCD'[i % 4]}" for i in range(39)] + ["2-Sep"]
    assert dated(scan(codes, ("Product code", "Price"))) == {}


def test_labels_in_capitals_with_too_few_digits_are_no_gene_list():
    states = ["CT", "DC", "GA", "NC", "FL", "DE", "TN", "AZ", "NY", "VA", "NJ", "PA", "OH", "TX", "CA", "WA", "OR", "MA",
              "MI", "IL", "MN", "WI", "CO", "UT"]
    assert dated(scan(states + ["47454", "2019-09-20"], ("State", "Votes"))) == {}  # a ZIP or a date in a state column
    plain = ["EGFR", "MYC", "KRAS", "PTEN", "NRAS", "BRAF", "APC", "VHL", "ATM", "CEBPA", "BCOR", "GAPDH", "ACTB"]
    digit = [g for g in GENES if any(ch.isdigit() for ch in g)]  # 29 of them
    assert dated(scan(plain + digit[:13] + ["2-Sep"]))  # 13 of 26 with a digit: half
    assert dated(scan(plain + digit[:12] + ["2-Sep"])) == {}  # 12 of 25: under half
