# AH-193 Researcher 2: high-end references (awesome-design-md + the "expensive" skills)

Repo read at main 12c7f52 (v0.1.431). Read only; nothing in the repo was edited. Evidence files are in
`ah193/r2/` (called `r2/` below).

## A. What I ran or read

- **Read whole first:** `90-System/Design-Rulebook.md` (968 lines), then CLAUDE.md L11 and L12 and `docs/design/motion.md` (594 lines).
- **Skills (vault `Machine-Setup/config/skills/`):** high-end-visual-design, minimalist-ui, redesign-existing-projects, all
  of them read whole. design-taste-frontend: sections 4.1 to 4.9, 9 and 11 (the parts on type, colour, layout, density
  and redesign). Most of high-end-visual-design breaks our rules, so those ideas are listed in D.
- **References picked (6 of 76 DESIGN.md), each calm, corporate, data-first, one accent:** Stripe (finance tables,
  `tnum`, one filled button per band); IBM Carbon (square corners, 4 px grid: closest to our Swiss look); Linear
  (hairline and surface ladder, product UI as hero); Vercel (4 px scale, "large gaps + tight interior"); Apple (17 px
  body, 3 weights, one shadow at most); Claude.com (cream `#faf9f5`, hairline `#e6dfd8`: our nearest ground). Not
  picked: Notion (pastel cards, purple pill); Mercury is not in the folder. No colour or font taken from any of them.
- **Measured in Chromium** (Playwright, swiftshader, under `flock /tmp/ah-browser.lock`): the home page at 1280x800,
  1440x900, 390x844 and 320x700 (`r2/site-measure.mjs`, `site-crops.mjs`, `probe.mjs`, `probe2.mjs`, `site-after.mjs`);
  the pane at 360 and 320 x 900 through a copy of ah170p/shots.mjs with computed-style counts (`r2/pane-measure.mjs`,
  `pane-after.mjs`, `pane-measure.txt`). Before/after: the proposed CSS injected with `bypassCSP` (`r2/after.css`,
  `r2/pane-after.css`), every page and first-screen height re-measured.
- **Could not run:** getdesign.md and the live reference sites (the proxy refuses them; the vault files are the
  source); the `taste` skill (refuses localhost); PIL (broken here, so pixels were read through a canvas in the page);
  the repo gates (out of scope for a researcher).

### What the references agree on (only the traits we can borrow)

| Trait | References (file:line) | Ours today (measured) |
|---|---|---|
| Spacing | 4 px base; sections 64-96 px; card interior 24-32; tight inside, wide between (vercel.md:491-507, ibm.md:354-371, stripe.md:334-346) | site 8 px scale with no 4/12 token: raw 12px x41, 10px x12, 14px x7, 6px x7, 9/11 px; home sections 48 px |
| Leading | display 1.03-1.17, body 1.47-1.55, 3-4 ratios (apple.md:356-363, ibm.md:340-346) | site 10 ratios (0.95 to 1.55); h2 .95 at 800 |
| Weight ladder | 3 weights: Apple 400/600 ("500 deliberately absent"), IBM 300/400/600, Vercel 400/500/600 | site 5 weights: 400x116, **500x148**, 600x35, 700x126, 800x39. Pane 400/700/800 (+600 x2) |
| Hairlines | about 1.2-1.5:1 tone, one 1 px weight (vercel.md:538 `#00000014`, apple.md:321, claude.md `#e6dfd8`) | site 1 px navy (15.9:1) x101 plus `--rule` (1.7:1) x489; decorative drawn lines also navy |
| Numbers | `tnum` on every money or count (stripe.md:323-327) | already done on both surfaces (T9): no change |
| Buttons | about 48 px, 12/16 padding, 14 px label (ibm.md:412-428) | site 48 px with 13.6 px labels; pane 48/44 px with 14/13 px labels: at the bar |
| Colour | one accent, sparse: "one filled button per band" (stripe.md:440), "reach for color rarely" (ibm.md:274) | wine on **38** marks of the home page at 1280 (42 at 390); 4 of them are decorative step numerals |
| Images | product UI as the picture, flat or framed, at most one shadow (apple.md:391-402, linear.md:258-272) | real pane screenshot and photo, 1 px frame: at the bar |

## B. Findings

**F1. Site, high. A grey fog across the bottom of the navy band at 1280 and 1440.**
- Where: `.calm::before` (styles.css:146-150). The maker block is 49 px below its section top, and its paper feather
  reaches 96 px up, so it paints about 47 px over `#checks`.
- Pixels at x = w/2: 3 px above the band's edge read `121,127,141` at 1280 and `125,131,144` at 1440, about halfway to
  paper. Navy is `12,25,56`. A phone is clean (`17,30,59`), because its block sits 97 px down.
- Screenshots: `r2/fog-1280-no-preference.png`, after the fix `r2/seam-after.png`.
- Breaks: B9 (no gradient as a coloured background) and X58 (sheen). It reads as a rendering fault, which is the
  opposite of P7.
- The other band edges were checked and are clean (`probe2.mjs`): proof to download, faq to footer.

**F2. Both, medium. The drawn decorative hairlines are full navy.**
- Site: `.rule` (styles.css:801) on the steps and the proof figures. Pane: `h2::before` (global.css:93).
- They sit beside 101 structural navy borders, so every line on paper carries 15.9:1. The references keep dividers at
  about 1.2-1.5:1 and save the strong line for frames.
- B3 says gold is for lines. Gold already draws these same lines on the navy band (`.check-list .rule` uses gold-hi,
  styles.css:442), but nowhere on paper, so P28's scorecard gold is missing where most of the page lives.

**F3. Site, medium. Wine spent on decoration: the install steps' "01-04".**
- `counter(step, decimal-leading-zero)`, 800 weight, `--fs-5` (51.9 px), wine (styles.css:520). They are the biggest
  wine on the page after the headline word, larger than the proof figures (41.5 px).
- B2 says wine means flagged; P22 says nothing is highlighted for show. The leading zeros are the numbered-grid template
  look (X40's tell, here on a real sequence).
- Screenshot: `r2/sec-1280-download.png`.

**F4. Site, medium. A weight step nobody can see.**
- The sample's 148 data cells and all mono code are 500 (styles.css:310, 353, 470, 498, 506), and the notice line is 500
  (163). Beside 400 text, 500 reads as noise, and it blunts the one weight contrast that matters: a flagged cell at 800
  white on wine against its row.
- Apple drops 500 on purpose; Stripe sets money tables at a light weight with `tnum`.

**F5. Both, low-medium. The two surfaces disagree on link underlines.**
- The pane underlines links in wine (global.css:71 `a`, :142 `.link-btn`, for example "All rows to check"). The site
  underlines in gold (styles.css:107).
- Breaks P21 (both surfaces), B2 (wine on something that is not flagged) and B3.

**F6. Both, low. The main button's tracking differs.**
- Pane `.primary` has `letter-spacing: .02em` (global.css:129). Its own row buttons reset it to 0 (:139), and the site's
  `.btn` uses normal. One button class carries two trackings (P21).

**F7. Pane, low. Off-scale type.**
- 13 px is written literally in 11 declarations (global.css:77, 100, 135, 184; components.css:74, 76, 154, 206, 233, 234)
  and 15 px once (components.css:220).
- The card shows 5 sizes: 12, 13, 14, 15 and 17.5 px (`pane-measure.txt`, "card"). The references use 3 in a card.
- No proposal: putting the reasons at 14 px makes the card's first screen taller (aee04f4 budget).

**F8. Pane, low. The list's row rules stop short on the right.**
- They end 21 px from the right frame and 6 px from the left (`padding: 4px 6px` plus `scrollbar-gutter: stable`,
  components.css:130-131). See `before193-2-results.png`.
- No proposal: a 2 px change re-wrapped "Units × UnitCost" onto another line (`r2/r2a360-2-results.png`).

**F9. Site, info. Crowded by the references' measure, but the budget is spent.** Home sections are 48 px against
their 64-96, with 29 px left at 1280 (4651 of 4680) and 12 px at 390 (8385 of 8397). C1 to C4 give back 8, 5 and 26 px:
too little to buy air (+8 px on 6 sections is 96 px).

**F10. Pane, low (needs JavaScript, so not a token change).**
- "Done in 1 second." wears the wine square (components.css:77, `#notice::before`), while "Before you scan" uses navy
  for "it informs". `notice()` (components/progress.js:5) does not know whether a message is a failure.

**F11. Site, words (outside the design scope; for the Orchestrator).** index.html:353 says "it has applied to the
SignPath Foundation"; S16 says SignPath declined on 2026-11-03, with no pending claim.

**Already at the reference bar on both surfaces, no change needed:** tabular figures (T9), 0 corners (T5), one accent
colour, mono only for data (B14), 44-48 px controls (A4), the site's 1.25 type scale, a real product picture (S20).

## C. Proposed changes, ranked by impact per line of code

Measured with C1 to C4 together on the site (`r2/after.css`; add line 353, see C4): page heights 1280: 4651 →
**4643**; 1440: 4828 → 4820; 390: 8385 → **8380**; 320: 9119 → 9093; nothing scrolls sideways. Pane with C2, C5 and C6
(`r2/pane-after.css`, which also held the list-padding change rejected in D): first-screen heights at 360 px 551 / 523 /
644 → **unchanged**; at 320 px 551 / 523 / 664 → unchanged.

**C1. Close the navy band's seam (site, 1 line).**
- Site: `.band-dark + .section { overflow-y: clip; }` in styles.css after line 234. The next section's paper feather can
  no longer reach over the band. Its sideways feather and every other edge stay as motion.md:289-294 describes.
- Pane: not needed. It has no `.calm` layer; the bands meet on hard edges (global.css:81, 169, 177).
- Rules: B9, X58, P7. M1 and M16 hold (nothing new moves). T20 holds (CLS 0: clipping changes no layout).
- Test first (`tools/test_site.mjs --browser`, "AH-193 seam"): at 1280x800 and 1440x900, reduced motion, sample
  x = w/2 at 3, 10 and 30 px above `#checks`' bottom edge. Each channel must be within 20 of `#0C1938`.
  Red today (121,127,141). Green after (14,27,57 and 22,34,63).
- Height: 0. Risk: low. The maker heading's drift (.03) moves it at most about 13 px, inside its 48 px padding. Check
  the AH-133 photo block and the reveal tests.

**C2. Draw the decorative hairlines in gold on paper (both surfaces, 1 line each).**
- Site: `.rule { ... background: var(--gold); }` (styles.css:801, was `var(--ink)`). Checks keep `--gold-hi` (lines 442
  and 802 are more specific). The steps, proof figures and IT ledgers turn gold.
- Pane: `h2::before { ... background: var(--gold); }` (global.css:93, was `var(--navy)`).
- Frames, section tops, the list and the form stay navy. That gives three tiers: navy frames, gold drawn lines, and
  `--rule` dividers inside a block.
- Rules: B3 ("gold is for lines"), P28, P15, T21. M16 and M58 hold (only the colour changes; still `scaleX`, 1:1 with
  the scroll). A5 holds: forced colors still paint `h2::before` in CanvasText (global.css:196). Gold is 3.6:1 on paper
  and about 3.3:1 on paper-2, over 3:1 for a graphic.
- Test first: test_site.mjs static, the default `.rule` background is `var(--gold)`; browser, `.steps li .rule` and
  `#proof .rule` compute `rgb(153, 125, 58)` and `.check-list .rule` stays `rgb(201, 168, 90)`; selfcheck,
  `h2::before` background is `var(--gold)`.
- Height: 0. Risk: low (no test reads `.rule` colour; test_site.mjs:1879-1911 reads its `scaleX` only).
- Screenshots: `r2/dl-after.png`, `r2/r2a360-2-results.png`.

**C3. Install steps: plain numerals in navy at the proof figures' size (site, 1 line).**
- Site: `.steps li::before { content: counter(step); color: var(--ink); font: 800 var(--fs-4)/.9 var(--sans); }`
  (styles.css:520: no leading zero, navy, 51.9 → 41.5 px, the size of the proof figures, so the page has one size for
  figures).
- Pane: not needed. Its numerals are data ("5 of 10" and the counts), and they keep their colours.
- Wine marks on the home page: 38 → 34. The four steps' height at 1280 drops 8 px (download 749 → 741).
- Rules: B2, P22, X40, P11 (still 800, still bold), T9 (keep `tabular-nums`).
- Test first (browser): `getComputedStyle(.steps li:first-child, "::before")` has content `counter(step)` and colour
  `rgb(12, 25, 56)`; and a wine allow-list on index.html: every visible wine mark is a flag cell or key square,
  `.btn-primary`, `.hero-head em`, `.proof dt`, a `.sheet-map` mark, a row button's mark or a `.notice` square. Red
  today, because of the four step numerals.
- Height: −8 px (1280), −5 (390), −26 (320). Risk: low. The "Start here" step text test (`practice.STEPS`) is unaffected.

**C4. Data at 400, so the flagged 800 stands out (site, 6 declarations).**
- Site: `font-weight 500 → 400` at styles.css:163 (the notice line), 310 (`table.grid`), 353 (a filtered cell: it must
  match the plain one, see the risk), 470, 498 and 506 (mono values and code).
- Pane: not needed. Its data and reasons are already 400 and it has no 500. That leaves both surfaces on one ladder:
  400 text, 700 labels and buttons, 800 display and flagged.
- Rules: T9, P11, X19 (fewer steps). B14: mono stays data-only.
- Test first: test_site.mjs static, no `500` weight in styles.css; browser, `#p-found tbody td` computes 400; the
  existing R5 test (test_site.mjs:2930) still passes. It compares a filtered `td.q` with a plain cell, so line 353 must
  move with line 310.
- Height: 0 (measured in the totals above). Risk: medium-low. The sample's columns re-measure their widest cell, which
  is now narrower. Re-run the AH-148, AH-171 and AH-183 browser blocks. Screenshot: `r2/sample-after.png`.

**C5. Link underlines in gold on the pane, as on the site (pane, 2 declarations).**
- Pane: `a { text-decoration-color: var(--gold) }` (global.css:71) and the same on `.link-btn` (:142).
- Site: already gold (styles.css:107).
- Rules: P21, B2, B3. A13 holds: hover and press still thicken the line, 2 then 3 px.
- Test first (selfcheck static): no `text-decoration-color: var(--wine)` in frontend/styles.
- Height: 0. Risk: low.

**C6. One tracking for the main button (pane, 1 line).**
- Pane: drop `letter-spacing: .02em` from `.primary` (global.css:129). The `letter-spacing: 0` at :139 then becomes
  redundant.
- Site: already `normal`.
- Rules: P21, T7.
- Test first (selfcheck static): no `letter-spacing` in pane CSS other than `var(--track)` (the limits heads).
- Height: 0 (the label is about 5 px narrower). Risk: low. The e2e "darker wine" check reads colour only.

## D. Rejected ideas

- Section padding 64-96 px as the references use: T18 and P9 (12 px left at 390).
- Heading leading .95 → 1.05: T18 (about +22 px at 390) and T12.
- Light display weights (Stripe and IBM at 300, Vercel and Linear at 600): P11, P29, B25.
- Negative display tracking (Stripe, Linear, Vercel, Apple): T7, X16.
- Pill buttons, the "double-bezel" frame, a button inside a button, squircles (high-end-visual-design): T5, X13, X66.
- Eyebrow tags above headings: T15, X21, X39.
- Blur-in or spring scroll entries, a 16 px heavy fade-up: M1, M3, X57.
- A floating glass nav, backdrop blur: X58, X68.
- Gradient-mesh or ambient-blob backgrounds (Stripe, Vercel, minimalist-ui): B9, X25, X64, M5.
- Bento or asymmetric card grids (high-end-visual-design, design-taste): X62.
- Stacked soft shadows on cards (Vercel, Notion): X68, T21.
- Moving off "cream + oxblood" (design-taste's premium-palette ban lists `#f7f5f1` and `#9a2436`): P15, P30, B1. The
  brand owner named these colours.
- A serif display face (Claude.com) or mono eyebrows (Vercel): B15, X15, B14, X23.
- Pane list rows padded 10 → 12 px and 6 → 8 px: measured that it re-wraps the reasons (`r2/r2a360-2-results.png`).
  It gains no air and shows fewer words.
- Pane card at 3 sizes (reasons 13 → 14 px): the first screen grows (aee04f4: 644 px must not grow).
- FAQ accordion turned into a side-by-side list (redesign-existing-projects): S18 (word-for-word FAQPage) and T18.
- Apple's single product shadow on the pane picture: X68.
- Snapping every site padding onto a 4 px grid (9 → 8, 10/14 → 12/16): no visible gain per line, and it moves the
  sample's measured geometry (S7, M19).
