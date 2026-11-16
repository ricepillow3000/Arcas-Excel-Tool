# AH-171 critique: boring vs interesting, complicated vs simple

Main 7f60461 (7d8f559 + merge), 1280x800 and 390x844. Visitors: office manager (A), sceptical analyst (B), IT (C).
Home height: 4,744 px desktop (5.93 screens), 8,397 px phone (9.95). **Anything added must be paid for.**

## Measured facts that drive the ranking

- **The sample stays grey until you scroll.** After 10 s with no scroll, `#preview[data-loading]` is still set at
  1280x800, 1440x900 and 390x844. It is cleared only at 1920x1080. At 1280 the first flagged row (row 11) sits at y=683,
  on screen, but it is drawn as beige bars (`desk-t5000.png`). In the first 5 s the visitor sees the headline, three
  buttons and a skeleton. The proof (red cells, "Fix: Units 57") needs a scroll first.
- **4 of the sample's 7 findings say the same thing:** "Total jumped sharply near <date>" (worth a check). All 4 stay
  after the fixes (`desk-sample.png`, `desk-sample-afterfixes.png`).
- **The pane picture is unreadable.** It is drawn 182x452 on desktop and 120x297 on a phone, from a 360x900 image, so
  its text is about 4 to 6 px (`desk-scroll-02.png`).
- **The checks use 3 sets of names:** home (Spelling, Formulas, Numbers...), the sample's filters (Totals that don't
  add up, Typing slips...) and checks.html (Reconciliation, Keying errors, Consistency...). **checks.html, "Every
  check Arcas runs", has no Formulas row** (`grep -ci formula checks.html` = 0), although the home page lists it.
- **The install path is 13 steps, not 4.** The site shows 4. The "Start here" workbook adds 9 more
  (`practice.STEPS`: 5 clicks to add the add-in, then Practice, Arcas, Find problems, a row). On the way, Windows warns
  3 times: the browser's "not commonly downloaded", SmartScreen, and the "Anomaly Hunter local CA" certificate.
- **On a phone the download bar offers "Download for Windows"** over the sample (`phone-sample.png`). The hero says to
  open the page on a Windows computer, but gives no way to get it there.

## Website, home page in order

**Hero.** INTERESTING and SIMPLE: headline and one-sentence lead (A gets it in 5 s). BORING: "Free for Windows" said
3 times. COMPLICATED: 3 equal buttons; "Contact John" competes with the sample.

**Sample scan.** INTERESTING, keep: the best thing on the site; red cells, "Fix: Units 42" and the detail box's
"83.58 ÷ 1.99" win B over (`desk-sample-row22.png`).
BORING: the skeleton described above. The 4 identical jump rows make the demo read as noise to B. The **Scanning**
tab is a 622 px panel, mostly empty, with a bar and three lines (`desk-sample-scanning.png`), and it plays *after* the
results: time runs backwards. COMPLICATED: the tabs read Findings, Scanning, After fixes, which is not the real order.
Fixes are shown but cannot be accepted, so the pane's real loop (row, card, Accept) is never felt. On a phone, 357 px
of filters come before the first data row.

**What it checks.** INTERESTING: the "Row 31" links. SIMPLE: a line each. BORING: 6 look-alike blocks, an unreadable
pane picture.

**Who made Arcas.** INTERESTING and SIMPLE: a real face, phone and email build trust. Keep.

**Proof strip.** INTERESTING: the count-up and the humble note. BORING: 585 px (855 phone) for 3 look-alike figures
and 3 links to one file (`desk-scroll-03.png`).

**Download.** SIMPLE: four numbered steps, IT details closed. BORING: the 160 px crest between the lede and the
button is decoration, which John's own rule rejects. COMPLICATED: step 3's "Anomaly Hunter local CA, Arcas's old name".
The hidden 9 workbook steps surprise A after she has committed. Nothing says how long it takes.

**Questions and form.** SIMPLE: 5 closed questions. COMPLICATED: the form opens with about 60 words of warnings and
needs a GitHub account. "Email John instead" is the easier path for A, but it is the secondary button.

## Other pages

- **checks.html:** two stacked headings ("Every check Arcas runs", then "Every row, held to the same standard", which
  reads like a slogan). Jargon: Reconciliation, Keying errors, "a cycle of 5, 7, 12, 24, 52 or 168 rows". Missing
  Formulas.
- **cases.html:** the most insightful content (Levon dated 1071, a published #DIV/0!), behind a text link and a
  600 px hero.
- **support.html:** SIMPLE: answers first, a clear IT ledger. Fine.

## Pane (judged from `after/1-start.png`, `2-results.png`, `3-card.png`; 5055 not used)

- INTERESTING: the card's "C11: -5 → 57" with the reason in the row's own numbers. Accept and Dismiss side by side.
- SIMPLE: one wine button, and options folded away.
- COMPLICATED: before any scan, a 10-step slider, 3 labels, a hint and "How we tested this level". Results open with
  a 40-word paragraph. Each card puts a text box, 3 starters and Ask AI under Accept: about 450 px, more than the card.
- BORING: after Accept or Dismiss nothing counts down. The user gets no "2 of 5 checked" and no sense of finishing.

## Fixes, ranked by impact per effort (TOP 6 marked ★)

1. ★ **Play the sample on the first screen.** Start the skeleton's sweep once the hero's entrance has ended and the
   first flagged row is on screen, not only when 60% of the sheet is. Why: the proof is seen in 3 s, not after a
   scroll. Height: 0. Tests: `test_site.mjs` skeleton block ("30% in view still waits, at 70% it plays", glide-wait).
   Risk: low. John asked for the skeleton to be noticeable, and it would still play once.
2. ★ **Accept in the sample.** Add an Accept button to the detail box of rows 11, 22 and 31. It writes the fix into the
   cell (the gold `mended` line the After fixes panel already has), the counts tick down (`data-after` values exist),
   and after the third the verdict shows "Scan complete: 0 probably wrong, 4 worth a check". It teaches the pane's
   real loop with the visitor's own hand. Height: 0 (inside the box). Tests: `test_site_sample.py` (the end state must
   equal the After fixes panel, already rescanned), the tab and filter blocks in `test_site.mjs`. Risk: medium (many
   pinned tab behaviours).
3. ★ **Phone: "Send this page to my computer"** in place of the dock's and hero's Download on a phone. Use
   `navigator.share`, or a `mailto:` to yourself with the link (the site already builds mailto links; nothing is
   loaded). Why: a shared link mostly opens on a phone, and today that is a dead end. Height: 0. Tests: the download-bar
   block (AH-126) and the privacy twins' wording about forms. Risk: low.
4. ★ **Say the whole install honestly, with a time.** One line over the steps: "About 2 minutes. Windows warns you 3
   times; that is expected. Then 5 clicks in Excel add Arcas." Step 3 says "a certificate that lets Excel talk to Arcas
   on this PC", and the old name moves into IT details. Pay for it by **removing the 160 px crest**, a net -100 px.
   Tests: `test_site.mjs` steps and IT blocks, `test_plain_words.py`. Risk: low.
5. ★ **One vocabulary, and the missing Formulas row.** Use the home page's six names everywhere: the filters'
   group heads and checks.html's rows. Add Formulas to checks.html, with its pane sentence as the example. Drop the
   second h1-sized heading. Why: B stops at "every check" that leaves out one the home page promised. Height: about
   0 at home, -150 px on checks.html. Tests: `test_site_sample.py:392-410`, `test_site.mjs:520-521`, CLAUDE.md
   map. Risk: low to medium.
6. ★ **Pane: a countdown to done.** Under "5 of 300 rows look wrong.", show "3 left to check" after each Accept or
   Dismiss, and "All 5 checked." at the end, said once with the check mark the pane already draws. It gives a finish
   line, and is the one reward loop the pane lacks. Height: 0 (the held `#status` space). Tests: selfcheck
   `summaryOf`, e2e results block. Risk: low.
7. **Pane: no decision before the first scan.** "Level 5 of 10, recommended · Change" as one line until the first
   results. About -200 px. Tests: e2e slider, selfcheck. Risk: medium.
8. **Pane: fold Ask AI under "Want a different fix?"**: about -400 px a card. Tests: e2e Ask AI and care. Risk: medium.
9. **A readable pane picture:** a 1:1 crop of the card ("C11: -5 → 57", Accept, Dismiss), about 360x420. Height
   about 0. Tests: the AH-156 block. Risk: low.
10. **Proof strip in one line**: "51 of 51 planted mistakes found · 199 of 201 in sheets it had never seen · 0 correct
    rows called wrong", one link to the record, and the note kept. Height: -300 px desktop, -450 px phone. That frees
    budget for 2 or 4. Tests: the AH-133 and AH-159 proof checks, the count-up. Risk: low.
11. **Drop the Scanning tab** (time backwards, 622 px of air). Tests: AH-147 block. A pinned feature: ask John.
12. **Hero: two buttons** (Contact John to the questions; "Free for Windows" once): -60 px. 13. **A case teaser**
    under the proof ("a published table dated a song 1071", to cases.html): +30 px, paid by fix 10.

Not recommended: a looping demo, hero decoration, testimonials (motion rules, budget, John's taste). The jump
sentences are the engine's words; removing the 4 jumps means a new sample sheet and is against AH-167's humility: ask John.
