"""AH-212 scanner: every sheet of every complex workbook, scanned as Find problems scans it with that tab active.
usage: python -I scan.py <repo> <epdir> <outdir>
The adversarial bench hands the engine clean tables. A user's sheet first goes through the pane's own reading
(grid.mjs: the used range, the layout reader utils/layout.js tablesFromGrid, formats for the top 30 rows and each
lower table's first rows), so its title rows, two-row headers, stacked tables and subtotal rows reach the engine as
they would: one /scan per table (AH-212), as scan.scanRequest sends them, never two tables' columns in one. The same
in-process /scan as adversarial/scan.py, at the default strength, with the table's rows and formulas as the engine
gets them (`sent`: merged labels filled down, subtotal and notes rows blank; formulas only if any).
Writes <outdir>/<book>__<sheet>.json: {"tables": [the scan answer + startRow, startCol, columns per table (to map flags
back to cells)], "unread_cells": [A1 blocks]}, or {"unread": true} where the pane finds no table.
"""
import json
import subprocess
import sys
from pathlib import Path

repo, eps, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(repo / "backend"))
from anomaly_hunter.server import create_app

GRID = repo / "backend" / "bench" / "complex" / "grid.mjs"
client = create_app().test_client()
out.mkdir(parents=True, exist_ok=True)
for f in sorted(eps.glob("*.json")):
    book = json.loads(f.read_text())
    for s in book["sheets"]:
        grid = json.dumps({k: s.get(k) for k in ("values", "formats", "formulas", "merged")})
        t = json.loads(subprocess.run(["node", str(GRID)], input=grid, capture_output=True, text=True,  # noqa: S603, S607 - our own script
                                      check=True).stdout)
        if t is None:
            res, said = {"unread": True}, "unread"
        else:
            res, said = {"tables": [], "unread_cells": t["unread"]}, []
            for tab in t["tables"]:
                calc = tab["sent"]["calc"]
                body = {"columns": tab["columns"], "rows": tab["sent"]["rows"], "limits": None, "order_by": None,
                        "strength": 5, "power_bi": False, "start_row": tab["startRow"], "sheet": s["name"][:31],
                        "decisions": None, "formulas": calc if any(any(r) for r in calc or []) else None}
                r = client.post("/scan", json=body, headers={"Origin": "https://127.0.0.1:5055"})
                one = r.get_json() if r.status_code == 200 else {"error": r.status_code, "body": r.get_json()}
                if "error" in one:
                    res = one
                    break
                one.update(startRow=tab["startRow"], startCol=tab["startCol"], columns=tab["columns"])
                res["tables"].append(one)
                said.append(sum(x.get("severity") in ("High", "Medium") for x in one["rows"]))
        res.update(book=book["name"], sheet=s["name"])
        (out / f"{book['name']}__{s['name']}.json").write_text(json.dumps(res))
        print(book["name"], "|", s["name"], said)
