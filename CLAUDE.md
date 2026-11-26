# Arcas: map for whoever changes this code next

Excel add-in: a task pane (`frontend/`) talks to a local HTTPS engine (`backend/anomaly_hunter/`, 127.0.0.1:5055) that
flags wrong cells and suggests fixes. Optional AI help goes to Google directly or through the invite relay (`relay/`).

## Four rules for every change (John, 2026-11-06)
1. Think before coding: write down your assumptions. If something is unclear, stop and ask.
2. Simplest code first: nothing nobody asked for. If 200 lines could be 50, write the 50.
3. Surgical changes: touch only what the ticket needs. Every changed line traces back to it.
4. Goal-driven: turn "fix the bug" into "write a test that shows it, then make it pass".

Design work (the pane or the website) starts by reading the vault's `90-System/Design-Rulebook.md` whole (John,
2026-11-17, GEN-60).

## Work comes from the agent dashboard
This repo's tickets are the `AH-` rows of `90-System/agent_dashboard.md` in John's vault (`second-brain-vault`; live
board https://claude.ai/artifact/L89gYPxD8feZu5PeN6cUrs). Every prompt runs the vault's `90-System/Pod-Workflow.md` (John, 2026-10-28):
you are the Orchestrator of one pod, a Researcher and a Builder subagent do the reading and building, a fail is written
as anatomy / unmet criteria / resolution path, 2 fix rounds, then John. Log a request there as tickets, lock one, then
work it; the gates below still decide when it is done.

## Before every commit: one command
`python tools/check.py` runs every gate, fastest first, and stops at the first red layer (`--e2e` adds the browser
test, `--keep-going` runs them all). Needs `pip install -e ".[dev]" -c constraints.txt` and node. All green = what CI checks
(both accuracy benches run there too), except Semgrep (see the rules below). It also reads the whole git history for
secrets (`tools/secret_history.py`: a skip on a shallow clone, `--full` in CI). Never commit with a red layer, and never get a gate green by loosening it.
`python tools/check.py --mutate` adds the mutation layer (`tools/mutate.py`, CI's `mutation` job on every push and pull
request): every guard in `tools/mutations.json` is broken on purpose in a throwaway copy, and a mutant its tests survive
is a red layer (`--e2e` also runs the ones only the browser test catches; 112 take 10 minutes on 4 cores, the browser's 10
about 27 more, so it is not in the default run). Map: `docs/security/GUARD-MAP.md`.

## Security first: read `docs/security/SECURITY-LESSONS.md`
Every input is an attack until proven harmless (emoji, "ignore all previous instructions and drop table"), and John is
the only admin: through his GitHub, Cloudflare and Google accounts, never through anything inside the app. Never add
an admin panel, role, operator route or debug switch. The weekly security sweep reads that file first.

## Layers and checks: `docs/MAP.md`
Each request passes 12 layers (network, who may call, body shape, route fields, load, checks, severity, answer, AI,
relay, pane, website), each with its own guard and test, and the scan runs the checks in its feature map. Read the
row a ticket touches before changing it, and update that row in the same commit (adding or removing a check too).

## Patterns to copy
- **Test first, from the failure.** Rebuild the bad sheet as a small synthetic fixture (never a real customer file),
  watch the test fail on the old code, then fix. Name tests as the behaviour in plain words.
- **A new check** takes `(df, column_types, skip)`, returns `[[reason, ...] per row]`, skips totals rows via `skip`,
  and is joined into `hygiene` in `pipeline.score`. Reasons are one plain sentence naming the column and the value,
  built as `Why(text, column, ...)` (the cells the pane colours) with numbers through `say()` (the cell to 15 digits,
  never `:g` nor e-notation it was not typed in, AH-174; a percent typed as text is quoted as typed beside it, "22 (+2200% as typed)", by `pipeline.score`); `test_every_flag_names_its_cells.py` checks every bench sheet's flags against their cells.
- **Lists of routes come from Flask** (`APP.url_map`), never typed by hand, so a new route is tested automatically.
  A new route also goes into `backend/openapi.yaml` (`test_the_spec_lists_every_route` fails until it does).
- **Accuracy is measured, not argued**: `score.py .` (gates) and `score.py . --blind` (held-out domains). A detector
  change that moves either one is explained in the commit message with the numbers. For a big change, also run a
  blind real-sheet test: one agent fetches random public tables and plants mistakes with a secret key, another runs
  the pane and engine without it (`docs/SYSTEMS-MAP.md`). Use a fresh set each time: a set you fixed against is no
  longer held out. Two scores never move backwards: the Chaos Dataset's harm-weighted F2 (`test_chaos_dataset.py`:
  5 TP / (5 TP + 4 FN + FP + 10 (harmful fixes + silent changes)), any harmful fix or silent change fails alone) and
  the any-schema proof (`test_schema_agnostic.py`: generated 8- and 40-column sheets with meaningless headers, same
  flags under other headers, a column's limits scale with it). Nor does any group's: `backend/bench/groups.py` (AH-223)
  grades recall and false alarms per group (a big group of 400 rows, a small one of 40 at another scale, slips planted in
  both) and fails when the small group is caught 10 points less often or falsely flagged 1 point more. A check that reads a header word says so in `docs/MAP.md`.
- **An AI prompt, its context or the model** changes only with `backend/bench/ai_eval.py` numbers (your own key,
  never the relay; paired wins vs losses on dev and held-out) in the commit message. No eval run, no change. An arm's
  request that is byte for byte one already answered takes that answer (AH-153: the same question asked twice only
  measured noise); `--dry-run` prints each arm's requests and reuses. Ask AI's
  real-world notes (`ai/bias_context.py`) are built but off: arm `bias_context`; `on=True` in `client.py` once it wins.
- **Before adding a system-design piece** (a cache, queue, lock, retry, rate limit), read `docs/SYSTEMS-MAP.md`: what
  exists, where, and which measurement would justify more.
- **Comments say why** (the incident or measurement), not what.
- **Every guard is tested both ways** (a test that keeps the wrong out, one that lets the right in, at its very limit)
  and held by a mutant in `tools/mutations.json`: a new or changed guard adds its loosen and tighten mutants in the same
  commit, and `tools/mutate.py --only ID` shows each one killed (AH-155: 15 of 110 survived tests that were all green).

## Rules learned the hard way (each one is now a test)
- Werkzeug's `make_server` is single-threaded by default: start test servers only with `live_engine()`.
- `request.get_json(silent=True)` doesn't catch `RecursionError`: the `_JSON` provider turns it into a 400.
- Float maths isn't exact (`2.99 - 1.99 != 1`): a spread below 1e-9 of the values is noise (`detectors.spread`).
- Least squares is bent by one x10 typo: exact pair checks (`pairs`) back up `sums`.
- A limit must not cut through a run of honest values in a signed column (`limits._end_of_run`); in a positive
  column, 0 and "15x below typical" stay hard bounds.
- A new detection changes what the pane shows (a reason, a fix card, what strength 0 lists): after a detector change
  run `python tools/check.py --e2e`, not just pytest. CI's Windows `new-user` job caught one that pytest couldn't.
- A real slip stands alone; a long tail is crowded (census hours 1-99, survey weights): a value past the weird limit
  votes only when few other values lie between it and halfway back to the median, or as far again beyond it (the lowest of 24 honest Friday peaks, AH-150)
  (`limits_detector.in_tail`), and a
  50%+ zero column is judged on its amounts (`limits._limits`). `test_wild_census.py`.
- A smooth line is not a series of jumps, and a cap is not a cure: the series check called 49-64% of real CO2 and
  jobs-report months unusual, because on a smooth line the local median is the value itself (gaps ~0, every bend
  17-30x past the line) and the first and last months were read against a one-sided window. AH-31 try 1 capped the
  votes to the most extreme 0.5-2% of rows: the strongest were those end artifacts, and 120 real jumps in 1,200 months
  were cut to 9 (Council A). Fix the misreading instead (`detectors.STEP`, `_centred_median`), and measure recall
  against main at every level on many real jumps, not one (`test_series_jumps.py`).
- A knob must reach a check that can move: strength only lowered k, and the long-tail crowd (a count, the same at
  every level) excused every value k let in, so 5 and 10 flagged the same sure mistakes on every sheet John would
  scan (AH-14). Levels 7+ now list a breach few other values share, and say how many: a crowd that grew with the level
  listed honest bulk orders "with few values near it" while 32 sat near them, and honest people aged 91-98 for their
  age (AH-14 review). Votes keep their crowd. Measure each level, not only 5 (`test_strength.py`).
- The slider's hints are measured: each level says in its own words what it does and what it did on the bench
  (`MEASURED` in `frontend/constants/index.js`), and `test_strength_promise.py` re-scans the bench at every level and
  fails when a number or a "the same mistakes as at 5" stops being true. John read 5 and 10 as the same list (AH-15);
  2, 4, 6, 8 and 10 showed the level below's words, so 6 opened "Recommended." (AH-20). A detector change that moves a
  number updates `MEASURED` in the same commit.
- A contraction keeps the word's first and last letters (Std, Mgmt): "Iran" is not one of "Ireland" (`_short_for`).
- A misspelling rule is judged by its honest-twin rate on the 10,000 commonest words, not by examples: one wrong letter
  has a twin for 61% of 5-letter words (safe only behind the rare-next-to-common gate), a dropped inner letter 2-6%, so
  it is allowed; at 4 letters only a swap (5%) or a dropped vowel (7%), never a wrong letter (89%: Iran/Iraq). Blind
  round 22's planted misspellings went from 3 to 9 of 9 (`_misspelt`, AH-23). People's names are worse: a dropped inner
  letter has a twin for 21% of the 10,000 commonest surnames and 37% of first names, a doubled letter 4% and 13%, so a
  person-name column gets no spelling guess at all (AH-24). But a header is read narrowly: plain "Name" silenced a
  product list's "Staplre", and all 3 plain "name" columns in blind round 22's 59 real tables were cities, car models
  and airports, so "Name" counts only beside a person's age, sex or birth date (AH-24 review). A role can be a company's:
  "Customer" of Microsoft and Contoso was silenced too, but a list of common US names to tell them apart left Thomson
  alone in a US roster and called Adeolu a misspelling of Adeola in a Nigerian one (0 of 200 Nigerian rosters read as
  people): a person-name rule never depends on where a name comes from (AH-26 review).
- The installer starts Excel by its App Paths path, never "open this .xlsx": with no Excel, Windows' "Pick an app"
  held the install (`app.excel_exe`, `test_the_installer_finds_desktop_excel_or_says_none`).
- A cliff on a measured shape is a coin flip: "upper spread > 2x lower" sits right at a log-normal's average, so 22 of
  60 telecom sheets got even-sided limits and an honest heavy user was called wrong. A column is log-shaped when it is
  more even on the log scale (`limits._log_shaped`). The pane must accept every limit the engine votes on: it checked
  only the weird one, so a lone x10 flagged past the usual limit got "may be real" and no fix (`fix.recommendFix`).
- A false-alarm budget lets false alarms in: "<= 1% of clean rows" passed an autoencoder adding 26 Medium ones. The
  bench gate now fails on any Medium+ false alarm not in `score.KNOWN_FA` (sheet:row); remove an entry once it's fixed.
- The 2-of-500 failure: thresholds tuned to avoid false alarms hid real defects. Any threshold change must keep
  `test_blindspots.py` (279/279 rows) and both bench gates green.
- A "likely" fix is a card the user may accept, so it is judged on real values, not only planted ones: 10 of 203 such
  guesses on 30 + 29 real tables and the benches were real values (Seattle's -1.1 highs and a sea level's first years
  flipped, DC's 4% made 40%, California's three fruit columns divided by 1000). A sign flip must stand alone, one step in 2+ cells is a real row,
  and what the numbers cannot prove is never "likely": a value too small is a "(maybe ...)" guess card, and a tenth among
  small whole numbers (Floors 20 among 1-5 is Q3 20 for 2 to the numbers) is flagged with no fix, as John ruled for the
  1-5 scale rule (AH-21, `test_likely_guesses.py`).
- A number column's "NA" is R's word for no value, and many blanks spread through a column are the data: blind round
  23 had ~3,960 "Text in a number column" rows from R's NA and 1,401 one-per-row blanks (Netflix cast, Titanic Age).
  NA/NaN/null/None in a number or date column are read as missing (`load.NO_VALUE`); an NA the column writes 5+ times,
  and 20+ blanks (1%+ of the rows) in every fifth of the sheet (since AH-142: 0.5%, 4 of the 5 fifths), are one note (`pipeline.blanks`, `MANY`, `NO_VALUE_SHARE`); a few blanks, or a block, stay
  one flag each, as do 20 deletions spread through a 20,000-row sheet (AH-28 review). An empty cell where the export writes NA is judged apart, since R never leaves a cell empty: that kept
  the NFL plant. False Medium+ on the round's 30 tables: 5,022 -> 710 at level 5, every plant still found
  (AH-27, AH-28, `test_missing_values.py`).
- Never invent a value. A median card filled 17,000 cells that were blank on purpose (a long-format sheet) and wrote
  39 over California's 169 delegates. A card writes only what is known: a typo pattern, the row's own arithmetic, the
  usual spelling (`fix.recommendFix`); 2+ cells off by the same step are a real row, not 2 typos.
- Synthetic benches only hold what their author imagined: 40 random real tables found long-format layouts, code
  columns ("R+51.5"), a "-" read as 0 and false duplicates the benches never had (2026-10-16).
- Checks over pairs of columns grow with the width (400 crafted text columns: 30 s; 160 number columns: 16 s). Cap
  them in sheet order, never with a clock inside a scan: the same sheet must give the same answer on any PC.
  `test_a_crafted_wide_sheet_cannot_make_the_column_pair_checks_run_for_minutes`.
- Real exports break what synthetic sheets never do: ISO timestamps ending in Z or +02:00 (with a blank) broke date
  parsing, and a chi-square on an all-zero column broke the fairness report. Both made every scan of the sheet a 500
  (`load._dates`, `fairness.report`; 40 random real tables, 2026-10-16). A new blind round reads every table, not only
  the planted ones.
- A highlight is a claim about a cell: the pane coloured whole rows, so a reason about one cell lit up every cell
  beside it, and reasons quoted cells through `:g` (1234567.89 said as 1.23457e+06, 12345.67 as 12345.7), while
  pandas' parser read -0.013338153250515461 as -0.0133381532505154. Each reason now carries its columns, the pane
  colours those cells only, and a test reads every bench flag's quoted value back from its cell (AH-40).
- A report fits the sheet only when it knows who the rows are: a blind sweep of 39 public tables found "a real gap" in
  Texas cities' missing house sales, a town's share of old houses read as people's ages, a cat's sex as a person's, race
  1/2/3 banded as "1-2" and "3 and over", Lunch/Dinner and House/Senate measured as outcomes, "Femlae" named as a group
  of people, and female, nonwhite, maritl, nativeBorn missed. Who the sheet is about is read from all its headers and
  labels (`fairness._people`, AH-39, `test_fairness_fits.py`).
- An amount compared across groups is only as fair as the amount: police killings' county_bucket is the county's
  income quintile, so "bucket 1: median income 29,707 vs 50,280" restated the cut, and a loan's term in months is
  called Loan_Amount_Term. Amounts are named ones with 10+ values, never across a bucket or a lookup of the group, and
  100 pure-noise sheets must read even in 95 (`fairness._amounts`, AH-49).
- Office caches ribbon icons per URL and the manifest per `<Version>`: the v0.1.71 logo kept the old file names and
  Version, so an upgraded ribbon would keep the old icon. A new logo gets new file names (now `assets/crest4-*.png` since AH-203, drawn by
  `docs/design/logo/draw.py`) and a `<Version>` bump; never clear the
  Wef cache in install (it is where Excel remembers the Add, `install.bat`).
- An icon URL is never retired: Excel kept drawing the 1.0.5.0 manifest it had cached ("Anomaly Hunter", `mark-*.png`)
  on 1.0.8.0 installs, and the deleted files showed as Office's grey placeholder (AH-154). Every icon name a shipped
  manifest gave answers with today's crest (`server.OLD_ICONS`; a new logo changes `CREST` and adds the old name, as
  AH-203 added `crest2`):
  `test_every_ribbon_icon_an_old_cached_manifest_names_is_still_our_crest`.
- One package for one function is a download cost: pyod (for ECOD) brought numba, llvmlite, matplotlib and
  scikit-learn, half of a 146 MB exe (2026-10-19). Check what a new dependency pulls in (`uv pip tree --invert`).
- The Privacy page once said "nothing is sent to any other third party" and "Remove key deletes every local file":
  both false (2026-10-19 audit, 24 items). `frontend/privacy.html`, `PRIVACY.md` and `site/privacy.html` are twins of the code: a change to
  what is sent, stored or installed updates all three (`test_both_privacy_pages_name_every_place_data_goes_and_every_file_the_app_keeps`),
  and `test_privacy_promises.py` holds them to the relay's caps in `relay/wrangler.toml`, the pane's localStorage keys and Forget.
- Pin every package, indirect ones too: an unpinned scikit-learn 1.9.1 broke every Windows install (2026-10-11).
  `constraints.txt` + `tools/pinned.py` (CI and the exe job); regenerate with the command in `tools/pinned.py`.
- pip-audit reads every package installed, the app's or not, never `constraints.txt`: certifi and pillow, pinned past
  their advisories, still failed the local gate until they were installed (2026-10-20). After a pin change, install
  the moved pins (`pip install -e ".[dev]" -c constraints.txt`, and `pip install -c constraints.txt <package>` for a
  pin outside `dev`), then run `tools/check.py`. The gate also audits every pin in `constraints.txt` (`-r`): setuptools,
  the build tool, is never installed for pip-audit to see, and 84.0.0 carried an advisory while the installed audit was
  green (Dependabot found it, AH-96). That audit runs `--strict`: without it a mistyped or made-up pin only printed
  "Dependency not found on PyPI" and passed (AH-105). Declare what the app imports (pydantic and werkzeug came only through
  anthropic and flask) and drop what nothing imports (Pillow, AH-87):
  `test_every_package_the_app_imports_is_declared_and_every_declared_one_is_used`.
- Semgrep runs only in CI (`security.yml`): its rule packs come from semgrep.dev, which a cloud session cannot reach.
  It went red three times on 2026-10-20 after every local gate was green: a RegExp built from a name, `Object.assign`
  of parsed JSON, urllib on a URL from a variable. Where it cannot run, grep the diff for those before pushing.
- Test a file the way its reader reads it. Power BI's Text/CSV import ends a record at every line break, even inside
  quotes (`QuoteStyle.None`): one cell with a line break shifted every row below it, and a 309-digit cell made the old
  writer give up silently, leaving the previous sheet's copy for Power BI (2026-10-20). `powerbi.py` writes a break as
  ↵, removes both files when a write fails, and `test_powerbi.py` parses them back record by record.
- One stray spelling switches a check off: a single "no " among 480 Yes/No answers made three labels, and every
  outcome fairness test vanished with the real gap in it (South 34% vs East 8%). Labels are read the way the spelling
  check reads them (`fairness._labels`, `test_delinquency.py`).
- Not significant is not even: "even across groups (22% to 50%, within normal variation)" was said of 80 people, the
  census sentence about who earns over 50K was put under a loan's denials and under a Day/Night shift, and 40
  countries' gap was stated against whichever one landed lowest (AH-17 bias hunt, 2026-10-22). The first fix swung the
  other way: an outcome allowlist lost Approved/Declined, and pure noise read "not enough rows to tell" in 13 of 20 sheets
  (AH-18 review). The report says only what its numbers show (`fairness.report`, `test_fairness_words.py`).
- An animation eased per frame takes as long as the machine is slow: the website's cursor light moved 8% a frame, so it
  needed ~87 frames to settle, 1.9 s on a loaded box and 4 s with the CPU slowed 8x, and the 2.5 s idle check failed 1
  run in 3 (AH-22). Ease by the clock (`site/home.js`); `tools/test_site.mjs` replays it at 20 frames a second.
- A cache that outlives a test run tests nothing: e2e/all.sh kept the AI answer cache, so a second run never reached
  the stub. It starts fresh now.
- A DOM0 key handler returning false cancels the key: `onkeydown = (e) => e.key === "Enter" && e.ctrlKey && askFix()`
  swallowed every keystroke in the Ask AI box, and the e2e never saw it because `page.fill` sets the value without a
  key event (2026-10-20). Test typing with the real keyboard (`page.keyboard.type`); `frontend/selfcheck.js` refuses
  DOM0 key/pointer handlers and any `on... = () => a && b()`.
- What the user decided must outlive the pane: Dismissed and accepted fixes lived only in its memory, so a reload or a
  re-scan brought a dismissed row back flagged and an accepted fix vanished from the list and from Power BI
  (2026-10-20). Each decision is kept in the workbook's settings under a code of the row's values plus its copy number
  (`features/decisions.js`; a sort keeps it, an edit makes a new row), sent with `/scan` for Power BI's Status. The
  e2e fake workbook keeps its sheets and saved settings across a page reload, so "reload the pane" is testable.
- A sheet is damaged before any check runs: opening a CSV makes "02134" the number 2134 and reads "03/04/2024" in the
  PC's order, and the loader did the same (`pd.to_numeric`, one day-first switch per column). A check can only see a
  cell as typed: `docs/airlock/` imports a file as raw text in Power Query and writes an Audit column (never over the
  source), and an Excel formula that tests a date never uses `--text` or DATEVALUE, which make the very guess it is
  checking (chaos audit, 2026-10-30, `test_chaos_dataset.py`).
- The environment is input too: Flask reads FLASK_DEBUG when it builds the app and again in `run()`, so one variable
  on a user's PC turned on Werkzeug's debugger, and a moving tag (`zaproxy:stable`) or a bare `npx wrangler` runs
  whatever was published last. The engine sets every switch itself, CI's images are pinned by digest and the deploy
  tool by version, and a secret deleted in a later commit is still found (`tools/secret_history.py`, AH-87).
- A contrast ratio is measured in the browser, not worked out from tokens: the comments said navy 16.6:1 (it is 15.9),
  and an opacity of .6 on a done row took its grey to 2.7:1 (`e2e/contrast.mjs`). A claim on the website is a test:
  "the engine's own result" had drifted twice (a dropped sentence, 19 for 20) before `test_site_sample.py` held it.
  On a box with no GPU, `test_site.mjs --browser` asks for `--enable-unsafe-swiftshader`: Chromium 141 warns on its own
  software fallback, and the console check fails on that warning (AH-87).
  A class name on a new site element is grepped across `site/` first: the skip link's `.skip` was already the
  sample's separator rows' class and pulled all five out of the table (AH-87 fix round 1; `tools/test_site.mjs` checks
  those rows stay in place in every filter state).
- Line endings are input too: `.gitattributes` named only `*.bat`, so a Windows checkout (core.autocrlf) wrote every
  other file CRLF and `test_site.mjs` found none of contact.yml's field ids. Every text file checks out LF, install.bat
  CRLF, the Chaos Dataset as its bytes (AH-186, `test_line_endings.py`).
