"""AH-235: the engine solves first, AI last. score.py says how many planted slips the pane's own card fixes for sure
(the right value), as a guess, or not at all, so a solver can only move the sure number up."""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SURE_FLOOR = 35  # raise it when a solver gets better, never lower it


def test_the_engine_fixes_at_least_the_floor_for_sure_and_never_wrongly():
    out = subprocess.run([sys.executable, str(ROOT / "backend/bench/score.py"), str(ROOT)],
                         capture_output=True, text=True, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "backend")}).stdout
    m = re.search(r"ENGINE FIXES: sure (\d+) / guess (\d+) / none (\d+) \(of (\d+)\), wrong sure (\d+)", out)
    assert m, "score.py prints no ENGINE FIXES line"
    sure, guess, none, total, wrong = map(int, m.groups())
    assert sure + guess + none == total
    assert wrong == 0
    assert sure >= SURE_FLOOR
