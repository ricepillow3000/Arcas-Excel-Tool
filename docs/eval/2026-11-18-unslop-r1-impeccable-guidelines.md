# AH-193 R1: impeccable + web-design-guidelines on the pane and the site (read-only)

Researcher 1, 2026-11-17. Repo `/home/user/excel-anomaly-hunter` at `12c7f52` (main, v0.1.431). Nothing in the repo was
edited. All paths below are under `ah193/`.

## A. What I ran or read, and what I could not run

Read first, whole: `second-brain-vault/90-System/Design-Rulebook.md` (969 lines), repo `CLAUDE.md` L11 and L12,
`docs/design/motion.md` (594 lines).

- **impeccable**, loaded with the Skill tool (repo copy). Read: repo `.claude/skills/impeccable/SKILL.md`,
  `reference/craft-floor.md` (same bytes as the vault copy), `audit.md`, `polish.md`, `operate.md`; vault copy's
  `reference/critique.md`, `mode-persuade.md`, `craft.md`; `site/.impeccable/config.json` (no ignores).
- **impeccable detector: could not run.** The repo copy has no `scripts/` (stripped on install, says SKILL.md). The vault
  copy has `scripts/impeccable` (v0.1.11), a launcher only: its `bin/<os>-<arch>/` binary is missing and it would
  download one, so I did not run it. Audit dimension 5 and the critique's Assessment B were done by hand.
- **impeccable critique: degraded.** `critique.md` wants two isolated sub-agents; I have no sub-agent tool, so A (design
  review) and B (browser evidence) ran in one context, A first. Scores below carry that caveat.
- **web-design-guidelines**: read the vault `SKILL.md`; the live rules fetch **worked** (HTTP 200, 191 lines, saved as
  `dl/wig.md`). Reviewed `site/*.html`, `site/styles.css`, `frontend/taskpane.html`, `frontend/styles/*.css`,
  `frontend/components/progress.js` against them (forms, focus, motion, typography, touch, theming).
- **Before screenshots** (all deviceScaleFactor 2, reduced motion so every block is at rest), in `before/`:
  site 1280 x 800 `site-1280-{hero,sample,checks,maker,proof,download,faq,checkspage,supportpage}.png`, site 390 x 844
  `site-390-{hero,sample}.png`, pane 360 x 900 `before193-{1-start,2-results,3-card,4-checkwords}.png` (shots.mjs:
  optionsAt 551, page 1071, resultsListAt 523, cardOptionsAt 644, oddList 67). Home heights 4,651 (1280) and 8,385
  (390), no sideways scroll, no console errors.
- **Measurements and CSS trials** (CSS injected in Playwright with `bypassCSP`, never written to the repo): scripts and
  pictures in `r1/` (`measure.mjs`, `trial.mjs`, `trial2.mjs`, `r1/site-1280-band-edge.png`,
  `r1/trial-1280-band-edge.png`, `r1/trial-1280-checkspage.png`, `r1/site-1280-checkspage-full.png`).

Scores (honest, degraded run): impeccable audit 16/20 (A11y 3, Perf 3, Theming 3, Responsive 4, Integrity 3: "Good");
Nielsen critique 31/40 (status 4, real world 3, control 4, consistency 3, prevention 3, recognition 3, flexibility 2,
aesthetic 3, recovery 3, help 3). Design specificity: authored, not interchangeable (the engine's own sample, the crest,
the ledger); the cheap tells are small edge defects, listed below.

## B. Findings

| # | Surface | Element, file:line | Sev | Rule / why it reads cheap | Evidence |
|---|---|---|---|---|---|
| F1 | site | `#maker .calm::before` (`site/styles.css:147-150`) reaches 96 px up over the navy band's last 47 px | P1 | A grey-blue fog with rounded corners across the band's foot: reads as a rendering smudge or a glow. B9 (no gradient as a coloured background), X58 (glow), T21 (hairlines between blocks), M17 (the paper fades only under prose) | maker's calm top 1987 - 96 = 1891 < band bottom 1938 (`measure.mjs`); `r1/site-1280-band-edge.png` vs fixed `r1/trial-1280-band-edge.png` |
| F2 | site | hero buttons, `site/styles.css:249` `.hero-cta` flex-wrap | P2 | At 1280 and 1440 "Contact John" wraps alone under the other two: an orphan that reads unplanned; on a phone it is already primary alone, two below. P32, P28 | cta boxes 1280: (755,246) (978,246) (755,310); 1440 same shape; `before/site-1280-hero.png` |
| F3 | site | no `::selection` anywhere in `site/styles.css` | P2 | Craft floor "Browser surfaces": selecting text shows the browser's blue, the one colour outside B1 | grep: none (pane has one, `frontend/styles/global.css:67`) |
| F4 | pane | `::selection` sets a background only (`global.css:67`) | P3 | Cream text on the navy header and footer bands, selected, is cream on a light gold tint (about 1.1:1). A1 | `global.css:67`, header `global.css:81`, footer `:177` |
| F5 | pane | `#busy-bar` animates `width` on `ease-out` (`frontend/styles/components.css:69`, `components/progress.js:17`) | P2 | M1 (transform and opacity only), M2 (the pane's one `--ease`), impeccable audit "layout-property animation"; the site's Scanning bar already fills by `scaleX` (M24) | file lines above |
| F6 | pane | `.primary, .secondary` hover is a `background-color, color, border-color` transition (`global.css:122-123`); also `.sev` colour (`components.css:156`), footer links (`global.css:184`) | P2 | M1, M44 ("masks for reveals and colour changes"), P21: the site draws a button's hover across by a `scaleX` layer (`site/styles.css:207-216`); the pane crossfades colours, so the two surfaces' main buttons feel different under the pointer | file lines above |
| F7 | pane | "Before you scan" first line breaks as "This sheet looks like a / time series by OrderDate." | P3 | `#empty-state p:first-child` (`components.css:94`) also matches the first `<p>` inside `#before-scan-lines`; `font: inherit` undoes its font but not its `text-wrap: balance`, so a sentence is balanced like a heading. T13 (balance on headings only) | `before/before193-1-start.png` |
| F8 | site | `checks.html` first screen holds no check | P2 | The navy band opens on a staircase: lede alone in row 1 (right), fact alone in row 2 (left), so 1280 x 800 shows heading, lede and an empty navy field; X33 (empty first screen), X42 (hollow state), P9 | `#every-check` table top 846 at 1280 x 800, 856 at 1440 x 900 (`measure.mjs`); `before/site-1280-checkspage.png` |
| F9 | site | phone hero says Windows three times: notice bar, `.phone-only`, and `.note` "Free for Windows with desktop Excel." (`site/index.html:53`) | P3 | X12 (verbose, redundant); the home page has 12 px left under the 8,397 px phone cap (T18) | `before/site-390-hero.png`; 8,385 px |
| F10 | pane | the flagged list is a 320 px scroll box inside a scrolling pane (`components.css:130`), cut mid-row at 360 x 900 | P3 | WIG: `overscroll-behavior: contain` in scroll boxes is missing, so the wheel at its end scrolls the pane; the cut row reads clipped | `before/before193-2-results.png` |
| F11 | site | install steps "01 02 03 04" at `--fs-5` in wine (`site/styles.css:520`, `decimal-leading-zero`) | P3 | Craft floor names zero-padded section numbers as a template tell; here it is a real sequence (X40 allows it) and four big wine figures sit beside the wine Download (B2). Not proposed: John's look | `before/site-1280-download.png` |
| F12 | site | no `<meta name="theme-color">` on any page | P3 | WIG theming: a phone's browser bar stays grey over the navy notice bar | grep: none |
| F13 | site | support form placeholder "When I clicked Find problems in this sheet, ..." (`site/support.html:124`) | P3 | WIG typography: "…" not "...". Also no `autocomplete="off"` on the non-auth fields (`support.html:115,119`) | file lines |

Held up well (keep): focus rings on every control (8 `:focus-visible` rules on the site, `global.css:74` in the pane),
44 px targets, no `transition: all`, no zoom lock (viewport `width=device-width, initial-scale=1, viewport-fit=cover`),
tabular numbers, skip link, labelled form fields with `autocomplete="name"`, reduced motion everywhere, CLS 0, the
sample is the engine's own answer. Web guidelines I set aside on purpose: "Title Case for headings/buttons" (W5 wins),
"URL reflects state" for the sample's tabs (no rule asks it; adds code), "virtualize lists over 50" (pane list is
capped by the engine's output, no measured slowness).

## C. Proposed changes (ranked by impact per line of code)

**C1. The navy band ends on a clean edge (F1).** Site: `site/styles.css` after line 234,
`.band-dark + .section { overflow: clip; }` (only `#maker` follows a band, on `index.html`). Pane: nothing to do; its
bands have no fading paper layer. Rules: B9, X58, T21, M17 (the paper still fades on the paper side). Test first,
`tools/test_site.mjs --browser`: at 1280 x 800 and 390 x 844, one pixel 12 px above `#checks`'s bottom, mid-width, is
`--dark` #0C1938 within 8 per channel (red now: fogged). Height 0. Risk: low; `#maker`'s reveal rise (24 px) and focus
outlines stay inside it. Trial: `r1/trial-1280-band-edge.png`, heights unchanged.

**C2. One main button, then the two quieter ones side by side (F2).** Site: `site/styles.css` near 249,
`@media (min-width: 761px) { .hero-cta { display: grid; grid-template-columns: repeat(2, max-content); justify-content: start; } .hero-cta .btn-primary { grid-column: 1 / -1; justify-self: start; } }`.
The phone keeps its flex (a grid at 320 px scrolled sideways in my trial; a flex `::after` break added 16 px and took the
phone to 8,401, over the cap, so both were dropped). Pane: already this shape (Find problems alone, secondaries below);
no change. Rules: P32, P28, S24 and R6 (Contact John stays a button), T18, T20, M13 (entrance order is DOM order,
unchanged). Test first (`test_site.mjs --browser`, 1280 x 800, 1280 x 720, 1440 x 900): Download's top is above both
others, the two secondaries share one top, no sideways scroll at 761 and 1024. Height 0 measured (4,651 and 4,828 before
and after; Download still at 246 / 316, so the 1280 x 720 first-screen test holds). Risk: the regex tests at
`test_site.mjs:122,395` read HTML, untouched.

**C3. Text selection in the house colours, on both surfaces (F3, F4).** Site: add to `site/styles.css` (base rules) and
pane: replace `frontend/styles/global.css:67` with the same line,
`::selection { background: color-mix(in oklch, var(--gold) 25%, var(--paper)); color: <navy token>; }` (site `--ink`,
pane `--navy`), with the hex fallback under `@supports not (color: color-mix(...))` as B4 asks. Rules: B1, B3 (gold as a
tint, never small gold text), B4, A1, craft floor "Browser surfaces". Test first: site in `test_site.mjs --browser`, pane
in `e2e/contrast.mjs`: `getComputedStyle(el, "::selection")` on a paper text and on a navy-band text (site `#checks p`,
pane `header h1`) clears 4.5:1 (red now: site has no rule, pane header about 1.1:1). Height 0. Risk: none known.

**C4. The pane's progress bar fills by `scaleX`, as the site's Scanning bar does (F5).** Pane:
`frontend/styles/components.css:69` becomes `#busy-bar { height: 100%; width: 100%; transform: scaleX(var(--p, 0)); transform-origin: 0 50%; background: var(--wine); transition: transform .2s var(--ease); }`,
`.unknown` adds `transform: none` (its `slide` keyframes keep moving it), and `components/progress.js:17` sets
`style.setProperty("--p", pct)` instead of `style.width` (CSSOM, allowed by the pane's CSP, as today). Site: none needed
(M24 already `scaleX`). Rules: M1, M2, M50, N3. Test first: `frontend/selfcheck.js` refuses `width` in any pane
`transition`; `e2e/run.mjs` reads `#busy-bar`'s transform as a scale between 0 and 1 while a scan reads (the existing
sliver check at `e2e/run.mjs:223` still reads the iteration count). Height 0. Risk: low.

**C5. The pane's button hover is drawn across like the site's (F6).** Pane, `frontend/styles/global.css:122-145`:
inside `@media (prefers-reduced-motion: no-preference) and (forced-colors: none)` give `.primary, .secondary` a
`::before` layer (`inset: 0; transform: scaleX(0); transform-origin: 0 50%; transition: transform 280ms var(--ease)`,
`:hover::before { transform: scaleX(1) }` over 350 ms), `--wine-deep` under the label for `.primary` (B6: never navy),
and for `.secondary` the site's difference fill (`#EBDCB8`, `mix-blend-mode: difference`, `site/styles.css:214`) so the
label reads at every frame; drop the colour transitions on lines 123, 156 and 184 (instant swap stays for reduced
motion, as on the site). About 8 lines. Site: none (it is the source). Rules: M1, M44, M33, B6, P21, N1. Test first:
`selfcheck.js` refuses `background-color`, `color` or `border-color` in a pane transition; `e2e/run.mjs:234-241`
(AH-166) then reads the hovered layer's colour (`::before`) instead of the button's own background, still "a darker
wine, never navy". Height 0. Risk: medium; that e2e assertion must be rewritten to read the layer (a change of what it
reads, not a looser gate), and the `.flagged-list button::before` rule (`components.css:141`) must not be matched.

**C6. A sentence in "Before you scan" is never balanced like a heading (F7).** Pane:
`frontend/styles/components.css:94` `#empty-state p:first-child` becomes `#empty-state > p:first-child`. Site: no
equivalent (grep found no leaking `:first-child` on the site's prose). Rules: T13, N9 (its held height is unchanged).
Test first, `e2e/run.mjs` "Before you scan" block: the first line's computed `text-wrap-style` is not `balance` (red now).
Height 0. Risk: none; the empty state's own first paragraph keeps its look.

**C7. checks.html shows a check on its first screen (F8).** Site: `site/styles.css` (page-scoped),
`#every-check { padding-top: var(--s5); } #every-check .fact { grid-row: 1; }`: fact and lede share one row, as the
home page's band does. Pane: no equivalent page. Rules: X33, X42, P9, P4, T19 (home order untouched). Test first,
`test_site.mjs --browser`: at 1440 x 900 the table's first row ends inside the screen; at 1280 x 800 its head starts
above 760 px. Measured trial: table top 846 to 734 (1280), first row bottom 975 to 863 at 1440 x 900 (inside 900);
page 1,978 to 1,866 px. Height -112 px. Risk: low; the rows' reveal test scrolls to `#every-check` first
(`test_site.mjs:2045`), and the lift heading is the page head, untouched. `r1/trial-1280-checkspage.png`.

**C8. The phone hero says Windows twice, not three times (F9).** Site: `site/styles.css` in the 760 px block,
`.hero .note { display: none; }` (the phone line already says Arcas runs on a Windows computer; "desktop Excel" is in the
download section and the FAQ). Pane: n/a. Rules: X12, P9, T18 (buys headroom under 8,397). Test first,
`test_site.mjs --browser` at 390 x 844: `.hero .note` is not rendered and the home page is 8,345 px or less. Measured:
8,385 to 8,340 (390), 9,119 to 9,010 (320). Risk: the static test at `test_site.mjs:524` reads the note's HTML (kept);
the 1280 x 720 test at `:3109` reads it at desktop (still shown).

Not in the top 8 but cheap, for a later pass: F10 `overscroll-behavior: contain` on `.flagged-list` (pane, 1 line);
F12 `<meta name="theme-color" content="#0C1938">` on every site page; F13 "…" in the support placeholder.

Seven measures (P20), in one line each: easier (C2: the one thing to do is alone on its row); fun (C5: the pane's
buttons answer the pointer like the site's); simple (C7, C8: fewer words before the content); convenient (C3: copying a
value keeps it readable; C1/C6 fix what looked broken); not boring (C7: a check, not a navy void); interesting (C7: the
real checks table in the first screen); intriguing (C2: "See a sample scan" sits beside "Contact John", one tap each).

## D. Rejected ideas

- Centre the pane's button labels like the site's: the pane's buttons are full width and flush-left on the 4-column
  grid (T4, Swiss); the site's are content-width, so there is no real mismatch (P28).
- Drop "Contact John" or make it a text link to fix F2: R6, S24.
- Change the 01-04 steps to plain or navy numbers (F11): John's look, a real sequence (X40 allows it); ask John first (R13).
- End the pane's "5 of 300 rows look wrong." without a period, or make it a heading: it is a sentence in a `<p>`, and the
  site's pane picture (S20) shows it as is.
- Remove the flagged list's 320 px box: the Options band would drop below every row of a big scan; pane first-screen
  heights must not grow (rulebook step 8).
- A gradient or shadow to hint the list scrolls: B9, X68.
- Fade the band's edge instead of clipping it: B9, X58.
- A flex `::after` line break for C2: +16 px, takes the phone to 8,401 (T18 cap 8,397).
- A CSS grid for C2 at every width: sideways scroll at 320 px (T17).
- Title Case on buttons and headings (the web guidelines' Content rule): W5, X5.
- Sync the sample's tab or filter to the URL (guidelines' Navigation rule): not asked, adds code (rule 2).
- Run the impeccable binary by downloading it: untrusted download; the repo's install removed it on purpose.
