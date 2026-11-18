# AH-198 adversarial episodes

Three episodes of four synthetic sheets: clinical trials, double-entry accounting, multi-currency logistics and
engineering BOMs. Each was built by a separate planter that never read the engine, and comes with a secret key
(`keys/`) of planted errors and valid traps. The results are in `docs/eval/2026-11-18-ah198-adversarial-episodes.md`.

Score any build. Do this once per episode, with N = 1, 2 or 3:

    PYTHONPATH=$PWD/backend python -I backend/bench/adversarial/scan.py . backend/bench/adversarial/epN /tmp/epN
    python -I backend/bench/adversarial/judge.py backend/bench/adversarial/epN /tmp/epN backend/bench/adversarial/keys/epN.json

AH-201's rules step (Check subject rules with AI) after the scan, with your own Google key, never the relay; then judge
`/tmp/epN-rules` the same way:

    GEMINI_API_KEY=... python -I backend/bench/adversarial/rules.py . backend/bench/adversarial/epN /tmp/epN /tmp/epN-rules

These three episodes are no longer held out: fix rounds were built against them. A new claim needs a fresh episode.
