"""Writes every drawing of the Arcas mark (AH-203) into this folder: `python docs/design/logo/draw.py`.

The mark is John's A of tiles inside a gold ring: a capital A made of six rows of slanted tiles, like the cells of a
sheet, wine at the top stepping to navy at the bottom, dead centre in a paper coin a little darker toward its rim, with
the site's own grain over it, ringed in gold. Each drawing is made for the pixels it lands on: a row's height and the
gap between rows are whole pixels at the size it is shown, and the A's box sits exactly in the middle of the coin (the
coin's size and the A's height both even or both odd, so the middle falls on a whole pixel).
"""
from math import hypot
from pathlib import Path

HERE = Path(__file__).parent
GOLD, PAPER = "#997D3A", "#F7F5F0"
# wine to navy in even OKLab lightness steps, the middle steps' colour held up (a straight mix sagged to grey)
STEPS = ["#6B1E2E", "#5B1E30", "#4B1C35", "#371C3A", "#211B3C", "#0C1938"]
# the coin: the header bar's own paper, --paper at its heart to --paper-2 at its rim (John: "the gradient white matches
# the textures of the hero line"), and the bar's grain (styles.css --grain: the same noise, colour, scale and 7% strength)
CENTRE, RIM = "#F7F5F0", "#EFECE4"
# each row's tiles as spans of 6 columns: the top, the opening, the opening, the crossbar, the legs
ROWS = [[(0, 2), (2, 4), (4, 6)], [(0, 2), (4, 6)], [(0, 2), (4, 6)], [(0, 2), (2, 4), (4, 6)], [(0, 2), (4, 6)],
        [(0, 2), (4, 6)]]
TALL, TOP = 1.06, 0.46  # 6% taller than wide; the top row 46% of the base (50% read as a pyramid)
GAP = 0.12  # the least clear gap between the A's corners and the ring, as a share of the coin's inner radius


def num(v, p=3):
    return f"{round(v, p):g}"


def tiles(h, g, ox, oy, lean=False):
    """The A at row height h and gap g, its box's top left at (ox, oy). Every slanted edge points at one vanishing point
    above the A, so the tiles lean as its sides do."""
    H = 6 * h + 5 * g
    wb = H / TALL
    wt = wb * TOP
    half = lambda y: (wt + (wb - wt) * y / H) / 2
    x = lambda u, y: ox + wb / 2 + u * half(y)
    out = []
    for r, spans in enumerate(ROWS):
        y0, y1 = r * (h + g), r * (h + g) + h
        for c0, c1 in spans:
            u0, u1 = c0 / 3 - 1, c1 / 3 - 1
            dl, dr = (0 if c0 == 0 else g / 2), (0 if c1 == 6 else g / 2)
            pts = [(x(u0, y0) + dl, y0), (x(u1, y0) - dr, y0), (x(u1, y1) - dr, y1), (x(u0, y1) + dl, y1)]
            d = "M" + " L".join(f"{num(px, 1 if lean else 3)} {num(oy + py)}" for px, py in pts) + "Z"
            tag = "" if lean else f' data-part="tile" data-row="{r}"'
            out.append(f'<path{tag} d="{d}" fill="{STEPS[r]}"/>')
    return "".join(out)


def coin(D, h, g, ring, pid, grain=True, sweep=False, side=None, plate=None, lean=False):
    """A coin of diameter D: the disc, the grain, the gold ring of width `ring`, and the A dead centre. `pid` keeps its
    ids apart from another drawing's on the same page. With `sweep`, the ring is shown through two half discs that CSS
    turns once (the ring draws itself, AH-203); at rest they show it whole, so with no CSS it is simply there. A `lean`
    drawing leaves out the parts' names and rounds its tiles' edges to a tenth of a pixel: the site's header is on every
    page, and its bytes are each page's (tools/test_site.mjs caps them)."""
    H = 6 * h + 5 * g
    c = D / 2
    oy = c - H / 2
    assert oy == int(oy), f"coin {D}: the A's rows would fall between pixels (an even coin wants an even A)"
    wb = H / TALL
    inner = c - ring
    corner = hypot(wb / 2, H / 2)  # the foot's corners, the A's farthest points from the middle
    assert corner <= inner * (1 - GAP), f"coin {D}: the A comes within {round((1 - corner / inner) * 100)}% of the ring"
    side = side or D
    o = (side - D) / 2
    at = f' transform="translate({num(o)} {num(o)})"' if o else ""
    defs = (f'<radialGradient id="{pid}-d" cx="50%" cy="42%" r="62%"><stop offset="0" stop-color="{CENTRE}"/>'
            f'<stop offset="1" stop-color="{RIM}"/></radialGradient>')
    noise = ""
    if grain:
        defs += (f'<filter id="{pid}-g" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" '
                 f'baseFrequency=".8" numOctaves="3" seed="3" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .05 '
                 f'0 0 0 0 .1 0 0 0 0 .22 0 0 0 -2 1.25"/><feComponentTransfer><feFuncA type="linear" slope=".07"/></feComponentTransfer>'
                 f'<feComposite in2="SourceGraphic" operator="in"/></filter>')
        # its 7% inside the filter, so the circle itself stays opaque (test_site.mjs reads every part of the logo opaque)
        noise = f'<circle cx="{num(c)}" cy="{num(c)}" r="{num(inner)}" fill="#000" filter="url(#{pid}-g)"/>'
    sweeping, whole = "", ""
    if sweep:  # each half disc clipped to its own half, turning from the other half into place: a clockwise sweep from 12
        # each half's clip stops half a pixel short of the middle: a half turned onto the other side otherwise showed its
        # smoothed edge as a tick at 6 o'clock before the sweep came to it
        defs += (f'<clipPath id="{pid}-r"><rect x="{num(c + .5)}" width="{num(c - .5)}" height="{D}"/></clipPath>'
                 f'<clipPath id="{pid}-l"><rect width="{num(c - .5)}" height="{D}"/></clipPath>'
                 f'<mask id="{pid}-m"><g clip-path="url(#{pid}-r)"><path class="sweep-a" d="M{num(c)} 0 A{num(c)} {num(c)} 0 0 1 {num(c)} {D} Z" fill="#fff"/></g>'
                 f'<g clip-path="url(#{pid}-l)"><path class="sweep-b" d="M{num(c)} {D} A{num(c)} {num(c)} 0 0 1 {num(c)} 0 Z" fill="#fff"/></g></mask>')
        # the masked ring sweeps; the whole ring over it shows once the sweep ends (where the two halves meet, their
        # edges' smoothing left a hairline at 12 and 6), and at rest it is the ring
        sweeping = (f'<circle class="ring-sweep" cx="{num(c)}" cy="{num(c)}" r="{num(c - ring / 2)}" fill="none" stroke="{GOLD}" '
                    f'stroke-width="{num(ring)}" mask="url(#{pid}-m)"/>')
        whole = ' class="ring-whole"'
    bg = f'<rect width="{side}" height="{side}" fill="{plate}"/>' if plate else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {num(side)} {num(side)}"><defs>{defs}</defs>{bg}<g{at}>'
            f'<circle{"" if lean else ' data-part="disc"'} cx="{num(c)}" cy="{num(c)}" r="{num(inner)}" fill="url(#{pid}-d)"/>{noise}'
            f'{sweeping}<circle{"" if lean else ' data-part="ring"'}{whole} cx="{num(c)}" cy="{num(c)}" r="{num(c - ring / 2)}" fill="none" '
            f'stroke="{GOLD}" stroke-width="{num(ring)}"/>{tiles(h, g, c - wb / 2, int(oy), lean)}</g></svg>\n')


# the 16 px icon, placed pixel by pixel: a 1 px gold ring, the disc one flat colour, the A 10 wide and 8 tall dead
# centre (its box from 3 to 13 and 4 to 12, the coin's from 0 to 16); "." transparent, "o" ring, "-" disc, 0-5 the steps
ICON_16 = [
    ".....oooooo.....",
    "...oo------oo...",
    "..o----------o..",
    ".o------------o.",
    ".o----0000----o.",
    "o----11--11----o",
    "o----22--22----o",
    "o---33333333---o",
    "o---44----44---o",
    "o---44----44---o",
    "o--555----555--o",
    ".o-555----555-o.",
    ".o------------o.",
    "..o----------o..",
    "...oo------oo...",
    ".....oooooo.....",
]
DISC_16 = "#F3F1EA"  # the coin's gradient at the middle of its radius


def icon_16():
    fill = {"o": GOLD, "-": DISC_16, **{str(i): s for i, s in enumerate(STEPS)}}
    rects = []
    for y, row in enumerate(ICON_16):
        assert len(row) == 16 and row == row[::-1], y  # every row is its own mirror image
        for x, ch in enumerate(row):
            if ch != ".":
                rects.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{fill[ch]}"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" shape-rendering="crispEdges">{"".join(rects)}</svg>\n'


DRAWINGS = {
    "coin-157.svg": lambda: coin(157, 12, 3, 6, "c157"),                   # the download's logo, the README
    "coin-41.svg": lambda: coin(41, 3, 1, 2, "c41", sweep=True, lean=True),           # every site page's header, its ring drawn once
    "coin-31.svg": lambda: coin(31, 2, 1, 1.5, "c31", sweep=True),         # the pane: header (drawn once), footer, notes
    # the icons carry no grain: unseen at their size, and noise made the 512 px PNG 324 KB (the site's cap is 32 KB)
    "icon-16.svg": icon_16,
    "icon-32.svg": lambda: coin(31, 2, 1, 1.5, "i32", grain=False, side=32),
    "icon-48.svg": lambda: coin(47, 3, 1, 2, "i48", grain=False, side=48),
    "icon-64.svg": lambda: coin(64, 4, 2, 2.5, "i64", grain=False),
    "icon-80.svg": lambda: coin(80, 6, 2, 3, "i80", grain=False),
    "icon-180.svg": lambda: coin(164, 12, 4, 7, "i180", side=180, plate=PAPER, grain=False),  # an iPhone shows no transparency
    "icon-192.svg": lambda: coin(192, 14, 4, 8, "i192", grain=False),
    "icon-256.svg": lambda: coin(256, 18, 6, 10, "i256", grain=False),
    "icon-512.svg": lambda: coin(512, 36, 12, 20, "i512", grain=False),
}

if __name__ == "__main__":
    for old in HERE.glob("*.svg"):
        old.unlink()
    for name, draw in DRAWINGS.items():
        (HERE / name).write_text(draw(), encoding="utf-8")
        print(name)
