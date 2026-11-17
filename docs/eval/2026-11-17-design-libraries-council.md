# AH-183 / AH-184 council: what to build (Orchestrator, 2026-11-17)

Source: `2026-11-17-design-libraries-research.md`, section C. John: "take out the boring stuff, add the fun stuff,
keep the colours and look, do not over-engineer, do not overcomplicate, make no mistakes".
Rule for picking: the visitor DOES something or SEES their data come alive. Pure decoration is out.

## Build: website (AH-183), one Builder, worktree `.claude/worktrees/ah183`
1. **The fix lands in the cell** (research item 1: Motion Primitives text-roll, Kokonut marker). On a sample
   Accept (`site/home.js` Accept handler), the DOM swap stays instant (tests read it). An `aria-hidden` copy of the
   old mended cell's value lies over the new one: old rises a little and fades, new rises in, ~360 ms `--ease-out`,
   then a gold underline draws by `scaleX` from the left. Once per press, nothing under reduced motion.
   Boring removed: a dead click.
2. **The whole sheet at a glance** (item 2: Kokonut uptime strip, Bklit hover-dim). Next to "60 rows · 5 columns"
   in `.ws-top`, 60 static marks (static HTML, never built from data), one per sample row: wine for the 3 rows
   flagged "probably wrong", gold outline for the "worth a check" ones, paper tint for the rest. `aria-hidden`.
   Accept makes its mark plain (opacity crossfade). If the filters already dim rows by a class, the marks follow the
   same rule with the fewest lines; if that needs new machinery, skip the dimming.
   Boring removed: "what is in the ⋯ rows?": the visitor sees 7 of 60 and the rest fine.
3. **The Scanning tab reads the strip** (item 3: Anime.js stagger, Watermelon steps). While the Scanning tab's
   existing meter fills, the same strip's marks light in order (opacity, a fixed step), each flagged one taking
   its colour as the meter reaches it; then the tab turns to the findings as today. Once per choosing (AH-147:
   nothing loops). Reduced motion: shown at once. Use the ONE strip of item 2; do not copy it.
   Boring removed: the empty Scanning tab.
4. **A picture for a jump** (item 4: Bklit sparkline + reference area + clip reveal). In the detail boxes of the
   "jumped sharply" rows (5, 21, 41, 57), a small inline SVG of the sample's Total by row (the same 60 values the
   sample shows), that row's point a wine dot, line navy. Revealed once as the box opens by a paper mask sliding
   away (`scaleX`, `--ease-out`), never `stroke-dashoffset`. The points are written in the HTML and a test reads them
   back against the sample generator / table (`test_site_sample.py`). Must stay inside the popover on a phone and
   at 1280. Keep it small (about 240 x 56). If the 4 copies make the HTML heavy, one `<symbol>` + `<use>` with a
   per-box dot is fine.
   Boring removed: four "Total jumped sharply" sentences with nothing to look at; and it shows the jump may be
   real (AH-167 humility).

Not built (website): step numbers lighting on scroll, scroll progress line, 201-square grid, FLIP filter (all
decoration or page height; see the research file, section D, for the rest).

## Build: pane (AH-184), one Builder, worktree `.claude/worktrees/ah184`
5. **A finish line you can see** (item 5: Watermelon checklist progress, Bklit bar reveal). A 2 px gold hairline
   across the top of the foot bar (`#status`), `scaleX(done/total)` from the left, ~300 ms `--ease-out` after each
   Accept, Dismiss or Undo, matching `scan.doneOf`'s words. Height 0 (AH-149/AH-165: nothing moves). Hidden before
   the first decision. Windows High Contrast keeps it drawn. Reduced motion: it jumps to its width.
7. **A row turns "Fixed" in front of you** (item 7: crossfade). Back to the list after a decision: the decided
   row's tag and swatch cross-fade to their done look (opacity, ~250 ms), once. Focus already lands on that row.

Not built (pane): item 6 (a second animation for the same Accept).

## Rules for both Builders (CLAUDE.md wins)
- Test first: a test that fails today, then the change. Name tests as behaviour in plain words.
- Only transform/opacity animate; `--ease-out`/`--ease-in-out` only; no overshoot; finite; nothing under reduced
  motion; nothing hidden without JS (website rule 4); AA as rendered; no text under 12 px; plain words
  (`test_plain_words.py`); grep a new class name across `site/` / `frontend/` first.
- Height: home page within today's budgets (1280: 4,651 px now, cap 4,680; 390: 8,385 now, cap 8,397). Pane
  first-screen heights unchanged.
- Update CLAUDE.md layer 11 (pane) or 12 (website) and `docs/design/motion.md` (website) in the same commit.
- Website: `tools/test_site.mjs` (static and `--browser`), `test_site_sample.py`. Pane: `frontend/selfcheck.js`,
  `e2e/all.sh`. Then the full gate:
  `PYTHONPATH=$PWD/backend flock /tmp/ah-browser.lock .venv/bin/python tools/check.py --keep-going --e2e`
  (browser runs take the lock so two never run at once). Mutants: a new guard adds loosen/tighten mutants to
  `tools/mutations.json`; a pure animation is not a guard.
- Commit on your worktree branch as soon as green; write the gate output to a log file.
