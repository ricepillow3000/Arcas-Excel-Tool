# AH-183/AH-184 Researcher: five design libraries, read for ideas only

Read-only. Today 2026-11-17. Repo at /home/user/excel-anomaly-hunter.

**How the sources were read.** This session's proxy refused every library website (motion-primitives.com, animejs.com,
kokonutui.com, ui.watermelon.sh, ui.bklit.com, 21st.dev: `connect_rejected`). GitHub was reachable, so I read each
library's own source from a shallow clone: `ibelick/motion-primitives`, `WatermelonCorp/watermelon-platform`,
`kokonut-labs/kokonutui`, `bklit/bklit-ui`, `juliangarnier/anime` (v4.5.0). The URLs below follow each site's own
URL pattern as found in its source (kokonutui's exact URLs are in its repo; the others are `/docs/<file name>`).
Names: "Coconut UI" is **Kokonut UI** (cards, buttons; the Flutter "Coconut Design System" has no web demos).
"Backlit UI" is **Bklit UI** (charts). All five are React + Framer Motion ("motion/react") + Tailwind, except Anime.js.

Common traits to filter out: almost every React piece uses `type: "spring"` (overshoot), `filter: blur()` on enter,
and some loop forever (`repeat: Infinity`). The *idea* is what we can take; the code is not.

## A. Per library: the relevant components

### 1. Motion Primitives (https://motion-primitives.com/docs/<name>), 33 components in `components/core/`
| Component | What the visitor sees | How it is built | Vanilla in a few lines? |
|---|---|---|---|
| text-effect | A sentence arrives word by word (or by letter), fading and un-blurring | splits text into spans, staggered opacity + blur + y | yes, but blur is banned |
| animated-number | A number counts to its value | `useSpring` on a value, text written each frame | yes (we have it) |
| sliding-number | Each digit rolls like an odometer to the new value | one column of 0-9 per digit, `translateY` by spring | yes, ~25 lines, with `--ease-out` |
| text-roll | Letters flip up one by one into new text | per-letter `rotateX` 0 to 90, stagger | yes, transform only |
| text-morph | Shared letters slide into place between two words | `layoutId` per letter + spring | no (FLIP per letter, heavy) |
| in-view / animated-group | Blocks fade and rise when seen, staggered | IntersectionObserver + variants | yes (we have it) |
| transition-panel | Panel content cross-fades/slides on tab change | AnimatePresence | yes (we have the page turn) |
| animated-background | One highlight pill slides to the hovered/active item | `layoutId` shared element | yes (we have the tab mark) |
| morphing-dialog / morphing-popover | A card grows into a dialog from where it was | `layoutId` shared element | yes (we have it, pane `morph`) |
| scroll-progress | A thin bar at the top fills with the page's scroll | `useScroll` -> `scaleX`, spring smoothed | yes: CSS `animation-timeline: scroll()` |
| image-comparison | A drag handle wipes between two images (before/after) | `clipPath` set from pointer x | yes, but clip-path + drag |
| accordion / disclosure | Sections open with a height slide | height animation | we have `<details>` + chevron |
| border-trail, glow-effect, spotlight, text-shimmer(-wave), infinite-slider, spinning-text, progressive-blur | light running round a border, glowing blobs, a cursor spotlight, shimmer text, endless marquee | loops (`repeat: Infinity`), masks, blur | banned |
| magnetic, tilt, cursor | A button leans to the pointer; a card tilts in 3D; a custom cursor | springs on pointer position | banned (spring, decoration) |
| text-scramble | Text resolves through random letters | `setInterval` swapping characters | possible, gimmick |

### 2. Watermelon UI (https://ui.watermelon.sh), `src/data/contents/`: 131 animated components, 187 blocks, template `landing-01`
| Component | What the visitor sees | How built | Vanilla? |
|---|---|---|---|
| landing-01 `stats.tsx` CountingNumber | Stat figures count up once in view | `useInView` once + `animate(0, n)` on **ease [0.16,1,0.3,1]** (our `--ease-out`) | we have it |
| landing-01 `feature-visuals.tsx` | Feature cards whose little charts draw in when seen (lines by `pathLength`, bars by `scaleY`, a meter by width) | `whileInView` | bars by `scaleY`: yes; `pathLength` = stroke-dashoffset: banned |
| widget-7 | A price line draws itself, its fill fades in | `pathLength` 0 to 1 | banned as built |
| labeled-progress-indicator | A labelled bar fills to its value, a sheen passes | width animation + looping `x` sheen | yes via `scaleX`, no sheen |
| onboarding-checklist | A checklist with "2 of 5 done" and a bar; items tick off | height + rotate, springs | yes, the counter and bar |
| step-indicator / stepper / pop-stepper | Steps light up in order, the line between them fills | opacity, width | yes via `scaleX` |
| copy-confirm | Copy icon swaps to a check | opacity + scale + blur | we have it |
| time-undo-action | A delete button becomes "Undo" with a 10 s countdown | spring width, interval | idea only |
| continuous-tabs / fluid-tabs / discrete-tabs | One pill slides between tabs | shared layout | we have the tab mark |
| expand-details / reveal-copy / revealing-cards | A card expands to details; content revealed by a moving mask | border-radius, `left`, scale | partly |
| testimonials (landing-01) | Endless marquee of tweets | `x: ['0%','-50%']` loop | banned |
| bento-01/02, hero-1..38 | Bento grids, hero variants with blur-in headlines | variants, blur | AI-tell / banned |

### 3. Kokonut UI ("Coconut UI", https://kokonutui.com/docs/...), `components/kokonutui/`: ~110 components
| Component (URL) | What the visitor sees | How built | Vanilla? |
|---|---|---|---|
| metric-card (/docs/cards/metric-card) | A KPI card whose small chart morphs between periods | canvas-free SVG, `clipPath`, rAF | idea only |
| uptime-card (/docs/cards/uptime-card) | A strip of thin day bars, red where down; the bar under the pointer swells | rAF easing of widths | strip yes (static spans); the swell no |
| split-flap-text (/docs/texts/split-flap-text) | Letters flip like an airport board to new text | per-letter `rotateX`, `setInterval` | yes, transform only |
| marker-text (/docs/texts/marker-text) | A highlighter pen draws over a phrase, by hand | SVG mask path drawn by stroke | idea yes via `scaleX` from the left |
| undo-button (/docs/buttons/undo-button) | Button becomes Undo with a ring running down | `pathLength`, blur | idea only |
| scroll-index (/docs/navigation/scroll-index) | A side rail marks the section being read | rAF on scroll, arrow keys | yes, decoration from scroll |
| smooth-tab (/docs/navigation/smooth-tab) | Tab highlight and content slide together | spring, clipPath | we have it |
| card-flip (/docs/cards/card-flip) | Drag to flip a card | drag + spring rotateY | banned (drag, spring) |
| empty-state (/docs/feedback/empty-state) | A friendly empty panel whose parts arrive in turn | layoutId, blur, spring | we have an empty state |
| receipt-printer, activity-terrain, attract-button, caustics/ink/topo backgrounds | Physics paper, canvas terrain, particles, animated backgrounds | canvas, rAF loops | banned |

### 4. Bklit UI ("Backlit UI", https://ui.bklit.com/docs/components/<name>), `packages/ui/src/charts/`: 22 chart types
| Component | What the visitor sees | How built | Vanilla? |
|---|---|---|---|
| line/area chart + `chart-reveal-clip` | The series is revealed left to right on load | a clip rect's width grows, 1100 ms, ease (.85,0,.15,1) | yes via `scaleX` from the left on a mask layer |
| bar-chart | Bars grow from the baseline, staggered | spring height | yes via `scaleY` from the bottom, `--ease-out` |
| sparkline | Tiny line/bar chart, a minimal hover crosshair | one SVG path, light enter animation | yes, static SVG |
| reference-area | A shaded band marks a range (target, normal zone) | SVG rect | yes, static |
| chart-crosshair + tooltip | Hover snaps a line to the nearest point, a tooltip says its value | pointer -> nearest index | yes, ~20 lines |
| series-hover-dim / legend-hover | Hovering one series dims the rest | opacity tween | yes (we dim by filter) |
| highlight-segment | The stretch of line around the hovered point is re-stroked brighter | clip to x-range | yes |
| line-series-terminal-marker | A dot (and ring) on the last point | SVG circle | yes, static |
| loading-sweep / use-grid-shimmer | A band of light crosses a skeleton chart, looping | SVG mask, loop | we have a once-only sweep |
| live-line-chart, particle-line | A streaming line; particles along a line | rAF loops | banned |

### 5. Anime.js v4.5.0 (https://animejs.com/documentation/...), `src/`
| Feature | What it does | Vanilla? |
|---|---|---|
| `stagger(…, {grid, from})` (utilities/stagger) | Delays by each item's distance from a chosen cell, so a grid lights in a ripple from that cell | yes, ~8 lines: delay = distance x step |
| timeline (timeline) | Several animations placed on one clock, labels, overlaps | WAAPI `delay`s do it |
| `svg.createDrawable` (svg/createdrawable) | Draws a path along its length | stroke-dashoffset: banned |
| `svg.morphTo` | Morphs one shape into another | `d` attribute: banned |
| `text.split` / `scrambleText` (text) | Splits text into words/letters to stagger; scramble resolve | split yes; scramble gimmick |
| `onScroll` (events/onscroll) | Ties an animation's progress to scroll position | we have it (`view()` + fallback) |
| `createLayout` / AutoLayout (layout) | FLIP: elements glide to their new place when the DOM changes | yes, ~15 lines FLIP with transform |
| `utils.round` modifier on a number | A count tweened as text, rounded | we have it |
| `createDraggable`, springs, `irregular` easing | Drag with inertia; spring and jittery easings | banned |

## B. Already have (do not re-propose)

| Library idea | Ours |
|---|---|
| Number ticker / counting number | proof strip count-up `site/home.js:548-560` (+ `count()` `:38-52`); filter counts tick `home.js:338-342`; pane `countUp` `frontend/components/motion.js:102` |
| In-view reveal + stagger (in-view, animated-group, whileInView) | `.reveal-item` + `data-reveal-group`, `site/motion.js:132-210`; rows 30 ms (`docs/design/motion.md:398`); pane `stagger` `motion.js:94` |
| Sliding tab highlight (animated-background, continuous-tabs, smooth-tab) | `span.tab-mark`, `home.js:250` `markTo`; doc `motion.md:403-404` |
| Morphing dialog / popover from trigger | detail box `openMatrix` `home.js:452`, interruptible `motion.md:502`; pane `morph` view transition `motion.js` (after turnIn) |
| Transition panel | the page turn `home.js:197` `turn`; pane card `turnIn` `motion.js:53` |
| Skeleton + sweep (loading-sweep, grid-shimmer) | sample skeleton `home.js:77-140`; download facts skeleton; pane `#scan-skeleton` `taskpane.html:75` |
| Copy confirm / icon crossfade | Copy button `home.js:621`, `motion.md:407` |
| Hairlines drawn (masks for reveals) | `span.rule` scaleX by scroll `styles.css:776-795` |
| Scroll-linked decoration (onScroll) | `data-depth` drift, `.rule` draw, `motion.md:252-294` |
| Accordion | FAQ chevron `motion.md:525-527` |
| Shared element highlight | `.row-mark` gold frame `home.js:568-619` |
| Check mark drawn once | pane `.tick` `frontend/styles/components.css:92-96` |
| "2 of 5 done" counter (onboarding-checklist) | pane `doneOf` `frontend/features/scan.js:189`, said in `#notice` `fix.js:304,365` |
| Press, hover fill by mask | `--press .97`, fills `motion.md:399-400` |
| Progress bar that fills once | sample Scanning meter `home.js:275-298`; pane `#busy-bar` `taskpane.html:61` |

What is missing: nothing on the site lets a visitor **see the whole 60-row sheet** (13 of 60 rows are shown with "⋯");
no chart anywhere (the 4 "Total jumped sharply" rows are a sentence with no picture, the critique's noise point);
the sample's Accept swaps the row with no motion at all (`home.js:518-527`, `tr.replaceWith(row)`); the Scanning tab is
"mostly empty" (`2026-11-16-engagement-critique.md`, Sample scan); the pane's finish line is words only.

## C. Ranked shortlist (all pass the hard constraints as described)

1. **The fix lands in the cell (sample Accept).** From: Motion Primitives sliding-number / text-roll, Kokonut
   split-flap-text, marker-text (as a `scaleX` mask). Where: Accept handler `site/home.js:518-527`, `.grid td.mended`
   `site/styles.css:392`. What: today the row is swapped instantly. Keep the DOM swap at once (tests read it), and lay an
   `aria-hidden` copy of the old cell over the new one (the page turn's own trick): old "-5" rises 0.6em and fades,
   new "57" comes up from 0.6em, 360 ms `--ease-out`; then the gold underline (`box-shadow` today, so move it to a
   `::after` bar) draws by `scaleX` from the left; the row's "Fixed:" text fades in 30 ms after. Replaces: a dead click.
   ~25 JS + 10 CSS. Risk low-medium: AH-171 Accept block `tools/test_site.mjs:1476-1510` reads rows/counts right after
   the press (unchanged DOM), "accepted" AA state, reduced motion = none; forced colours keeps `td.mended` border
   (`styles.css:851`).
2. **A 60-row strip: the whole sheet at a glance.** From: Kokonut uptime-card (a strip of thin bars), Bklit
   series-hover-dim. Where: `.ws-top` beside "60 rows · 5 columns", `site/index.html:60-61`. What: 60 static `<i>`
   marks (static markup: layer 12 forbids HTML built from data), wine for probably wrong (11, 22, 31), gold-outline for
   worth a check (5, 21, 41, 57), the rest a paper tint. The filters dim marks that do not match (opacity, as the rows);
   an Accept turns its mark plain (opacity crossfade). Marks arrive once with the skeleton's rows (30 ms steps,
   opacity). Shows "7 of 60, the rest are fine" without a scroll; answers "what is in the ⋯". Height 0 desktop
   (phone: one 8 px line, fits under the title). ~60 HTML + 15 CSS + 6 JS. Risk low-medium: `test_site_sample.py` must
   hold each mark to the engine's scan (the generator at `:28` gives all 60 rows); the skeleton block and CLS; the
   mark is decoration (`aria-hidden`), the figure keeps its `aria-labelledby`.
3. **The Scanning tab checks the strip row by row.** From: Anime.js `stagger` (timeline), Watermelon step-indicator.
   Where: `#p-busy` `site/index.html:189-200`, `scan()` `site/home.js:275-298`. What: while the existing meter fills
   (1100 ms), the same 60 marks (a copy in `#p-busy`, or the shared strip from item 2) light top to bottom by opacity,
   18 ms apart, and the 7 flagged ones take their colour as the meter reaches them; then the tab turns to Findings as
   today. One run per choosing (AH-147 holds), nothing loops. Fills the "622 px of air" with the visitor's sheet being
   read. ~20 JS + 10 CSS. Risk medium: AH-147 timings in `test_site.mjs`, `test_site_sample.py:241`
   (the pane's progress words stay), reduced motion = the marks shown at once.
4. **A picture for a jump.** From: Bklit sparkline + reference-area + line-series-terminal-marker + chart-reveal-clip.
   Where: detail boxes `#m5 #m21 #m41 #m57` (`site/index.html:146-185`), and `#m22` for Units. What: an inline SVG,
   about 240 x 56 px, Total by OrderDate for the 60 rows, the flagged point a wine dot, the usual step's band
   shaded paper-2; for `#m22`, Units as a dot strip with the "usual limit" band and 7777 off the end ("7777 ->").
   Revealed once as the box opens: a paper mask layer over the line slides away by `scaleX` from the left, 600 ms
   `--ease-out` (never `stroke-dashoffset`). Lets a sceptical analyst see why a jump is "worth a check" and also that
   it may be real (AH-167 humility). Static SVG points written in the HTML. ~40 HTML + 15 CSS + 8 JS. Risk medium:
   the box's height on a phone (`motion.md:534-547` placement rules; keep it inside the popover), the points must be
   the generator's (`test_site_sample.py` reads the `points` back), AA: the line navy on paper, gold only for lines.
5. **Pane: the finish line as a bar.** From: Watermelon onboarding-checklist + labeled-progress-indicator, Bklit bar
   reveal. Where: the foot bar `#status` / `#notice` `frontend/taskpane.html:59-65`, `doneOf` `scan.js:189`. What: a
   2 px gold-on-paper hairline (gold is for lines) across the foot bar's top, `scaleX(done/total)` from the left,
   300 ms `--ease-out` after each Accept/Dismiss/Undo, beside the words "2 of 5 rows done."; at "All 5" the existing
   `.tick` draws. Height 0 (held space, AH-149/165). ~8 JS + 6 CSS. Risk low: selfcheck pins `doneOf`; e2e AH-171
   "at most one line shows"; High Contrast must keep it drawn (CanvasText).
6. **Pane: the change rolls in the card on Accept.** From: Motion Primitives text-roll / sliding-number. Where:
   `#fix-changes` `frontend/taskpane.html:139`, after the write in `fix.js` (~`:300`). What: in "C11: -5 -> 57", the old
   value lifts and fades and the arrow's target settles, 300 ms, once, inside the held `.fix-body`. Replaces: a
   status line only. ~15 lines. Risk low-medium: e2e Accept/Undo paths, "nothing moves when a fix lands" means the
   box keeps its size (transform only inside), reduced motion none.
7. **Pane: a row in the list turns "Fixed" in front of you.** From: Kokonut/Watermelon icon crossfade, Motion
   Primitives text-morph (as a crossfade). Where: `rowItem` `frontend/components/row-item.js:7-11`, `.flagged-list li.done`
   `components.css:140`. What: on Back after a decision, the decided row's tag cross-fades from "Probably wrong" to
   "Fixed" (opacity, 250 ms) and its swatch fades to muted; focus already lands on that row. ~10 lines. Risk low: e2e
   "the row after Back" focus; selfcheck innerHTML `esc()` rule (no new template values).
8. **Install steps light as you read them.** From: Watermelon stepper / step-indicator, Kokonut scroll-index.
   Where: `.steps li::before` numbers `site/styles.css:495-496`, `site/index.html:317-326`. What: each "01".."04"
   number is drawn in a paper-2 tint and turns wine as its hairline finishes drawing (the same `view()` range as
   `.rule`, `--col` steps): a pure function of the scroll, so it reverses on scroll back. Decoration, but it reads as
   "you are on step 3". ~8 CSS (+3 lines in the JS fallback's pose list). Risk low: the static motion test (opacity on
   an overlay copy of the number, never `color`), AA of the faded number (it is decoration over a real wine number).
9. **Proof figures as a 201-cell sheet.** From: Anime.js grid stagger `from` a cell, Bklit bar reveal. Where:
   `#proof dl.proof` second figure `site/index.html:297`. What: under "199 of 201", a 201-square grid (navy squares,
   2 hollow gold-outline ones), filling by a grid ripple once as the figure counts (opacity, 900 ms total, shared with
   `count()`). "Every cell" made literal. ~10 HTML (CSS-generated via a repeating gradient is impossible to stagger; so
   201 spans or a 2-layer trick) + 15 CSS. Risk medium: home height budget (critique: 8,397 phone max; costs ~60 px),
   the AH-133/AH-171 proof checks, AA none (decorative). Only if items 1-3 leave room.
10. **Scroll progress hairline.** From: Motion Primitives scroll-progress. Where: under the sticky bar (`.bar`,
    `site/index.html:36-44`). What: a 1 px gold line scaled by the page's scroll (`animation-timeline: scroll()`,
    fallback in `motion.js`'s one scroll frame). Decoration only; low fun value. ~10 CSS + 4 JS. Risk low (static
    property test passes, scaleX); home page only or every page (curtain keeps the header mounted).
11. **FLIP when a filter hides rows.** From: Anime.js `createLayout`. Where: filters `site/index.html:69-74`,
    `show()`/filter code in `home.js`. What: when a filter dims rows today nothing moves (rows only dim); if a future
    change collapses non-matching rows, slide the rest by `translateY` from their old place. Today it would *add*
    movement nobody asked for: keep in reserve. ~15 lines. Risk medium (filter blocks pinned).

Builder notes: every item above uses only `transform`/`opacity`, `--ease-out` or `--ease-in-out`, plays once, and is
skipped under `prefers-reduced-motion` (`document.getAnimations()` empty) and without JS (static final state). New
words must pass `test_plain_words.py`; new class names grepped across `site/` first (CLAUDE.md, the `.skip` lesson).

## D. Rejected (one line each)

- Text effect / blur-in headline (MP text-effect, Watermelon heroes): animates `filter`; the hero already enters; an AI tell.
- Border trail, glow, spotlight, shimmer text, shimmer button, sheen on progress bars: loop forever and/or glow.
- Infinite slider / testimonial marquee (Watermelon landing-01): loops; John chose measured results over reviews (AH-133).
- Magnetic button, tilt card, custom cursor (MP), attract-button (Kokonut): springs, tween what the hand drives, gimmick.
- Card flip by drag (Kokonut), draggable carousels (Anime.js): drag + spring; "no drag on the site".
- Image comparison wipe for Findings/After fixes (MP): clip-path on drag (only the curtain may use clip-path), and the tabs are pinned (AH-147).
- SVG line drawing (Anime.js createDrawable, Watermelon `pathLength`, Kokonut marker-text as built): stroke-dashoffset; item 4 uses a `scaleX` mask instead.
- Shape morph (Anime.js morphTo), text-morph per letter (MP): `d` / layout per letter; heavy for no data gain.
- Text scramble (MP, Anime.js): gimmick, reads as "AI"; the count-up already gives figures life.
- Split-flap on the proof figures (Kokonut): duplicates the count-up.
- Bento grids (Watermelon bento-01/02, Kokonut bento-grid): generic identical boxes, an AI tell; checks are a list by design (AH-159).
- Crosshair corner marks on stats (Watermelon stats): template decoration.
- Timed undo countdown (Watermelon time-undo-action, Kokonut undo-button): the pane's Undo outlives a reload (`undo-store.js`); a countdown would say something false.
- Metric card with morphing chart (Kokonut): needs period data the site does not have.
- Canvas/physics pieces (receipt-printer, activity-terrain, backgrounds, particle-line, live-line): rAF loops; we already have one field.
- Grid ripple from row 11 replacing the skeleton's top-down landing (Anime.js): the skeleton is John's spec (AH-89/92/99/171).
- Pane sparkline of a column's values: needs a new `/scan` field (layers 4, 8, openapi, privacy twins): too big for this ticket.
- Hover crosshair/tooltip on the sample sheet (Bklit): the row hover, podium and detail box already do this job.
- Anything from the 2026-11-16 council's REJECT list (remove crest, "about 2 minutes", two hero buttons, case teaser, changing the 4 jump rows, dropping Scanning).
