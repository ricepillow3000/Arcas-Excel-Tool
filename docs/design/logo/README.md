# The Arcas mark: an A of tiles (AH-203)

A capital A made of tiles, like the cells of a sheet: six rows of slanted tiles, wine at the top stepping to navy at the
bottom, and one gold tile in the A's opening, the one cell Arcas finds. Flat, like the page it sits on: solid fills in
the site's own colours, square corners, no shading, no outline.

Why (John, 2026-11-19): "redesign our logo ... make it so it matches the textures, design, and feel of our website and
tool". The Spear and Banner went through two rounds (crest3, never shipped) before John asked for a fresh mark built
from his emblem's shapes, then for "a letter A in caps ... made of square blocks ... kind of gradient", and picked a
Nano Banana idea (Gemini's image model) of a tiled A shading by rows: "wine red at the top, fading into navy, with
accents of gold in the middle". Its tiles lean like his emblem's two slabs, the A is his triangle, and the gold cell is
the product: every cell read, the wrong one found.

How it was judged (blind, labels shuffled, each mark shown in the website header, the phone header, the pane's navy
band, a browser tab, Excel's ribbon light and dark, and the download section):
- Round 6, five marks: this A 153 of 210, a flat navy block A 155, a solid A with a dot 147, today's crest2 91. It led
  on eye-catching, memorable, fit with the site and the seven feel measures; its points were lost on craft (16 px,
  the pane, soft rows), which the polish below fixed.
- Round 7, after the polish: this A 131 (126 before it), the flat navy block A 163, crest2 83. One judge in two
  preferred the flat block A; John chose this one.

The polish (round 6's list, no element changed): every row on whole pixels at the size it is shown; 6% taller than
wide and the top row 46% of the base (a square footprint read as a pyramid); the middle steps' colour held up (a
straight mix sagged to grey); a 16 px icon of its own, the crossbar joining both legs and the gold one 2 x 2 cell (with
gaps it read as an arch with a lantern).

On navy (the pane's header and footer, its privacy and support pages) there is no box round the mark (John: "no white
box ... visible at 100%"). The true wine and navy are about 1:1 there, so `band-29.svg` draws its night steps: the same
wine and navy lifted only to 3:1 on navy, WCAG's floor for a graphic, its base a slate navy, the cell the true gold. A
first try in pale tints (rose to cream, gold-hi, 4.5:1 and up) read "way too bright" and its gold "not gold"; the
mark on its paper square read as a white box. A blind judge of the four in the pane's header: night steps 70 of 90,
brighter night steps 60 and 58, the paper square 53. `frontend/selfcheck.js` holds every night fill between 3 and
3.6:1 (the gold up to 4.5) and no paper icon on the pane's navy bands.

| Drawing | Shown at | Rows | Used for |
|---|---|---|---|
| `mark-157.svg` | 157 px tall | 22, 5 apart | the download's logo (inline in `site/index.html`), the README |
| `mark-29.svg` | 29 px tall | 4, 1 apart | the header of every site page (inline), 1.8 times the 16 px capitals beside it |
| `mark-23.svg` | 23 px tall | 3, 1 apart | `frontend/assets/crest4-mark.svg`: the pane on paper (Check as you work's note) |
| `band-29.svg` | 29 px tall | 4, 1 apart | `frontend/assets/crest4-band.svg`: the pane's navy bands, its night steps, no box |
| `icon-16.svg`, `icon-32.svg` | 16, 32 px | placed pixel by pixel | `crest4-16.png`, `crest4-32.png`: ribbon, favicon, the exe's 16 and 32 |
| `icon-48.svg` ... `icon-512.svg` | their size | whole pixels there | `crest4-64.png` (manifest, favicon), `crest4-80.png` (ribbon), the site's 180, 192 and 512, the exe's 48 and 256 |

The icons are the mark on a paper square: on a dark ribbon or tab, wine and navy would vanish on their own.

- `python docs/design/logo/draw.py` writes every drawing here. Render each with Chromium at 1x at its own size:
  `icon-16.svg` to `frontend/assets/crest4-16.png`, `icon-32.svg` to `crest4-32.png`, `icon-64.svg` to `crest4-64.png`,
  `icon-80.svg` to `crest4-80.png`; copy `crest4-32.png` and `crest4-64.png` to `site/assets/`, and render `icon-180`,
  `icon-192` and `icon-512` to `site/assets/crest4-180.png`, `-192.png`, `-512.png`. Copy `mark-23.svg` and `band-29.svg`
  to `frontend/assets/crest4-mark.svg` and `crest4-band.svg`.
- `packaging/AnomalyHunter.ico` holds PNG entries 16, 32, 48, 64 and 256, each its own `icon-*.svg`.
- `site/assets/og-card.png` (1200 x 630): the left panel, paper-2 #EFECE4 from x 0 to 424, holds the mark at rows of 44
  px, 10 apart (314 px tall), centred; the rest unchanged; saved as a 256-colour PNG.
- `site/assets/pane-after-scan.webp`: its top 60 rows are the pane's header rendered at 360 px, 1x, with this mark.
- The site's inline copies are these files as they are (`tools/test_site.mjs` checks every page, and that each
  drawing's rows are whole pixels at the height `styles.css` shows it). Each tile is `data-part="tile"` with its
  `data-row`, the gold one `data-part="cell"`: the browser check reads one colour a row, wine to navy, and the gold cell
  between its row's two tiles, above the crossbar. `frontend/selfcheck.js` reads the 16 and 32 px PNGs pixel by pixel:
  only the palette, every row a mirror image, a paper edge, the gold one 2 x 2 or 6 x 4 cell.
- Office caches ribbon icons per URL: new art gets new file names and a `<Version>` bump in `frontend/manifest.xml`
  (`crest4-*.png` and 1.0.9.0 for this one), and every older name still answers with today's mark (`server.OLD_ICONS`).

Palette: the rows #6B1E2E (wine), #5B1E30, #4B1C35, #371C3A, #211B3C, #0C1938 (navy); the cell #997D3A (gold) on paper
#F7F5F0. Night steps on navy: #B03D54, #9F4B66, #8C5477, #795B87, #5A6398, #52659A, the cell #997D3A.
