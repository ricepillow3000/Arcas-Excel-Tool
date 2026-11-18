# R3: load speed (John's tool #4) and the 3D crest (tool #5), AH-193

Researcher 3, 2026-11-18. Read-only on the repo (main, v0.1.431). Every number below was measured on this box.
Scripts and raw data: `ah193/r3/` (measure.mjs, trace.mjs, gate-slowphone.mjs, pane.mjs, paneflash.mjs,
idle.mjs, lh/*.json). Variant copies of site/ (v1, v2, v3) live there too, never in the repo.

## A. What I ran or read, and what I could not

- Read whole: `90-System/Design-Rulebook.md` (969 lines), `docs/design/motion.md` (594), CLAUDE.md rows L11 and L12.
- **chrome-devtools-mcp is not installed.** Stood in with Playwright 1.56 + Chromium 1243 over CDP: Tracing
  (devtools.timeline), `Performance.getMetrics`, `Emulation.setCPUThrottlingRate` 4, `Network.emulateNetworkConditions`
  (150 ms, 1.6 Mbps down, 750 kbps up: the gate's own slow phone), PerformanceObserver (paint, LCP, layout-shift,
  longtask), V8/CSS coverage. All browser jobs under `flock /tmp/ah-browser.lock`.
- **Lighthouse 12.8.2 runs** (`npx lighthouse@12`, `CHROME_PATH=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`),
  mobile and desktop presets, 3 pages, through a local server that gzips like GitHub Pages (`r3/lh/*.json`).
- `gate-slowphone.mjs` = the slow-phone block of `tools/test_site.mjs:2381-2395` with its server (748-756, no gzip),
  copied as is, so its numbers are the gate's numbers. 7 runs a variant.
- Pane: the real engine (`e2e/engine.py`) and `e2e/fake-office.js`, as `ah170p/shots.mjs` does, 3 runs at 1x and 4x CPU.
- img2threejs: `npx --yes img2threejs@latest --help` runs (v0.2.0), and the GitHub repo was cloned and read.
- **Could not:** reach the live site (proxy 403 on ricepillow3000.github.io), so "Pages gzips" rests on
  `motion.md:363`, not a live header. Did not run `img2threejs install`: it writes skill links into every agent host on
  this PC (a config change no agent message can authorize), and the tool itself is an agent pipeline, not a converter.

## B. Findings

**F1. Site, slow phone: the headline waits for every deferred script (high).** `site/index.html:441-446`, `boot.js:12-14`,
`motion.js:229-230,384`. Chain, from a trace (`r3/trace-home-raw.json`): index.html 52 KB done at 363 ms; styles.css
(100 KB, render-blocking) and the preloaded font (27 KB) share the line, CSS done 910-1077 ms; boot.js waits for the
CSS before it runs (1081-1088 ms) and holds the hero (`data-ah`); Chromium asks for the six `defer` scripts (120 KB, Low
priority) only after the CSS, all at once, so motion.js (27 KB) lands at ~1900 ms; then field, home (231 ms of script
at 4x CPU), support, transition and count run back to back, and the entrance's first frame only paints after
DOMContentLoaded (2223-2280 ms). Gate numbers today: headline shown **2250-2342 ms** (median 2303), at rest 3451-3508,
styles.css **881-888 ms** (the brief's ~866). With other jobs on the box that becomes the flaky 2400-2650 against 2500.
A second ceiling sits at the same place: boot.js's 1.4 s deadline fires at ~1086 + 1400 = 2486 ms whenever motion.js is
later. Breaks nothing yet, but M12 has ~160-250 ms of room left.

**F2. Why the margin vanished: bytes crept, 15 days (high).** The budget is "twice the slowest of 5 runs on 2026-11-02"
(1205 ms). Since then (git, same paths): styles.css 37,301 -> 99,881 B; home.js 6,030 -> 51,334; deferred JS
49,184 -> 119,964; index.html 28,417 -> 51,615. No test caps a byte. 39% of styles.css is comments (38,882 B), kept on
purpose (no build step, `motion.md:363`; "Comments say why").

**F3. The gate measures an uncompressed site (medium).** `tools/test_site.mjs:748-756` sends files raw; Pages gzips.
Same page, my gzip server: headline 1414-1487 ms, FCP 792-812, bytes 115 KB vs 296 KB raw. Visitors get ~0.85 s less
than the gate sees. Not a reason to loosen (see C4).

**F4. Site, unused bytes at first load (low).** Coverage, desktop: styles.css unused 63% (home), 84% (checks), 81%
(support); home.js unused 48% on home, 86% on checks and support (it loads on every page so a page change in one
document works, `transition.js`). Lighthouse: unused CSS 18-24 KiB, "unminified" 14 KiB CSS + 17 KiB JS. TBT on the slow
phone home 129-182 ms (home.js's 197-231 ms task); checks 0-11, support 0-5. CLS 0.0000 on every site run.

**F5. LCP is the end of the hero entrance (low, report only).** LCP element = the h1 (`hero-title`, `checks-title`, support
`P`) and its time = entrance at rest + ~20 ms: desktop 1612-1704 ms; slow phone, gzip, checks 2708-2724 and support
2956-2992 (CWV "good" is 2500). Lighthouse's simulated LCP says 1.7 s (it ignores the animation). The 1400 ms entrance is
John's (P17, M13, R13: ask John first), so no proposal; C1 takes 190-200 ms off it as a side effect.

| Lighthouse 12 (gzip server) | Score | FCP | LCP | TBT | CLS | Bytes |
|---|---|---|---|---|---|---|
| index mobile / desktop | 93 / 100 | 1.1 / 0.2 s | 1.7 / 0.8 s | 300 / 0 ms | 0 / 0 | 159 / 151 KiB |
| checks mobile / desktop | 99 / 100 | 1.1 / 0.3 s | 1.7 / 0.4 s | 70 / 0 ms | 0 / 0 | 104 KiB |
| support mobile / desktop | 100 / 100 | 1.1 / 0.2 s | 1.7 / 0.4 s | 50 / 0 ms | 0 / 0 | 107 KiB |

Render-blocking (all pages): styles.css (est. 450 ms mobile) and boot.js (300 ms, but it is fetched beside the CSS and
waits for it anyway). Fonts: one woff2, 27 KB, preloaded, `font-display: swap`, metric-matched fallback (B12, B13):
Lighthouse font-display passes. Images: all WebP/PNG under 32 KB (S25); Lighthouse's only image note is
pane-after-scan.webp (29 KB, 360 x 900, drawn as a 360 x 364 window: ~16 KB never seen), lazy and below the fold.

**F6. Pane: every open first says "Open this inside Excel." (high).** `frontend/taskpane.html:16-18`, `app.js:36-40`. The
message is the only thing painted until `Office.onReady` and the module graph (40 requests, 180 KB JS) finish: FCP
64-128 ms, main view 225-253 ms (1x) and 339-368 ms (4x). With office.js taking 700 ms to say ready (my assumption for a
real Excel; the fake answers at once) the pane shows only those words on bare paper for the whole wait:
`r3/shots/pane-open-150ms.png`, `pane-open-500ms.png`, then `pane-open-1400ms.png`. A user inside Excel is told to open
Excel (W1, N10 "nothing waits in silence", X33, X42). When the app replaces it, BODY moves 14 px (the `<p>`'s margin):
CLS 0.009 at 188-320 ms, every run. T20 says CLS 0 "on the site and pane", but no pane test reads layout-shift
(`grep layout-shift e2e frontend` finds nothing).

**F7. Pane font: no preload, no metric fallback (low).** `global.css:59` has the face; `taskpane.html` has no preload,
though B12 says "preloaded ... on site and pane". On localhost the woff2 lands at 98 ms, before the app shows, so it
costs nothing today; it matters once C2 paints the header first.

**F8. Pane speed is fine otherwise.** Ready 225-368 ms against M12's 2 s; one 72-76 ms long task at 4x. office.js is
parser-blocking from Microsoft's CDN (`taskpane.html:8`), which Office requires in the head: kept. components.css is 9%
used on the first screen, but over localhost bytes cost ~nothing: no proposal.

## C. Proposed changes (ranked by impact per line)

**C1. Preload motion.js on every page that runs it (site; 1 line x 8 pages).** After the stylesheet in each `<head>` of
index, checks, support, privacy, terms, cases, code-signing, thanks: `<link rel="preload" href="motion.js" as="script">`.
motion.js then arrives beside the CSS and runs the moment parsing ends, before home.js and the rest even land, so the
entrance's frames paint between them. Measured (`r3/v1`): gate headline **2303 -> 1583 ms median (max 2342 -> 1617)**,
at rest 3482 -> 2984; gzip 1435 -> 1068; checks/support headline 1854/1890 -> 1407/1421 raw, LCP gz 2716/2956 ->
2524/2792. Cost: FCP +120 ms raw, +52 ms gz (motion.js shares the line with the CSS); styles.css 883 -> 1027 ms; no
console warning; CLS 0. Tried and dropped: `fetchpriority="high"` on the script tag changes nothing (2263 ms).
Pane version: not needed; the pane's modules come from localhost (F8); its own first-paint fix is C2.
Rules: M12, M7 and M9 unchanged (nothing new is hidden; boot.js keeps its 1.4 s deadline), S1 (self only, CSP
untouched), P8 (no new look), R13 (the entrance itself unchanged). Test first: in `tools/test_site.mjs`, (a) static: every
page with `src="motion.js"` preloads it in `<head>` before `</head>`; (b) `BUDGET.shown` 2500 -> 2000 (red today at
2250-2650, green at ~1600, still 1.25x the new slowest). Mutant in `tools/mutations.json`: remove the preload line, killed
by (a). Height cost 0. Risk: low; tests that count `<link>`s: none found (`grep preload tools/test_site.mjs` is empty).

**C2. The pane opens on its own shape, never on "Open this inside Excel." (pane; ~10 lines).** `taskpane.html`: `#sideload-msg`
gets `hidden`, `#app-body` loses it, so the first paint is the navy header band and the start-up `#skeleton` (already
built, `global.css:150-152`). `app.js`: when `typeof Office === "undefined"` or `info.host !== Office.HostType.Excel`, hide
`#app-body` and show the message (today a non-Excel host just returns, `app.js:38`). To keep M49 (the brand flies in when
the pane opens), hold `header [data-enter]` at the start pose in CSS until `initMotion` runs (opacity 0, -40 px, as the
site's `data-ah` does, `boot.js:12-14`), with a 1.4 s fallback like boot.js so a stuck office.js never hides the name
(M7); none under reduced motion. Add `<link rel="preload" href="assets/plus-jakarta-sans.woff2" as="font"
type="font/woff2" crossorigin>` (B12, F7), so the header's "Arcas" never swaps under the eye. Site version: the site has
no host to wait for; its boot.js hold already never shows a wrong state, and C1 is its matching fix.
Rules: N10, X33, X42, W1, T20, M7, M49, N3 (no inline style, same-origin font). Test first: e2e (`e2e/launch.mjs` mode, fake
office with `onReady` delayed 700 ms, as `r3/paneflash.mjs`): at 150 ms `#skeleton` is visible and `#sideload-msg` is
not; layout-shift sum from navigation to ready is 0 (today 0.009); a host of `null` still shows "Open this inside
Excel." Mutants: show the message by default (killed by the 150 ms probe); drop the host check (killed by the null-host
case). Height cost 0 (the skeleton is the same height as the first screen it stands for). Risk: medium, the entrance
and `launch.mjs`'s "ready under 2 s" read the same elements; run `check.py --e2e`.

**C3. A byte budget, so speed is paid for like height (site; ~8 lines of test).** Static block in `tools/test_site.mjs`:
gzip -9 sizes at most styles.css 31 KB (today 29.3), the six deferred scripts together 46 KB (43.4), index.html 14.5 KB
(13.5), boot.js 1 KB (0.93). A design change that adds bytes raises a cap in the same commit and says why, as height
does (Rulebook step 8). Pane version: not needed for speed (localhost, F8); `e2e/launch.mjs`'s 2 s already guards it.
Rules: M12, P8, "Pay for height". Test: it is the test; loosen/tighten mutants in `tools/mutations.json` (cap +50%,
cap at today minus 1 KB). Height 0. Risk: none to other tests.

**C4. Optional, needs the Orchestrator's ruling: the gate's server gzips as Pages does (site; ~4 lines).** Same block,
`zlib.gzipSync` for html/css/js when the request accepts it, so the slow phone reads what visitors get (F3); in the same
commit `BUDGET.shown` re-derived the file's own way (twice the slowest of 5 gzip runs: after C1, 2 x 1126 = 2250). That
is looser than C1's 2000, so take C4 only with the budget kept at 2000 or lower. Without C1, or with a looser budget,
it is loosening: never (CLAUDE.md "never get a gate green by loosening it"). The test that proves it: the existing "the slow line is not slow"
check (`css > 300`) must still pass (gz CSS took 635-656 ms here).

## D. Rejected ideas

- Inline critical CSS: CSP `style-src 'self'` (site meta, pane N3); a hash per page is a CSP change for ~440 ms of
  Lighthouse-estimated, ~150 ms of measured gz gain.
- Minify, or strip comments: no build step (`motion.md:363`), "Comments say why" (CLAUDE.md). Gzip already takes most.
- Drop the font preload (measured another -100 ms, `r3/v2`): B12.
- `fetchpriority="high"` on the motion.js tag: measured no effect (gate 2263 vs 2250 ms).
- Split styles.css per page: one document across page changes (`transition.js`, S9), tests read tokens from styles.css,
  ~14 KB gz saved on checks/support (~70 ms): P8, Four rules #2.
- Shorten the hero entrance to fix LCP: R13, P17 (ask John).
- Crop pane-after-scan.webp to its 364 px window (~16 KB): lazy, off the critical path; 360 x 900 pinned by
  `tools/test_site.mjs:648-661` and S20.
- A spinnable 3D crest from img2threejs, anywhere: see the 3D verdict below (X64, M4, M5, M11, B18, P31, R25, M12).
- On the 404 page: `404.html` has no script by rule (CLAUDE.md L12).
- A one-time CSS `rotateY` "coin turn" of the download crest (0 KB, transform only): decoration (P31, R25); only if John
  asks for it by name.

## The 3D crest (tool #5): what it is, the trial, the verdict

**What it is.** img2threejs (Apache-2.0, npm 0.2.0, skill v2.0.1) is not a converter: the npm CLI only installs an agent
skill into Claude Code, Codex, OpenCode or Hermes. The skill makes the agent rebuild an object from a reference picture as a
TypeScript `THREE.Group` factory in many vision-checked passes (Python "forge" gates), for three@0.169, and its README asks for
"a userData.tick for a looping idle animation".

**Trial** (`ah193/research/3d/`, never the repo): the lowest-cost version any such output needs: three@0.169.0
vendored, the crest's own `mark-80.svg` paths extruded 3 units in flat site colours (`MeshBasicMaterial`, no light: B18),
CSP `script-src 'self'`. `?mode=demand` draws only when dragged; `?mode=spin` turns forever like the tool's idle tick.
Shots: `trial-demand-0.png`, `trial-spin-0.png`.

| | Bytes (gz, transferred) | Slow-phone ready | Idle main+raster task | Idle frames |
|---|---|---|---|---|
| Today's whole home page | 116-150 KB | headline 1435 ms gz | 0.2-0.5 ms/s | 0/s |
| 3D crest, draws on drag only | **192 KB** (three.module.min.js 687 KB raw / 170 KB gz) | 1938-1983 ms for the crest alone | 0.2-0.6 ms/s | 0/s |
| 3D crest, idle spin | 192 KB | same | **191 ms/s desktop, 327 ms/s at 4x CPU** | **60/s** |

**Verdict: reject.** It more than doubles the home page's weight (+192 KB gz, ~+1 s on slow 4G, against M12's 2.5 s); the
spin loops and draws while idle (M4, M5: 19% of a core on a desktop); turning it by hand is a drag, and the site has none
(M11, M41, `motion.md:410-411`); it is a canvas object of the kind X64 bans and a second WebGL context beside `field.js`;
its output is TypeScript, which needs a build step the site refuses (`motion.md:363`); and under B18 (flat, no shading)
it can only look like today's crest face-on or like a cardboard cut-out turned (the trial shows both), while shading it
would break B18. It shows no data (P31, P22); "spin the logo" is decoration the councils already turned down (R25).
Nothing in Arcas needs it: the crest stays the flat Spear and Banner (B16-B21).
