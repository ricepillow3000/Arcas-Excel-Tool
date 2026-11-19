"""AH-206 (John's brief, 2026-11-19: keep every check local): emails, phone numbers, US Social Security numbers and
card numbers in what Ask AI sends become tokens ([EMAIL_1], [PHONE_1], [SSN_1], [CARD_1]) before anything leaves
this PC, and the AI's answer gets the real values back here, from a map that never leaves the request.

Every pattern is a bounded, linear regex (a cell can hold 32,767 characters): no nested repeats, no unbounded run
followed by something it must give back. Only the first SCAN characters of a text are read: past them nothing is ever
sent (one request is at most client.BUDGET bytes, and a cell other than the flagged one is cut at 200 characters)."""
import re

SCAN = 10_000  # characters of one text read; more than any one request can carry
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){0,7}\.[A-Za-z]{2,63}(?![\w-])")
# a card: 13 to 19 digits that start like a card (2-6: Mastercard's 2-series, Amex, Visa, Mastercard, Discover), in
# groups as cards print them (4-4-4-4, 4-6-5, 4-4-4-4-3) with one kind of separator or none; only a Luhn-valid run is
# one (a 16-digit order number fails Luhn 9 times in 10). Groups of 4+, so two dates side by side are never one
CARD = re.compile(r"(?<![\w+.-])[2-6]\d{3}([ -]?)\d{4,6}(?:\1\d{4,5}){1,2}(?:\1\d{1,3})?(?!\w|\.\d)")
# ddd-dd-dddd with an area the SSA ever issues: never 000, 666 or 900-999
SSN = re.compile(r"(?<![\w-])(?!000|666|9\d\d)\d{3}-\d{2}-\d{4}(?![\w-])")
# a phone: +country and 10-15 digits with or without separators, or a North American number written with its
# separators ((555) 123-4567, 555-123-4567, 555.123.4567; any digits: sheets are full of made-up 555-123-4567s).
# A bare run of digits is never one: an order number, an amount or a ZIP looks the same
PHONE = re.compile(r"(?<![\w+-])\+\d[\d .()-]{7,22}\d(?!\w)"
                   r"|(?<![\w+-])(?:1[ .-]?)?(?:\(\d{3}\)[ .-]?|\d{3}[ .-])\d{3}[ .-]\d{4}(?![\w-]|\.\d)")
KINDS = (("EMAIL", EMAIL), ("CARD", CARD), ("SSN", SSN), ("PHONE", PHONE))
TOKEN = re.compile(r"\[(?:EMAIL|PHONE|SSN|CARD)_\d{1,6}\]")


def luhn(digits):
    total = 0
    for k, d in enumerate(reversed(digits)):
        d = int(d) * (2 if k % 2 else 1)
        total += d - 9 if d > 9 else d
    return total % 10 == 0


def _longest(text, ok):
    """The longest start of `text` that ends at a group's end (before a space, dash, dot or bracket) and that `ok`
    takes, or None: "4111 1111 1111 1111 12/27" is a card and its expiry, a phone may be followed by a year."""
    ends = [m.start() for m in re.finditer(r"[ .()-]+", text)] + [len(text)]
    for end in sorted(ends, reverse=True):
        part = text[:end]
        if part and ok(re.sub(r"\D", "", part)):
            return part
    return None


CHECK = {"CARD": lambda d: 13 <= len(d) <= 19 and luhn(d), "PHONE": lambda d: 10 <= len(d) <= 15}


def mask(texts):
    """texts (anything but a str passes through) -> (the texts with each email, phone, SSN and card number a token,
    {token: the original}). Numbered by first appearance in this order, kind by kind, so the same input always gives
    the same tokens (the answer cache keys on the prompt); the same value is one token. A token the texts already
    hold as typed is never given out, so the answer's tokens can only mean what was masked."""
    taken = {t for s in texts if isinstance(s, str) for t in TOKEN.findall(s[:SCAN])}
    mapping, given, count = {}, {}, {}

    def token(kind, value):
        if value not in given:
            while True:
                count[kind] = count.get(kind, 0) + 1
                t = f"[{kind}_{count[kind]}]"
                if t not in taken:
                    break
            given[value], mapping[t] = t, value
        return given[value]

    def one(kind, pattern, text):
        def sub(m):
            s = m.group()
            if kind in CHECK and not CHECK[kind](re.sub(r"\D", "", s)):
                part = _longest(s, CHECK[kind])
                return token(kind, part) + s[len(part):] if part else s
            return token(kind, s)
        return pattern.sub(sub, text)

    out = []
    for s in texts:
        if isinstance(s, str):
            head = s[:SCAN]
            for kind, pattern in KINDS:
                head = one(kind, pattern, head)
            s = head + s[SCAN:]
        out.append(s)
    return out, mapping


def unmask(text, mapping):
    """The AI's text with each token this request gave out put back; any other token stays as typed (never invented)."""
    return TOKEN.sub(lambda m: mapping.get(m.group(), m.group()), text)
