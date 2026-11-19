"""AH-198: a possible misspelling is only worth a check (Low): it may be a real name. Its row's own code can prove it:
where another column's every value names one label of this column ("Account 2000" is "Accounts Payable" on every
row), "Acounts Payable" on Account 2000 is no other payee but a slip, Medium. 10+ codes of 2+ rows must show the rule.
Synthetic sheets only."""
from anomaly_hunter.server import create_app

APP = create_app().test_client()
COLS = ["Account", "Account Name", "Amount"]
NAMES = ["Accounts Payable", "Office Supplies", "Rent Expense", "Sales Revenue", "Cash at Bank", "Inventory Stock",
         "Salaries Expense", "Utilities Expense", "Accrued Wages", "Bank Charges", "Travel Expense"]


def ledger(codes=10):
    rows = [[2000, NAMES[0], 100 + k * 37 % 400] for k in range(8)]
    for c in range(1, codes):
        rows += [[2000 + 100 * c, NAMES[c], 100 + (c * 7 + k) * 37 % 400] for k in range(3)]
    rows[5][1] = "Acounts Payable"
    return rows


def scan(rows):
    r = APP.post("/scan", json={"columns": COLS, "rows": rows, "strength": 5})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["rows"]


def test_a_misspelling_its_rows_own_code_proves_is_a_slip_not_a_guess():
    out = scan(ledger())
    assert out[5]["severity"] == "Medium" and out[5]["cells"] == ["Account Name"]
    assert out[5]["reason"].startswith('Account Name "Acounts Payable" differs from the other rows of Account 2000, '
                                       'which all read "Accounts Payable"')


def test_nine_codes_are_too_few_to_prove_it_and_it_stays_worth_a_check():
    out = scan(ledger(9))
    assert out[5]["severity"] == "Low" and "differs from the other rows" not in out[5]["reason"]


def test_one_other_code_with_two_names_still_lets_the_codes_prove_it_and_two_do_not():
    # AH-211 episode 20: "Finannce" on an employee whose other rows read Finance, beside one other employee moved to
    # another department for a period: the code still names one label besides the row's own slip
    for others, want in ((1, "Medium"), (2, "Low")):
        rows = ledger(11)
        for k in range(others):
            rows[8 + 3 * (k + 1)][1] = NAMES[0]  # one row of another account under another account's name
        assert scan(rows)[5]["severity"] == want, others
