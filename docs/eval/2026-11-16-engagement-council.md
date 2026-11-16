# AH-171 Council: build plan

## Claims checked
- Skeleton until scroll: CONFIRMED (`home.js:104-109`, 60% rule; `desk-t5000.png`).
- 4 of 7 rows say "Total jumped sharply": CONFIRMED (rows 5, 21, 41, 57; the engine's words).
- No Formulas row on checks.html: CONFIRMED.
- 13 install steps: PARTLY. The hidden cost is `practice.STEPS`' 5 add-in clicks. Its 4 "try it" steps are practice.
- Phone dock offers a Windows download: CONFIRMED.
- Pane picture unreadable: CONFIRMED (`styles.css:421` 180 px, `:934` 118 px).
- 160 px crest is decoration: WRONG. John brought it back on 2026-10-30 (`test_site.mjs:1310`).
- Scanning tab order: CONFIRMED (AH-147, pinned).
- Pane slider before first scan: CONFIRMED.
- No countdown after Accept: CONFIRMED (`fix.js:322`).

## Build, in order (one PR)

### 1. The sample plays on the first screen (Critic 1, BUILD WITH CHANGES)
`home.js` `skeleton()`: if at mount, before any scroll, `#r11`'s layout bottom (not its entrance transform) is inside the screen, it counts as seen. It plays a third into the entrance, through the existing `later(play, …)`. Otherwise the 60% and glide rules stay. Phone: unchanged.
- Test first (browser): at 1280x800 and 1440x900, no scroll, "play" by ENTERED+500 ms, one sweep, gone 1.3 to 2.4 s after play, CLS 0. At 390x844, still "" at ENTERED+1 s. Red today.
- Change: the below-the-fold, 30%/60% and glide blocks move to 1440x600, where row 11 starts below the fold. Same assertions.
- Height 0. Motion unchanged; nothing under reduced motion. Risk: low. Run all of `--browser`.

### 2. Accept in the sample (Critic 2, BUILD WITH CHANGES)
In `#m11`, `#m22` and `#m31` only, add `<button type="button" class="btn btn-primary m-accept">Accept</button>`. On press:
- The row's cells in `#p-found` become the same row's cells from `#p-clean`: the mended cell and "Fixed: Units 57, was -5", already proven against the engine's rescan.
- The row keeps its `id` and loses its `data-kind` and row button. The box closes and focus goes to the row's `th`.
- The filter and key counts are recounted from the rows still flagged, through the existing `count()`.

No number is made up: after three, every count equals its `data-after`. No automatic tab turn, no storage.
- Caption: "…Click a flagged row for its detail, and Accept its fix: each fix comes from the row's own numbers or the column's usual spelling."
- Tests first: `test_site_sample.py`: an Accept only where `#p-clean` mends the row, naming that cell's value. `test_site.mjs`: after each press the row equals `#p-clean`'s row; after three the counts equal `data-after`; focus is on the row. Under reduced motion counts are set, not counted. "accepted" becomes an AA state (48). The box still opens inside the findings at 1280 and 390.
- Height 0 (inside the popover). Risk: medium.

### 3. Pane: a finish line (Critic 6, BUILD WITH CHANGES)
After a successful Accept, Dismiss or Undo, `#notice` in the foot bar (nothing moves, AH-165) says "2 of 5 rows done." and at the end "All 5 rows done." (one row: "1 of 1 row done."). The count comes from `doneOf(rows, decided)` in `scan.js` (`flaggedRows` against `state.decided`). Silent before the first decision. Failures stay on the card (AH-149).
- Tests first: selfcheck pins `doneOf` (0, some, all, 1 of 1, after an Undo). e2e: Accept, then "1 of 5 rows done."; Dismiss, then "2 of 5"; Undo, then "1 of 5".
- Height 0, no motion. Risk: low.

### 4. checks.html: Formulas, plain names, one heading (Critic 5, BUILD WITH CHANGES)
- Renames: Reconciliation, Keying errors and Consistency become the sample filters' names ("Totals that don't add up", "Typing slips", "Same word, typed two ways"). "Missing values" becomes "Blanks and duplicates".
- New row after the totals: **Formulas** | "A cell that breaks its column's formula: a number typed over it, or a formula that points one row off." | "None in this sample: it has no formulas" + "On another sheet:" and the engine's own sentence (for example "Total 400 is a typed number where the column's other rows use a formula").
- Delete the h2 "Every row, held to the same standard". Move `id="checks-title"` to the h1.
- Tests first: the new list at `test_site_sample.py:392`. The fact stays `len(checks)` ("9 checks · 7 rows flagged…"). The Formulas sentence comes from scanning a small sheet with `formulas` through the engine, like the fairness example. `test_site.mjs`: every home check name heads a row or starts one.
- Height on checks.html about −100 px. Risk: low.

### 5. Install step 4 names the clicks (Critic 4, BUILD WITH CHANGES)
Step 4: "Excel opens a "Start here" workbook. The first time, it shows 5 clicks that add Arcas to Excel. Then try its Practice tab and press **Find problems**."
- Test first: read "(N clicks)" from `practice.py`; step 4 must say "shows N clicks".
- The certificate's name stays: it is what Windows' box shows. The crest stays. No time claim. Height about +20 px.

### 6. Phone: email yourself the link (Critic 3, BUILD WITH CHANGES: a mailto, no script)
- `#dock`: `<a class="btn btn-primary" href="mailto:?subject=Arcas%20for%20Excel&body=<canonical URL + #download, encoded>">Email yourself the link</a>`.
- Hero phone line: "Arcas runs on a Windows computer. Open this page on that computer to download it, or email yourself the link." ("email yourself the link" is the same link.)
- Tests first: `test_site.mjs:123` and `:884` pin the new markup, and the body must be the canonical URL + `#download`. The no-address mailto passes "only John's email". The privacy twins send nothing new: run them.
- AH-126 and AH-148's rules for when the dock shows are unchanged. Height about +20 px on phone. Risk: low.

### 7. Proof strip, shorter (Critic 10, BUILD WITH CHANGES; it pays for 5, 6 and 8)
- Remove the lede.
- New words for the three figures: "planted mistakes found in 27 test sheets" / "found in 42 more test sheets it had never seen" / "correct rows called probably wrong in those test sheets, out of 2,724 and 6,954 clean rows".
- One line under the figures: "From the stress test of 5 November 2026." (a link). The note and the cases link stay.
- Tests: the figures are still read from the record (`:436-440`). `:442` becomes "the strip links the record once, under it". `:709` gets the new 0 sentence, still "in those test sheets". In `:1948`, `#proof .sec-lede` becomes `#proof .proof-note`.
- Height: desktop about −150 px, phone about −250 px.

### 8. A pane picture you can read (Critic 9, BUILD WITH CHANGES: crop the same asset)
- `.shot img`: drawn 1:1 at 360 px (`max-width: calc(100% - 2px); height: auto; aspect-ratio: 360 / 400; object-fit: cover; object-position: 50% <y>`). The window shows "5 of 300 rows look wrong." through Row 11. On a phone the figure is one column.
- Alt: "…the rows to check start with Row 22 and Row 11, each with its reason".
- Tests: the AH-156 asset checks stay. Add: drawn width ≥ 340 px at 1280 and ≥ 300 px at 390, CLS 0.
- Height: desktop about 0, phone about +180.
- **Gate: after items 5 to 8 the phone home is at most today's 8,397 px. If not, shorten the crop.**

## Not built
- Critic 7, fold the slider: follow-up AH-172, as a `<details>` "How hard to look: 5 of 10", with the start-up skeleton changed too. Too many e2e paths for this PR.
- Critic 8, fold Ask AI: AH-172, as a `<details>` "Want a different fix? Ask AI", with `#fix-care` outside the fold so failures and the care message are never hidden.
- Critic 11, drop the Scanning tab: NEEDS JOHN (AH-147 is pinned).
- Critic 12, two hero buttons: REJECT. "Contact John" is John's AH-133 choice.
- Critic 13, case teaser: REJECT. It costs page height, and the link already exists.
- Remove the crest: REJECT. John's choice.
- "About 2 minutes": REJECT. Not testable, and false on a slow PC.
- Rename the certificate step: REJECT. The user must match Windows' wording.
- Change the 4 jump rows: REJECT. They are the engine's answer, and AH-167's humility.
- `navigator.share`: REJECT in favour of the mailto (no script).

## For the Builder
- Run `python tools/check.py --e2e`. `home.js` has no mutants.
- In the same commit, update CLAUDE.md layers 11 and 12 (skeleton rule, sample Accept, dock mailto, checks names, rows-done line).
- Check every new word against `test_plain_words.py`.
