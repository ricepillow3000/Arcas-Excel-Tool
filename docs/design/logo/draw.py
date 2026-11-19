"""Writes every drawing of the Arcas mark (AH-203) into this folder: `python docs/design/logo/draw.py`.

The mark is John's pick of a capital A made of tiles, like the cells of a sheet: six rows of slanted tiles, wine at the
top stepping to navy at the bottom, and one gold tile in the A's opening, the one cell Arcas finds. Each drawing is made
for the pixels it lands on: a row's height and the gap between rows are whole pixels at the size it is shown, so every
flat edge is sharp at 1x; the 16 and 32 px icons are placed pixel by pixel.
"""
from pathlib import Path

HERE = Path(__file__).parent
GOLD, PAPER = "#997D3A", "#F7F5F0"
# wine to navy in even OKLab lightness steps, the middle steps' colour held up (a straight mix sagged to grey)
STEPS = ["#6B1E2E", "#5B1E30", "#4B1C35", "#371C3A", "#211B3C", "#0C1938"]
# each row's tiles as spans of 6 columns; "G" is the gold tile, in the opening above the crossbar
ROWS = [[(0, 2, ""), (2, 4, ""), (4, 6, "")], [(0, 2, ""), (4, 6, "")], [(0, 2, ""), (2, 4, "G"), (4, 6, "")],
        [(0, 2, ""), (2, 4, ""), (4, 6, "")], [(0, 2, ""), (4, 6, "")], [(0, 2, ""), (4, 6, "")]]
TALL, TOP = 1.06, 0.46  # 6% taller than wide; the top row 46% of the base (50% read as a pyramid)


def num(v):
    return f"{round(v, 3):g}"


def tiles(h, g, ox=0.0, oy=0):
    """The A at row height h and gap g (whole pixels where it is shown), its top left at (ox, oy). Every slanted
    edge points at one vanishing point above the A, so the tiles lean as its sides do."""
    H = 6 * h + 5 * g
    wb = H / TALL
    wt = wb * TOP
    half = lambda y: (wt + (wb - wt) * y / H) / 2
    x = lambda u, y: ox + wb / 2 + u * half(y)
    out = []
    for r, spans in enumerate(ROWS):
        y0, y1 = r * (h + g), r * (h + g) + h
        for c0, c1, kind in spans:
            u0, u1 = c0 / 3 - 1, c1 / 3 - 1
            dl, dr = (0 if c0 == 0 else g / 2), (0 if c1 == 6 else g / 2)
            pts = [(x(u0, y0) + dl, y0), (x(u1, y0) - dr, y0), (x(u1, y1) - dr, y1), (x(u0, y1) + dl, y1)]
            d = "M" + " L".join(f"{num(px)} {num(oy + py)}" for px, py in pts) + " Z"
            part, fill = ("cell", GOLD) if kind == "G" else ("tile", STEPS[r])
            out.append(f'<path data-part="{part}" data-row="{r}" d="{d}" fill="{fill}"/>')
    return "".join(out), wb, H


def mark(h, g):
    body, wb, H = tiles(h, g)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {num(wb)} {H}">{body}</svg>\n'


def icon(side, h, g):
    """The mark on a paper square: on a dark ribbon or tab, and on the pane's navy band, it keeps its true colours
    (wine is 1.6:1 on navy; tints drawn for navy read too bright and the gold not gold, John 2026-11-19)."""
    body, wb, H = tiles(h, g, ox=(side - (6 * h + 5 * g) / TALL) / 2, oy=(side - (6 * h + 5 * g)) // 2)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}"><rect width="{side}" height="{side}" '
            f'fill="{PAPER}"/>{body}</svg>\n')


# the 16 and 32 px icons, placed pixel by pixel: (top row, [(from x, to x, step or "G"), ...]), each row a mirror image
PIXELS = {
    # rows of 2 px, no gaps: the apex one bar, the crossbar joining both legs, the gold one 2 x 2 cell (a gap at 16 px
    # cut the crossbar off and the A read as an arch with a lantern)
    16: (2, [(1, [(5, 11, 0)]), (3, [(4, 6, 1), (10, 12, 1)]), (5, [(3, 6, 2), (7, 9, "G"), (10, 13, 2)]),
             (7, [(3, 13, 3)]), (9, [(2, 6, 4), (10, 14, 4)]), (11, [(1, 6, 5), (10, 15, 5)])]),
    # rows of 4 px, 1 px apart, 1 px from the top (the mass is low); the legs' tiles 4, 5, 6, 7, 7, 8 wide, the middle
    # tiles never wider than the legs', the gold 6 x 4 with paper either side
    32: (4, [(1, [(9, 13, 0), (14, 18, 0), (19, 23, 0)]), (6, [(8, 13, 1), (19, 24, 1)]),
             (11, [(6, 12, 2), (13, 19, "G"), (20, 26, 2)]), (16, [(5, 12, 3), (13, 19, 3), (20, 27, 3)]),
             (21, [(3, 10, 4), (22, 29, 4)]), (26, [(2, 10, 5), (22, 30, 5)])]),
}


def pixel_icon(side):
    h, rows = PIXELS[side]
    rects = []
    for y, spans in rows:
        for x0, x1, k in spans:
            assert (side - x1, side - x0, k) in spans, (side, y, x0)  # every row is its own mirror image
            fill = GOLD if k == "G" else STEPS[k]
            part = "cell" if k == "G" else "tile"
            rects.append(f'<rect data-part="{part}" x="{x0}" y="{y}" width="{x1 - x0}" height="{h}" fill="{fill}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}" shape-rendering="crispEdges">'
            f'<rect width="{side}" height="{side}" fill="{PAPER}"/>{"".join(rects)}</svg>\n')


DRAWINGS = {
    "mark-157.svg": lambda: mark(22, 5),             # the download's logo, shown 157 px tall; the sharing card
    "mark-29.svg": lambda: mark(4, 1),               # the site header, 29 px tall (1.8 times its 16 px capitals)
    "mark-23.svg": lambda: mark(3, 1),               # the pane on paper (Check as you work's note), 23 px tall
    "icon-16.svg": lambda: pixel_icon(16),
    "icon-32.svg": lambda: pixel_icon(32),
    "icon-48.svg": lambda: icon(48, 6, 1),
    "icon-64.svg": lambda: icon(64, 8, 2),
    "icon-80.svg": lambda: icon(80, 10, 2),
    "icon-180.svg": lambda: icon(180, 22, 5),
    "icon-192.svg": lambda: icon(192, 24, 5),
    "icon-256.svg": lambda: icon(256, 32, 8),
    "icon-512.svg": lambda: icon(512, 64, 16),
}

if __name__ == "__main__":
    for name, draw in DRAWINGS.items():
        (HERE / name).write_text(draw(), encoding="utf-8")
        print(name)
