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
- The emblem is John's, at its size, 4 units higher on the 80 than AH-121's, in the room the drape left.

| Drawing | Grid | Used for | What it keeps |
|---|---|---|---|
| `mark-80.svg` | 80, 1 unit = 1 px | the download's logo (160 px, 2 px a unit), `crest3-80.png` (ribbon 80), the exe's 256, the site's 192 and 512 icons, the 180 on paper, the sharing card (at 320) | everything: a leaf blade from a point at y 4 to 8 wide at y 16 and 4 at y 22, the pole 38 to 42 down to y 40, the bar 12 to 68 from y 40 to 44, the banner 20 to 60 from y 44 with its hem at 71 and its point at 75, the gold line 2 units in, the emblem (panels 61 to 67, the ring at y 56) |
| `mark-64.svg` | 64 | `crest3-64.png`: the pane's logo at 2x, the manifest's high resolution icon, the 64 px favicon, the exe's 64 | the same parts redrawn on their own grid (never 80 scaled by .8): pole and bar 4 px, which is the 2 CSS px the pane's navy band needs at 2x; the blade 8 at its widest; the gold line 1 px set 2 px in; AH-121's 64 px emblem, 3 px higher |
| `mark-40.svg` | 32 x 40, 1 unit = 1 CSS px | the site header (inline, 40 px tall, `aspect-ratio: 32 / 40`), the exe's 48 (drawn 1:1, centred) | a tip 2 px wide from its second row (a needle point faded to a gradient at 1x), the blade 4 at its widest, the pole 2 and the bar 3 (the 80's 4 units scaled to this banner), the gold line 1 px set 1 px in, the ring's stroke 1.5 px; sharp at 1x, smooth at 2x and 3x |
| `mark-32.svg` | 32 | `crest3-32.png`: favicon, ribbon 32, the pane's logo at 1x, the exe's 32 | placed pixel by pixel: the tip 2 px, the blade 4, the pole and the bar 2 px solid, a navy row under the bar, the gold line 1 px set 1 px in with its hem a V of 3 px steps, and the emblem as AH-121's 32 px ring alone: a 2 px ring whose hole a 1 px slash splits into two navy corners (the panels were a smear at this size) |
| `mark-16.svg` | 16 | `crest3-16.png`: favicon, ribbon 16, the exe's 16 | placed pixel by pixel, centred on column 7: a 1 px tip over a 3 px blade, the bar, and the banner with its gold line on the edge, the bar standing for its top (set 1 px in it left the ring no gap and read as nested squares), and AH-121's 1 px ring with a 1 px slash poking past it |

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
  above the Download button; `tools/test_site.mjs` checks every page holds them as they are here. Their `data-part`
  groups (spear, bar, banner, emblem) are what its browser check reads: the spear and bar fill gold, the banner navy with
  its gold line a stroke, the emblem paper; the spear stands on the bar over the banner's middle, the bar sits on the
  banner and is wider than it, and the emblem lies inside the gold line.
- Office caches ribbon icons per URL: new art gets new file names and a `<Version>` bump in `frontend/manifest.xml`
  (`crest3-*.png` and 1.0.9.0 for this one), and every older name still answers with today's crest (`server.OLD_ICONS`).

Palette (the tokens in `site/styles.css`): gold #997D3A for the spear, pole, bar and the banner's line; navy #0C1938 for
the banner; paper #F7F5F0 for the emblem.

Honest weaknesses: at 16 px the gold line is the banner's edge, not set in, and the 3 px blade on its 1 px pole can read
as a small cross; at 64 px on the pane (32 CSS px at 2x) the gold line is one device pixel; the 80's blade has a point at
its tip, so at 80 px at 1x its first rows are a blend.
