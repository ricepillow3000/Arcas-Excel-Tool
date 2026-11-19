"""AH-206: what Ask AI sends has its emails, phones, SSNs and card numbers as tokens, and only those: each shape is
masked at its very edge and its look-alikes (dates, amounts, ZIPs, order ids) are left as typed. Synthetic values only."""
import time

import pytest

from anomaly_hunter.ai import pii


def masked(text):
    return pii.mask([text])[0][0]


def with_check_digit(body):
    """The Luhn check digit that makes `body` a valid card number."""
    return next(body + str(d) for d in range(10) if pii.luhn(body + str(d)))


@pytest.mark.parametrize("text,token", [
    ("anna.smith@example.com", "[EMAIL_1]"), ("a+tag@mail.example.org", "[EMAIL_1]"), ("anna@example.co.uk", "[EMAIL_1]"),
    ("x@ab.io", "[EMAIL_1]"),  # a two-letter top-level domain, the shortest
    ("(555) 123-4567", "[PHONE_1]"), ("555-123-4567", "[PHONE_1]"), ("555.123.4567", "[PHONE_1]"),
    ("1-555-123-4567", "[PHONE_1]"), ("+1 555 123 4567", "[PHONE_1]"), ("+44 20 7946 0958", "[PHONE_1]"),
    ("+4915123456789", "[PHONE_1]"), ("+33 1 23 45 67 89", "[PHONE_1]"),
    ("001-23-4567", "[SSN_1]"), ("123-45-6789", "[SSN_1]"), ("665-12-3456", "[SSN_1]"), ("667-12-3456", "[SSN_1]"),
    ("899-12-3456", "[SSN_1]"),  # the last area before 900
    ("4111 1111 1111 1111", "[CARD_1]"), ("4111-1111-1111-1111", "[CARD_1]"), ("4111111111111111", "[CARD_1]"),
    ("5555555555554444", "[CARD_1]"), ("378282246310005", "[CARD_1]"), ("3782 822463 10005", "[CARD_1]"),
    ("6011111111111117", "[CARD_1]"), ("2223 0000 4840 0011", "[CARD_1]"),  # Mastercard's 2-series
    ("4222222222222", "[CARD_1]"),  # 13 digits, the fewest
])
def test_each_kind_is_masked_in_the_shapes_people_type_it(text, token):
    assert masked(text) == token and masked(f"see {text}, today") == f"see {token}, today"


def test_a_card_of_19_digits_is_masked_and_one_digit_more_or_fewer_than_13_to_19_is_not():
    nineteen = with_check_digit("601100000000000000")
    assert masked(nineteen) == "[CARD_1]"
    assert masked(with_check_digit("6011000000000000000")) == with_check_digit("6011000000000000000")  # 20 digits
    assert masked(with_check_digit("42222222222")) == with_check_digit("42222222222")  # 12 digits


def test_a_card_followed_by_its_expiry_is_masked_and_the_expiry_kept():
    assert masked("4111 1111 1111 1111 12/27") == "[CARD_1] 12/27"


@pytest.mark.parametrize("text", [
    "2024-01-15", "2024-01-15T10:30:00Z", "01/15/2024", "15.01.2024", "12.31.2024", "10:30:45", "2024-01-15 2024-01-16",
    "$1,234,567.89", "1234567.89", "-3314.28", "12345", "02134", "12345-6789", "ORD000123", "ORD-555-123-4567", "INV-2024-000123",
    "2024", "42", "5551234567",  # a bare run of digits: an order number or an amount looks the same
    "4111111111111112",  # 16 digits that fail Luhn: one digit off a valid card
    "1000000000000008", "7000000000000005",  # Luhn-valid, but no card starts with a 1 or a 7
    "000-12-3456", "666-12-3456", "900-12-3456", "999-12-3456",  # areas the SSA never issues
    "qty@2.50", "3 units @ 2.50", "@handle", "user@localhost", "192.168.1.1", "+12.5%", "v1.2.3", "R+51.5", "16A",
])
def test_dates_amounts_zips_ids_and_look_alikes_are_left_as_typed(text):
    assert masked(text) == text


def test_the_same_value_is_one_token_numbered_by_first_appearance_and_the_answer_gets_it_back():
    texts = ["Anna anna@example.com", 42, None, "call +1 555 123 4567 or anna@example.com", "bob@example.com 123-45-6789"]
    out, mapping = pii.mask(texts)
    assert out == ["Anna [EMAIL_1]", 42, None, "call [PHONE_1] or [EMAIL_1]", "[EMAIL_2] [SSN_1]"]
    assert mapping == {"[EMAIL_1]": "anna@example.com", "[PHONE_1]": "+1 555 123 4567", "[EMAIL_2]": "bob@example.com",
                       "[SSN_1]": "123-45-6789"}
    assert pii.mask(texts) == (out, mapping)  # the same input, the same tokens: the answer cache keys on the prompt
    assert [pii.unmask(t, mapping) if isinstance(t, str) else t for t in out] == texts


def test_a_token_the_request_never_gave_out_stays_as_typed():
    _, mapping = pii.mask(["anna@example.com"])
    assert pii.unmask("[EMAIL_1] and [EMAIL_2], [CARD_1]", mapping) == "anna@example.com and [EMAIL_2], [CARD_1]"


def test_a_token_the_sheet_already_holds_is_never_given_to_a_real_value():
    # a cell typed "[EMAIL_1]" (a prompt injection, or a template) must come back as typed, never as someone's address
    out, mapping = pii.mask(["[EMAIL_1]", "anna@example.com"])
    assert out == ["[EMAIL_1]", "[EMAIL_2]"] and mapping == {"[EMAIL_2]": "anna@example.com"}
    assert pii.unmask("[EMAIL_1] [EMAIL_2]", mapping) == "[EMAIL_1] anna@example.com"


@pytest.mark.parametrize("cell", ["a" * 100_000, "1" * 100_000, "4" * 100_000, "a@" * 50_000, "x.y@" * 25_000,
                                  "+1 " * 33_334, "1-" * 50_000, "4111 " * 20_000, "(555) " * 16_667, "a@b." * 25_000])
def test_a_100000_character_cell_is_masked_in_a_blink(cell):
    t = time.perf_counter()
    pii.mask([cell])
    assert time.perf_counter() - t < 0.2


def test_past_the_first_10000_characters_nothing_is_read_since_no_request_carries_that_much():
    out, _ = pii.mask(["x" * pii.SCAN + " anna@example.com", "x" * (pii.SCAN - 17) + " anna@example.com"])
    assert out[0].endswith(" anna@example.com") and out[1].endswith(" [EMAIL_1]")
