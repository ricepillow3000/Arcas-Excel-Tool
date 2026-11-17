"""What the website and the notices must say to stay true and lawful (AH-185, John's legal list, 2026-11-17).

The repo's rule for prose is the one test_fix.py:642 set: a page may not make a comfortable absolute claim that
nothing in code enforces. These checks hold the other half - that the claims John IS required to make are actually
on the page, and that a page never drifts back to describing a setting as off once it is on.

Every file is read in text mode on purpose. Python's universal newlines make these checks give the same answer on a
CRLF checkout and an LF one; a regex anchored on a bare "\n" does not, which is how the website gate layer came to be
red on Windows for a correct file (AH-186).
"""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def words(rel):
    """The page's visible words, tags removed and runs of whitespace collapsed."""
    return " ".join(re.sub(r"<[^>]+>|`|\*\*", "", (ROOT / rel).read_text(encoding="utf-8")).split())


def test_every_runtime_dependency_is_named_in_the_third_party_notices():
    """BSD-3 section 2 and Apache-2.0 section 4(d) ask for the notices to travel with the binary, and Arcas.exe
    redistributes all of these. A new dependency must add its row in the same commit."""
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    names = [re.match(r"[A-Za-z0-9_.\-]+", d).group().lower() for d in declared]
    notices = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8").lower()
    assert [n for n in names if n not in notices] == [], "a runtime dependency with no row in THIRD-PARTY-NOTICES.md"
    for want in ("office.js", "plus jakarta sans", "fivethirtyeight", "cc by 4.0", "trademarks of microsoft"):
        assert want in notices, want


def test_no_privacy_page_says_the_visit_counter_is_still_switched_off():
    """The counter went live on 2026-11-05 (site/count.js holds John's code), while all three privacy pages still
    said it would count 'once John turns the counter on'. A policy describing live processing as not yet started is
    the one kind of inaccuracy that cannot be argued as a simplification."""
    live = bool(re.search(r'COUNTER\s*=\s*"[a-z0-9-]+"', (ROOT / "site" / "count.js").read_text(encoding="utf-8")))
    assert live, "site/count.js has no counter code: this test's premise is gone, re-read it before changing it"
    for page in ("PRIVACY.md", "frontend/privacy.html", "site/privacy.html"):
        said = words(page)
        for stale in ("once John turns the counter on", "once John turns it on", "with the counter on"):
            assert stale not in said, f"{page}: describes the live counter as not switched on yet"
        assert "counts its page views with GoatCounter" in said, page


def test_every_privacy_page_names_the_rights_a_reader_has_and_why_the_counting_is_allowed():
    """A privacy policy that lists only self-service buttons never tells a reader what they may ASK for."""
    for page in ("PRIVACY.md", "frontend/privacy.html", "site/privacy.html"):
        said = words(page)
        for want in ("access", "rectification", "erasure", "restriction", "portability", "objection",
                     "legitimate interest", "data-protection authority", "john4000.nguyen@gmail.com"):
            assert want in said, f"{page}: no {want}"


def test_the_website_states_its_cookie_position_and_the_pane_twin_is_not_given_website_words():
    """Cookies are a website matter: the pane has no cookies and no banner question, so this text belongs only to
    site/privacy.html, inside the one section the twins rule excludes (test_privacy_promises.py)."""
    site = words("site/privacy.html")
    for want in ("sets no cookies at all", "no local storage", "no session storage", "whole cookie policy"):
        assert want in site, want
    assert "whole cookie policy" not in words("frontend/privacy.html"), "the pane's twin was given the website's words"


def test_the_terms_say_nothing_is_charged_so_nothing_can_be_refunded():
    said = words("site/terms.html")
    for want in ("Nothing is charged for Arcas", "nothing to refund", "no payment details are ever asked for"):
        assert want in said, want


def test_the_terms_do_not_exclude_liability_the_law_does_not_let_john_exclude():
    """An unqualified 'not liable for any loss' is void in part against consumers (UK CRA 2015 s.65, Dir. 93/13).
    The clause must carry its own savings sentence, or the whole paragraph risks being read down."""
    said = words("site/terms.html")
    assert "to the fullest extent the law allows" in said
    assert "death or personal injury caused by negligence" in said
    assert "the law wins" in said


def test_the_terms_say_the_pane_is_not_a_crisis_service():
    """ai/care.py answers words of crisis with helpline numbers and no AI call. Signposting is the right shape, and
    the terms must not leave it looking like a service anyone should rely on."""
    said = words("site/terms.html")
    assert "not a crisis service" in said and "call your local emergency number" in said


def test_the_fairness_check_is_never_offered_as_a_legal_finding():
    """'flags even across groups' reads like a discrimination clearance unless the page says it is not one."""
    said = words("site/checks.html")
    assert "not a legal or compliance finding about discrimination" in said


def test_the_website_has_an_accessibility_statement_that_claims_no_more_than_is_checked():
    said = words("site/support.html")
    for want in ("Accessibility", "WCAG 2.2 level AA", "Known limits", "not been tested with every screen reader"):
        assert want in said, want
    for overclaim in ("fully accessible", "fully conformant", "meets WCAG", "no barriers"):
        assert overclaim not in said, f"accessibility statement overclaims: {overclaim}"


def test_a_link_that_opens_a_new_tab_says_so_in_words_not_only_to_a_screen_reader():
    assert "Open on GitHub (opens a new tab)" in (ROOT / "site" / "support.html").read_text(encoding="utf-8")
