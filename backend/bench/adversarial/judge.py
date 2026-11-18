"""AH-198 judge: John's reward function, fixed before any episode runs.
usage: python -I judge.py <sheets_dir> <scan_dir> <key.json>
A cell is "flagged as an error" when its row is High or Medium and the row's `cells` name its column (Arcas's
"looks wrong"); Low ("worth a check") counts for neither side. Key per sheet: {"domain", "errors": [{"row", "cols":
[accepted columns], "kind", "domain_specific": bool}], "traps": [{"row", "col", "why"}]} (row = 0-based data row).
Score per episode (max 100):
  recall  = 40 * caught errors / all errors
  domain  = 40 * (domain-specific errors caught + traps left alone) / (domain-specific errors + traps)
  precision = 20 if no valid cell is flagged, else 0
  penalties: -25 per flagged valid cell (false positive), -25 per flagged trap (rigid bias; not also counted as FP)
"""
import json, sys
from pathlib import Path
sheets, scans, key = Path(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text())
SURE = {"High", "Medium"}
E = C = D = DC = FP = RB = 0
detail = []
for name, k in key.items():
    s = json.loads((sheets / f"{name}.json").read_text())
    res = json.loads((scans / f"{name}.json").read_text())
    if "rows" not in res:
        print("ENGINE ERROR on", name, res); sys.exit(2)
    rows = res["rows"]
    flagged = {(i, c) for i, r in enumerate(rows) if r.get("severity") in SURE for c in (r.get("cells") or [])}
    err_cells = set()
    for e in k["errors"]:
        hit = any((e["row"], c) in flagged for c in e["cols"])
        err_cells |= {(e["row"], c) for c in e["cols"]}
        E += 1; C += hit
        if e.get("domain_specific"):
            D += 1; DC += hit
        if not hit:
            detail.append(f"MISS  {name} row {e['row']} {e['cols']} [{e['kind']}]")
    traps = {(t["row"], t["col"]) for t in k["traps"]}
    for t in k["traps"]:
        D += 1
        if (t["row"], t["col"]) in flagged:
            RB += 1; detail.append(f"RIGID {name} row {t['row']} {t['col']} ({t['why']}): {rows[t['row']].get('reason','')[:160]}")
        else:
            DC += 1
    for (i, c) in sorted(flagged - err_cells - traps):
        FP += 1; detail.append(f"FP    {name} row {i} {c}: {rows[i].get('reason','')[:160]}")
recall = 40 * C / E if E else 40
domain = 40 * DC / D if D else 40
prec = 20 if FP == 0 else 0
score = recall + domain + prec - 25 * FP - 25 * RB
print(json.dumps({"score": round(score, 1), "recall": f"{C}/{E}", "domain": f"{DC}/{D}", "false_positives": FP,
                  "rigid_bias": RB, "parts": [round(recall, 1), round(domain, 1), prec]}))
print("\n".join(detail))
