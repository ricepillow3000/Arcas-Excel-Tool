# AH-198: adversarial episodes (John, 2026-11-17)

John's goal: a reasoning policy for the scan that scores 98/100 or more on 3 consecutive unseen, escalating
adversarial episodes. Each episode has 4 sheets, one per subject: clinical trials, double-entry accounting,
multi-currency logistics and engineering BOMs.
His rules: improve only the reasoning inside the existing engine (same /scan in and out, no new features), and
use general principles, never fixes for one test sheet.

**Result: not converged.** We ran 3 episodes and 2 fix rounds, and every unseen episode scored far under 98. The
Pod Workflow stops here and hands the decision to John (2 fix rounds, then a human).

## How it was scored (fixed before episode 1)
- **Planter:** a separate helper builds each episode from scratch, and nobody else sees its answer key. It never
  read the engine's code or the earlier episodes. Every planted error is provable from the file alone, every trap
  is valid in its subject, and its own `check.py` recomputes every formula and rule.
- **Scan:** each sheet goes to the real engine's `/scan` at strength 5, exactly as the pane sends it
  (`backend/bench/adversarial/scan.py`).
- **Judge** (`judge.py`): a cell counts as flagged when its row is "looks wrong" (High or Medium) and the row names
  that cell. "Worth a check" (Low) counts for neither side. The score is:
  - recall: 40 x errors caught / all errors
  - domain: 40 x (subject-specific errors caught + traps left alone) / (both together)
  - precision: 20 if no valid cell is flagged
  - minus 25 for each flagged valid cell, and minus 25 for each flagged trap
- **No peeking:** each episode was scored on a build that had never seen it. Only after that score was it handed
  to the next fix round.

## Convergence telemetry
| Episode | Subject mix | Difficulty tier | Scored on (unseen) | Reward score | Policy update after it |
|---|---|---|---|---|---|
| 1 | clinical lab results (long format), general ledger journal, multi-currency shipments, multi-level BOM | 1 | main (39e7ebc) | **-562.0** (8/20 caught, 20 valid cells flagged, 4 traps flagged) | Fix round 1: formula cells, formula culprit, tree roots, counter-entries, crowds, circular references, date order, records over lines, long-format limits, misspellings a code proves |
| 2 | trial vitals and dosing, ledger with intercompany and VAT, freight invoices in 5 currencies, costed indented BOM | 2 | fix round 1 | **-49,242.2** (13/28 caught, 1,963 valid cells flagged, 8 traps flagged) | Fix round 2: trees, formula variants, balanced records, signs a label explains, weak evidence, key values, an entity's own scale |
| 3 | PK sampling log, fixed-asset depreciation, landed cost with duties, EV mass and centre-of-gravity roll-up | 3 | fix round 2 | **-111.5** (10/31 caught, 5 valid cells flagged, 1 trap flagged) | Stopped: not converged |

**The final build on all 3 episodes (1 and 2 were seen in training, so these are not unseen scores):** 69.0, 67.2
and -111.5.

Neither change moved the benches. The industry bench stays 51/51 and the blind bench 199/201, both with 0 Medium
false alarms.

On 129 real public tables, the High and Medium rows went from 1,621 to 1,626:
- **Added (every one a real error, checked by hand):** misspellings their own code proves, a grant that ends
  before it starts, two districts filed under the wrong state, and two county counts 10x off their own other years.
- **Removed:** crowds of honest values, and lone extremes with nothing behind them, which went to "worth a check".
  Two of those were real (a year 2084 in two tables); they are still listed, as worth a check.

## Why it did not reach 98
- **What the score demands:** a score of 98 needs about every planted error caught and not one valid cell flagged,
  on sheets the engine has never seen.
- **Precision is close:**
  - episode 2: 1,963 flagged valid cells became 0
  - episode 3: 5 flagged valid cells and 1 trap
- **Recall is the gap:** episode 3 caught 10 of 31. Most of its misses need the subject's own rule, which John's
  "general principles, never hardcoded fixes" rules out:
  - a roll-up missing a child
  - depreciation after an asset's disposal
  - months that do not match two dates
  - a concentration below the assay's limit while BLQ says no
  - a sample time out of the protocol's order
- **Each new rule also costs elsewhere:** these were measured and dropped because they flagged honest rows on the
  public tables:
  - one number above another on fewer than 1,000 rows
  - dates that go backwards inside a record
  - units in an entity's own scale

## The policy as it stands (not converged)
These are the general reasoning rules the engine now follows, in addition to the feature map in `CLAUDE.md`.

1. **A formula's result is not typed.** Limits never judge or name a formula cell; its odd value is its inputs'
   fault.
2. **Name the culprit.** When the formula check finds the broken cell on a row, every arithmetic reason about that
   cell names it alone.
3. **A second formula used on purpose is the column's own.**
   - A formula the column writes on 5 or more rows is a variant, not a break.
   - So is a formula on every row of one label, and only those rows.
   - A lone break is still flagged, and so is a value typed over the formula a label's other rows use.
4. **A tree is not a list.** Where every line's parent sits on the path above it:
   - a sub-tree listed again under another parent is the layout, not a duplicate
   - a top line's blank parent is a root, not a missing value
5. **A typo changes one cell; corroboration clears it.** None of these gets a vote or a "likely":
   - the same number in the counter column of a nearby row
   - an amount inside an entry whose debits equal its credits
   - negatives that are exactly the rows of one label (a rebate, a reversal)
6. **Weak evidence is "worth a check".** A lone breach of the far limit goes to Low when:
   - nothing else on its row is flagged, and no rule it breaks is found
   - no slip reads it back inside the usual limits (a decimal point, a sign, C/F, lb/kg, in/cm, ft/m, mi/km,
     mmol/L)
   - it is within 2 widths of the far limits
7. **Crowds are not slips.** A breach with no typo behind it is not a vote when 2 or more other breaches lie near
   it.
8. **Judge a value among its peers:**
   - in a long-format sheet, among the rows of its own label (test, currency)
   - against its own entity's other rows
   - against the one value its code key carries everywhere else
   - in a record split over lines, against the other lines of that record
9. **Excel's own impossibilities are always wrong:** a formula naming its own cell, an end date before its start,
   and an entry that does not balance, named by the digit swap that fixes it.

## What John can choose next
1. **Keep looping:** more fix rounds and episodes. Each round takes about 1.5 hours and gains a little recall.
   Reaching 98 three times without subject rules is unlikely.
2. **Allow subject rules:** for example, "a roll-up equals the sum of its children" or "no depreciation after
   disposal". That breaks the "general principles only" rule as written, so it needs John's say.
3. **Let the AI step check subject rules:** the optional AI (Ask AI) could read a sheet's subject and test its
   rules. That is a prompt change, so it needs `ai_eval.py` numbers on John's own key before it ships (CLAUDE.md).

The episodes, keys, scanner and judge are in `backend/bench/adversarial/` so any later build can be scored the
same way.

## AH-202: John's choice 3, the AI checks subject rules (2026-11-18)
John picked choice 3: send the AI only the column headers and whether each holds numbers, dates or text, never a
cell. The AI proposes subject rules (a sum, a product, an order, a value that is 0 after a date, a parent that is
the sum of its children). Arcas checks each one on every row on the PC, and only believes a rule that holds on 95% of
10+ rows (an order on all but max(1, 0.1%), the bar of the scan's own date order). It is an opt-in button, Check
subject rules with AI, and Find problems never calls it.

Measured with John's own Google key, two runs each, the judge unchanged. A rule row counts as a flag only where the
scan did not already flag that row. Episodes 4 and 5 are new and were never used to tune anything.

| Episode | Without the rules step | With it (run 1, run 2) | What changed |
|---|---|---|---|
| 1 (training) | 69.0 | 69.0, 69.0 | nothing |
| 2 (training) | 67.2 | 70.0, 70.0 | systolic and diastolic swapped, caught by "DBP is at most SBP" |
| 3 (training) | -111.5 | -135.2, -135.2 | 1 more caught, 1 more valid cell flagged |
| 4 (held out) | -2,523.0 | -2,523.0, -2,523.0 | every row a rule flagged, the scan had already flagged |
| 5 (held out) | -5,934.5 | -5,957.2, -5,957.2 | 1 more caught (more tablets returned than dispensed), 1 more valid cell flagged |

Result: on the held-out episodes the rules step adds 1 catch and 1 false cell, so it does not move the score toward
98. The rules the AI proposes are mostly right (Net = Debit − Credit, payroll gross to net, Tablets taken =
Dispensed − Returned), but the scan already catches most rows that break them. The misses that remain need rules
across rows that the five shapes cannot say. The two runs gave the same rules.

What hurts the held-out score is false alarms on new subjects (102 and 238 valid cells flagged), and the AI step
cannot take a flag away. Episodes 4 and 5 are in `backend/bench/adversarial/` now, so they are no longer held out
either.
