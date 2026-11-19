# The Spear and Banner mark

Flat, like the page it sits on: solid fills in the site's own colors, square ends, no shading and no outline.
The spear, the bar and the banner are John's; the emblem is his sketch (two panels touching at their inner top corners,
a slashed ring above).

Why (AH-103): the header showed a blocky pixel-grid redraw and the large logo had dark brown outlines, rounded ends and
a lit and a shaded face of gold, so the mark looked out of place on a flat, square-cornered, hairline page. John kept
the design and changed only its texture ("B: flat + thin lines").

Why one drawing per size (AH-121): at 1x a single drawing put edges between pixels, the 16 px icon was a smudge and the
32 px mush. Each drawing is made for the pixels it lands on: every straight edge on a whole pixel at its size, and the 16
and 32 px icons placed pixel by pixel (`shape-rendering="crispEdges"`, whole-pixel rects, every pixel gold, navy, paper
or empty).

## AH-203: the hairline mark

John (2026-11-19): "redesign our logo, keeping the banner symbol and banner, make it so it matches the textures, design,
and feel of our website and tool." Three directions were drawn; a blind judge chose "Hairline" (58 of 80, ahead of a
plain lance at 57, a 4-unit grid at 56 and AH-121's mark at 33), for its fit with the site's hairlines and square corners
and for looking the most premium, with one fix: its 2-unit pole and bar nearly vanished at 32 px on the pane's navy band.

What changed:
- Gone, since neither the site nor the pane has any of it: the curled wings, the banded collar and end caps, the X
  lashing, the curved drape and its folds, the midrib.
- The blade is a plain leaf of straight edges (T5's square corners), 8 units at its widest on the 80 grid.
- The pole and the bar are 4 units each (the judge's fix: twice the concept's 2), the bar a plain rule with square ends.
- The banner hangs straight from the bar. Its rim is a one-unit gold line set 2 units in from its edge, following the V
  hem: the site's hairline box and the pane's navy band with its gold line. On the navy band the banner's edge melts into
  the band and this line draws its shape (B21).
- The emblem is John's, at its size, in the room the drape left.

Fix round 1 (a second blind judge preferred this mark to AH-121's 57 to 40, and named its defects):
- The blade read as a match head or a pin at 40 px (a slanted edge blurs at 1x) and as a "+" cross at 16. At 40 and 32
  it is now whole-pixel rows, 2, 4, 6 and 4 px wide, two rows each (uneven steps read as a tiered tower, a single wider
  row as arms); at 16 a 2 px post with no arms; at 64 a flat 2 px tip and a 4 px base on whole pixels with straight
  sides (1 px steps read as a tower at 2x).
- The pole is about 25% shorter at every size (14 units on the 80, was 18), so the banner is over 45% of the mark's
  height.
- The bar passes the banner by about 8% of its width each side (4 units on the 80, 3 px on the 64, 2 on the 40 and the
  32, 1 on the 16; it was 8 on the 80, a quarter of the banner, and read as a sword's crossguard). Its weight stays 4
  units, the pole's: an earlier judge needed it heavy enough to show at 32 px on navy, and one weight for pole and bar
  is plainer than a 3 beside a 4.
- At 32 one gold edge, the rim on the banner's outside (a navy edge outside the gold line read as a double edge on
  paper), and the ring redrawn: 2 px around a 4 px hole, its 1 px slash 2 px past the ring at each end.
- At 64 the bar, banner, gold line and the hem's point are whole pixels (`crispEdges`), so the point is sharp.
- No lighter navy or cream outer edge for dark backgrounds (B1, R31; B21: the gold carries it on navy), no notch.

| Drawing | Grid | Used for | What it keeps |
|---|---|---|---|
| `mark-80.svg` | 80, 1 unit = 1 px | the download's logo (160 px, 2 px a unit), `crest3-80.png` (ribbon 80), the exe's 256, the site's 192 and 512 icons, the 180 on paper, the sharing card (at 320) | everything: a leaf blade from a point at y 7 to 8 wide at y 19 and 4 at y 25, the pole 38 to 42 down to y 39, the bar 16 to 64 from y 39 to 43, the banner 20 to 60 from y 43 with its hem at 70 and its point at 74, the gold line 2 units in, the emblem (panels 60 to 66, the ring at y 55) |
| `mark-64.svg` | 64 | `crest3-64.png`: the pane's logo at 2x, the manifest's high resolution icon, the 64 px favicon, the exe's 64 | its own grid (never 80 scaled by .8): the bar, banner, gold line and hem whole pixels; the blade a flat 2 px tip to 8 px to a 4 px base on whole pixels; pole and bar 4 px (2 CSS px on the pane's navy band at 2x), the bar 3 px past the banner; the gold line 1 px set 2 px in; AH-121's 64 px emblem, drawn smooth |
| `mark-40.svg` | 32 x 40, 1 unit = 1 CSS px | the site header (inline, 40 px tall, `aspect-ratio: 32 / 40`), the exe's 48 (drawn 1:1, centred) | the blade whole-pixel rows (2, 4, 6, 4 px, two rows each), the pole 2 by 3, the bar 3 and 2 px past the banner, the banner 24 by 24, the gold line 1 px set 1 px in, the ring's stroke 1.5 px; sharp at 1x, smooth at 2x and 3x |
| `mark-32.svg` | 32 | `crest3-32.png`: favicon, ribbon 32, the pane's logo at 1x, the exe's 32 | placed pixel by pixel: the 40's stepped blade, a 6 px pole, the bar 2 px solid and 2 px past the banner, one gold rim on the banner's outside with its hem a V of 3, 3, 2 and 2 px steps, and the emblem as the ring alone: 2 px around a 4 px hole, a 1 px slash 2 px past it at each end (the panels were a smear at this size) |
| `mark-16.svg` | 16 | `crest3-16.png`: favicon, ribbon 16, the exe's 16 | placed pixel by pixel, centred between columns 7 and 8: a 2 px post with no arms, the bar 1 px past the banner, the banner with its gold rim on the edge, the bar standing for its top, and AH-121's 1 px ring with a 1 px slash poking past it |

- Render with Chromium at 1x on a transparent background, each file at its own size (the 16 and 32 px PNGs must hold only
  the three palette colours and fully transparent pixels): `mark-16.svg` at 16 to `frontend/assets/crest3-16.png`,
  `mark-32.svg` at 32 to `crest3-32.png`, `mark-64.svg` at 64 to `crest3-64.png`, `mark-80.svg` at 80 to
  `crest3-80.png`; copy `crest3-32.png` and `crest3-64.png` to `site/assets/` for the favicons. `site/assets/crest3-192.png`
  and `crest3-512.png` are `mark-80.svg` at 192 and 512 on transparent; `crest3-180.png` (the iPhone's home screen, which
  shows no transparency) is `mark-80.svg` at 152 in the middle of a 180 square of paper #F7F5F0.
- `packaging/AnomalyHunter.ico` holds PNG entries, each from its own drawing: 16, 32, 48 (`mark-40.svg` at 32 x 40 in the
  middle of a 48 square), 64 and 256 (`mark-80.svg` at 256).
- `site/assets/og-card.png` (1200 x 630): the left panel, paper-2 #EFECE4 from x 0 to 424, with `mark-80.svg` at 320 px
  whose top left corner is at (52, 156); the rest of the card unchanged; saved as a 256-colour PNG (`+dither -colors 256`).
- The site's inline copies are these files without comments: `mark-40.svg` in the header of every page, `mark-80.svg`
  above the Download button; `tools/test_site.mjs` checks every page holds them as they are here, and that the header's
  blade is whole-pixel rects. Their `data-part` groups (spear, bar, banner, emblem) are what its browser check reads: the
  spear and bar fill gold, the banner navy with its gold line a stroke, the emblem paper; the spear stands on the bar
  over the banner's middle, the bar sits on the banner and passes it by at most a tenth of its width each side, the
  banner is at least 45% of the mark's height, and the emblem lies inside the gold line. `frontend/selfcheck.js` reads
  the 16 and 32 px PNGs pixel by pixel: only the palette, no navy meeting the outside, a 16 px spear no wider than 2 px,
  and a pointed 32 px blade.
- Office caches ribbon icons per URL: new art gets new file names and a `<Version>` bump in `frontend/manifest.xml`
  (`crest3-*.png` and 1.0.9.0 for this one), and every older name still answers with today's crest (`server.OLD_ICONS`).

Palette (the tokens in `site/styles.css`): gold #997D3A for the spear, pole, bar and the banner's line or rim; navy
#0C1938 for the banner; paper #F7F5F0 for the emblem.

Honest weaknesses: at 16 and 32 px the gold line is the banner's edge, not set in, so on the pane's navy band at 1x
the banner is a gold outline; at 16 the spear is a plain post, with no point; the 40's and 32's stepped blade shows its
steps at 2x and 3x; the 64's blade sides and the 80's tip are slanted, so they blend at 1x.
