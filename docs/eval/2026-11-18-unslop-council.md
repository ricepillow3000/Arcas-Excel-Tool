# AH-193 council: the unslop pass, what to build (Orchestrator, 2026-11-18)

Inputs:
- research/R1-impeccable-guidelines.md (impeccable + web-design-guidelines)
- research/R2-high-end-references.md (awesome-design-md + the high-end skills)
- research/R3-speed-and-3d.md (Chrome DevTools speed checks + img2threejs)

Every builder first reads the vault's 90-System/Design-Rulebook.md WHOLE (GEN-60 rule), then the repo CLAUDE.md L11/L12 and
docs/design/motion.md. Base: origin/main b554705 (it includes #121, #126, #127, #123: re-measure on it; line numbers in the
reports may have moved). Every change is built test-first (show the red run), on BOTH surfaces where it applies.

## Website builder (worktree .claude/worktrees/ah193s), items S1-S8
- S1 The paper fog over the navy checks band: `.band-dark + .section { overflow-y: clip; }` (R1 P1 = R2 #2). Test: the
  pixels 3 px above the band's bottom edge read navy at 1280 and 1440, height unchanged.
- S2 Hero buttons at 761 px and wider: Download alone on its row, "See a sample scan" and "Contact John" side by side
  (R1 #3). Height 0; phone untouched. Test: no button alone on a row except Download, at 1280 and 1440.
- S3 checks.html shows a check on its first screen: the table moves up about 112 px by its two CSS rules (R1 #4). Test:
  the first check row's top is within the first screen at 1440x900 (and the best it can at 1280x800).
- S4 Text selection in the brand: `::selection` navy text on a gold-hi or paper tint that passes AA as rendered (R1 #5).
  The same rule as the pane's (P-side item P1), one token pair. Test: contrast of the selection as rendered >= 4.5.
- S5 Hairlines on paper in gold: the decorative `.rule` lines (R2 #3); frames and table borders stay navy (B3, P28).
- S6 Weights: the sample cells' 500 becomes 400 so the bold flagged cells stand out (R2 #5); update the sample filter
  test lines R2 named (test_site.mjs ~310 and ~353) together.
- S7 Speed: `<link rel="preload" href="motion.js" as="script">` on the pages that run motion.js (R3 C1). Tests first: a
  static "every page that loads motion.js preloads it", and the slow-phone headline budget TIGHTENED from 2500 to 2000 ms
  (tightening is allowed; never loosen). Plus R3 C3: a gzip byte cap per page in tools/test_site.mjs at today's bytes
  + a small margin, so added bytes must be paid for.
- S8 Phone hero: hide the hero's `.note` below 761 px (Windows was said three times), saving about 45 px (R1 #8).
Update CLAUDE.md L12 and docs/design/motion.md in the same commit. Add near the top of CLAUDE.md (under "Four rules"):
"Design work (the pane or the website) starts by reading the vault's `90-System/Design-Rulebook.md` whole (John,
2026-11-17, GEN-60)." Home heights must stay within 4,680 (1280) and 8,397 (390).

## Pane builder (worktree .claude/worktrees/ah193p), items P1-P6
- P1 `::selection` that stays readable on the navy header and foot (today about 1.1:1), the same token pair as S4.
- P2 The progress bar grows by `transform: scaleX` instead of `width`; buttons' hover fill is a mask/`scaleX` layer like
  the site's instead of a `background-color` crossfade (R1 #6, M1, M44). Rewrite the one hover test R1 named to read the
  fill layer (never drop an assertion).
- P3 `#empty-state p:first-child` becomes `#empty-state > p:first-child` so "Before you scan"'s first line is not set as a
  heading (R1 #7).
- P4 The pane's `h2::before` hairline in gold, as S5 (R2 #3).
- P5 One link and one button style with the site: link underline gold (not wine), the main button without the extra
  letter-spacing the site's buttons lack (R2 #6).
- P6 Open on the pane's header and its existing start-up skeleton instead of "Open this inside Excel." on blank paper,
  and preload the pane's font (R3 C2: a 14 px jump, CLS 0.009, and B12 says the font is preloaded). Test: CLS 0 on
  open in e2e, and the font preload present (selfcheck).
Update CLAUDE.md L11 in the same commit. Pane first-screen heights must not grow.

## Not built
- img2threejs: it is a skill that writes three.js code, not a converter; a trial spinning crest adds 192 KB gzipped (more
  than the whole home page) and draws 60 frames a second while idle (M4, M5, M11, X64, B18). Rejected everywhere.
- The 01-04 install steps restyle (R2 #4): John's earlier design; left for him.
- R3 C4 (gzip test server): it would loosen the gate's view; John's call.
- Renaming the merged code's AH-183/184 labels to the dashboard's AH-194/195: churn for no user gain; the vault rows map them.
