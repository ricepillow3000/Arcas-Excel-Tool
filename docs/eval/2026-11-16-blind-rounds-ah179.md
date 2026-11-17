# Three blind rounds on 126 public tables: accuracy and fairness (AH-179, 2026-11-13 to 2026-11-16)

John asked (2026-11-16) for the scan and the fairness report to be "at its utmost reliable and true, whatever the
sheet is about", proven on many subjects. Three blind rounds, each on 42 fresh public tables from TidyTuesday (CSV, no
table reused, the weeks the project tuned on before left out): a planter agent fetched the tables and planted mistakes
and fairness gaps with a secret key; a scanner agent ran the engine on them, every cell sent as text the way the pane
sends it, never seeing the key; a judge script scored the answers against the key. Each round: 28 tables with 3 to 8
planted mistakes, 14 clean tables, and 10 to 13 tables about people, 4 to 6 of them with a planted gap.

| Round | Tables | Subjects | Weeks | Planted mistakes | Planted gaps |
|---|---|---|---|---|---|
| 1 | 42 | 15 | 2025-2026 (4 from 2024) | 135 | 4 |
| 2 | 42 | 15 | 2021-2023 | 138 | 6 |
| 3 | 42 | 21 | 2018-2020, 2024 (2 tables 2021) | 142 | 6 |

A plant counts as caught when its row is listed (High, Medium or Low) with a reason naming the planted cell's column
(a duplicate: its row listed as a duplicate). A false alarm is a Medium or High row with no plant on it. Strength 5 (the
pane's default). Every table answered HTTP 200 in every run.

## Accuracy

| Round | First blind scan | After that round's fixes | Medium+ rows with no plant, first | After |
|---|---|---|---|---|
| 1 | 111 of 135 (82%) | 116 (86%) | 506 | 233 |
| 2 | 106 of 138 (77%) | 117 (85%) | 539 | 320 |
| 3 | 124 of 142 (87%) | 121 (85%) | 861 | 798 |

Round 3 is the held-out round: no rule was tuned on it except the two fixes below, which narrow or settle a rule rounds
2-3 showed was wrong, and are said here so the number is read as what it is.

- Round 3 lost 3 catches on the final code: an age/height swap, two "minutes late" counts swapped and one tuition above
  its total were caught only by the first `order` check, which read any two neighbouring number columns in order on
  99.9% of rows as a rule ("b_draw is at most b_wins", "lng is at most lat"): about 60 false Medium rows. The fix judges
  only headers that name an order (min/max, low/high, 10th/90th...), and the 3 lucky catches went with it.
- What round 3's false alarms are, checked by hand on the four biggest tables: 137 real exact copies in the measles
  table, 52 restaurant inspections dated 1900-01-01 (a stand-in for "not inspected"), "Bottom Two" beside "Bottom two",
  9 Broadway rows whose average ticket price is above the top price. Most are the source's own problems.

Caught by kind on the final code (rounds 1 + 2 + 3, 354 of 415 in all, 85%):

| Kind | Caught | Kind | Caught |
|---|---|---|---|
| blank in a filled column | 25 of 25 | sign flip | 27 of 27 |
| date in another form | 27 of 27 | text in a number column | 16 of 16 |
| duplicate row | 66 of 69 | total that no longer adds up | 14 of 15 |
| far date (2084, 1084) | 30 of 36 | lost leading zero | 6 of 8 |
| misspelled label | 66 of 75 | x100, ÷100 | 18 of 21 |
| two cells swapped | 13 of 18 | x10 | 46 of 78 |

What is honestly not caught: an x10 or a ÷100 that lands inside the column's own honest range (a 200 kg Pokémon with 77
heavier, a population 10x that thousands of rows reach), an age of 15 swapped with a rank of 50, a copy among 4,219
honest identical hotel bookings. On the column alone these look exactly like real values; "a long tail is crowded"
(CLAUDE.md) is why the engine keeps quiet, and loosening it was measured before to flood real sheets with false alarms.

## Fairness

| Round | Planted gaps the rules call a fairness measure | Found |
|---|---|---|
| 1 | 3 (literary prizes, coffee survey, near-death study) | 2 first, 3 after AH-172 |
| 2 | 4 (Erasmus, "Alone", centenarians, salaries) | 3 first, 4 after AH-176 |
| 3 | 4 (astronauts, powerlifting, salaries, climbers) | 3 |

Not counted, by the rules and said so: a race time (T13, T39 of round 2: no amount word), which corner won a bout
(Red/Blue is a side), and two tables whose rows are groups with an "All Races" total row (a table of counts, not people).
Round 3's miss: the climbers' success column has "Pending" on 198 of 19,791 rows, exactly 1.0%: the line AH-176's fix
round set (extra labels under 1% together are left out; at 1% and 20+ rows they are a group of their own).

Misreadings found and fixed: an answer's "NA" was a third label, so a real gap went unsaid (AH-172); "57% missing year of
death" was said of artists still alive (AH-176); an age band "flagged more" for its own impossible ages (AH-176); a
National/Transnational meeting type was an outcome (AH-176).

## Every fix, its ticket and its test

| Ticket | What it fixed | Tests |
|---|---|---|
| AH-172 | an outcome's NA is no label; stray labels left out and named; Red/Blue, Summer/Winter no outcome | `test_fairness_round_ah172.py` |
| AH-173 | sorted "?" placeholders one note; unknown tied entrants no duplicate; ZIP vs ZIP+4 no lost zero; fix rounds: a row with its own id stays a duplicate, a decimal score never names a row | `test_many_duplicates.py`, `test_placeholder_codes.py`, `test_leading_zeros.py` |
| AH-174 | punctuated misspellings; a total beside a mostly blank part; the harmful "likely 1.00851" card; 16+ digit IDs; code columns | `test_blind_round_1.py` |
| AH-176 | a 1% third label; a death date; a group's own bad cells; National/Transnational; fix round: AH-172's 1% rule kept beside it | `test_fairness_round_ah176.py` |
| AH-177 | honest below-zero temperatures; no-value spellings counted together; no style vote on code columns | `test_blind_round_2.py` |
| AH-178 | totals rows out of duplicates; a TOTAL category; labels past 200; year columns; the `order` check; fix rounds: only headers that name an order, plain numbers only beside a quantile word | `test_blind_round_2_misses.py` |
| (fuzz) | a sheet whose numbers sit only on a skipped row: a 500 under warnings-as-errors, on main too | `test_fuzz_api.py` |

Benches unchanged through all of it: `score.py .` 51 of 51 caught, 0 Medium false alarms, harm 0; `score.py . --blind`
199 of 201, 0 Medium false alarms, harm 0. Full gate with the browser tests: ALL GREEN, 1,860 engine tests.

## How to repeat

The planter, scanner and judge scripts are not in the repo (they hold no app code). The method is CLAUDE.md's blind
real-sheet test: a fresh set of tables each time, a planter with a secret key, a scanner that never sees it, every
table scanned (not only the planted ones). A round 4 must exclude the 126 sources of rounds 1-3.
