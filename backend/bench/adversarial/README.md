# AH-198 adversarial episodes

Five episodes of four synthetic sheets (4 and 5 for AH-202): clinical trials, double-entry accounting, multi-currency logistics and
engineering BOMs. Each was built by a separate planter that never read the engine, and comes with a secret key
(`keys/`) of planted errors and valid traps. The results are in `docs/eval/2026-11-18-ah198-adversarial-episodes.md`.

Score any build. Do this once per episode, with N = 1 to 5:

    PYTHONPATH=$PWD/backend python -I backend/bench/adversarial/scan.py . backend/bench/adversarial/epN /tmp/epN
    python -I backend/bench/adversarial/judge.py backend/bench/adversarial/epN /tmp/epN backend/bench/adversarial/keys/epN.json

AH-202's rules step (Check subject rules with AI) after the scan, with your own Google key, never the relay; then judge
`/tmp/epN-rules` the same way:

    GEMINI_API_KEY=... python -I backend/bench/adversarial/rules.py . backend/bench/adversarial/epN /tmp/epN /tmp/epN-rules

These five episodes are no longer held out: fix rounds were built against them. A new claim needs a fresh episode.

AH-208 added `plant.py`, a seeded planter of 6 subjects (payroll, retail inventory, school grades, field sensors,
insurance claims, project budgets), each with its own honest quirks and 8 planted errors and 4-5 valid traps; the seed
picks 4 subjects. Episodes 6-8 (seeds 6, 7, 8) were AH-208's tuning set; 9 and 10 (seeds 9, 10) were its held-out set,
scored once at the end. None of them is held out now. A new episode is a new seed:

    python -I backend/bench/adversarial/plant.py 11 /tmp/ep11 /tmp/keys/ep11.json
Known planter bug (found scoring 9 and 10): in the inventory sheet, shrinkage can take a week's closing stock below 0,
and the next week then opens negative and "sells" a negative number of units on honest rows (5 rows in each of
episodes 9 and 10). The engine is right to flag those cells; a judge of those episodes should set them aside. Fixing it
changes the inventory sheets every seed builds, so it waits for a new set of episodes.
