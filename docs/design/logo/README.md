# The Arcas mark: an A of tiles in a gold ring (AH-203)

A capital A made of tiles, like the cells of a sheet: six rows of slanted tiles, wine at the top stepping to navy at the
bottom, dead centre in a paper coin ringed in gold. The coin is the header bar's own paper, `--paper` at its heart to
a warm sand at its rim (John: "add some gradient inside the ring"), with the bar's grain over it, so on the site it blends into the page and the gold ring is its
only edge. On the pane's navy band the same coin carries the A's true colours with no box round it.

How John got here (2026-11-19): he retired the Spear and Banner for a fresh mark from his emblem's shapes, picked a
Nano Banana idea (Gemini's image model) of an A of tiles shading by rows ("wine red at the top, fading into navy"), had
it polished ("keep that intact ... elevate it to great"), then took its gold tile out for a gold circle round the A
("not just a static circle"), its inside "a little darker", textured "similar to our website ... subtle", the A "dead
center" and "not touching the ring", the grain and the white matching "the hero line".

Proof: seven blind judges, labels shuffled, each mark shown in the website header, the phone header, the pane's band, a
tab, Excel's ribbon light and dark, and the download section. The A of tiles scored 126 to 153 of 210 against the
Spear and Banner's 83 to 91; one judge in two preferred a flat navy block A. On the pane's navy band, four ways to show
it were judged: the night steps without a box 70 of 90, the paper square 53 ("no white box", John), and John chose the
coin, which shows the true colours with no box at all.

How it is drawn (`draw.py` writes every file here; `python docs/design/logo/draw.py`):
- The A's rows and gaps are whole pixels at the size each drawing is shown; 6% taller than wide; the top row 46% of the
  base; every slanted edge points at one vanishing point. The middle steps hold their colour (a straight mix sagged to
  grey).
- Dead centre: the coin's size and the A's height are both odd or both even, so the A's box sits exactly in the middle
  on whole pixels; `draw.py` refuses a drawing whose A comes within 12% of the ring's inner radius.
- The grain is the site's own (`styles.css --grain`, `frontend/assets/grain.svg`): fractal noise .8, 3 octaves, seed 3,
  the same colour, 7%, one unit a pixel. The icons carry none: unseen at their size, and noise made a 512 px PNG 324 KB.
- The ring draws itself once (site header, pane header): two half discs in its mask turn into place, transform only,
  the first easing in and the second out (no stop at 6); each half's clip stops half a pixel short of the middle (its
  smoothed edge showed a tick at 6 before the sweep), and a whole ring over it shows once the sweep ends (the halves'
  meeting left a hairline at 12 and 6). At rest, under reduced motion or with no CSS the ring is simply whole.

| Drawing | Size | A rows | Used for |
|---|---|---|---|
| `coin-157.svg` | 157 | 12, 3 apart | the download's logo (inline in `site/index.html`), the README |
| `coin-41.svg` | 41 | 3, 1 apart | every site page's header (inline; lean: no part names, edges to 0.1 px, its ring drawn once) |
| `coin-31.svg` | 31 | 2, 1 apart | `frontend/assets/crest4-coin.svg`: the pane's header (inline, its ring drawn once), footer, Check as you work's note, its privacy and support pages |
| `icon-16.svg` | 16 | placed pixel by pixel | `crest4-16.png`: favicon, ribbon 16, the exe's 16 |
| `icon-32.svg` ... `icon-512.svg` | their size | whole pixels there | `crest4-32.png`, `-64`, `-80` (ribbon, manifest, favicons), the site's 180 (on paper: an iPhone shows no transparency), 192 and 512, the exe's 48 and 256 |

- Render each `icon-*.svg` with Chromium at 1x at its own size, the large ones (64 up) saved as 256-colour PNGs:
  `icon-16`, `-32`, `-64`, `-80` to `frontend/assets/crest4-*.png`; copy `crest4-32.png` and `crest4-64.png` to
  `site/assets/`; `icon-180`, `-192`, `-512` to `site/assets/crest4-*.png`. Copy `coin-31.svg` to
  `frontend/assets/crest4-coin.svg` and into `frontend/taskpane.html`'s header.
- `packaging/AnomalyHunter.ico` holds PNG entries 16, 32, 48, 64 and 256, each its own `icon-*.svg`.
- `site/assets/og-card.png` (1200 x 630): the left panel, paper-2 #EFECE4 from x 0 to 424, holds a 300 px coin (rows of
  20, 6 apart, no grain) at (62, 165); saved as a 256-colour PNG (octree, no dither: 22 KB).
- `site/assets/pane-after-scan.webp`: its top 60 rows are the pane's header rendered at 360 px, 1x, with this mark.
- Tests: `tools/test_site.mjs` reads every page's logos against these files, each drawing's rows on whole pixels at the
  height `styles.css` shows it, and in the browser the download coin's 14 tiles wine to navy, its gold ring, the A dead
  centre (within half a pixel) and clear of the ring. `frontend/selfcheck.js` reads the 16 and 32 px icons (round, no gold
  inside the ring, the true wine and navy; the 16 every pixel the coin's own colours and every row a mirror image) and
  holds the pane's navy bands to the coin: no paper icon there, and the coin's tiles in their true steps.
- Office caches ribbon icons per URL: new art gets new file names and a `<Version>` bump in `frontend/manifest.xml`
  (`crest4-*.png` and 1.0.9.0), and every older name still answers with today's mark (`server.OLD_ICONS`).

Palette: the rows #6B1E2E (wine), #5B1E30, #4B1C35, #371C3A, #211B3C, #0C1938 (navy); the ring #997D3A (gold); the
coin #F7F5F0 (the header bar's paper) at its heart to a warm sand #E3DBCA at its rim, with the site's grain.
