"""AH-212 scanner: every sheet of every complex workbook, scanned as Find problems scans it with that tab active.
usage: python -I scan.py <repo> <epdir> <outdir>
The adversarial bench hands the engine clean tables. A user's sheet first goes through the pane's own reading
(grid.mjs: the used range, tableFromGrid, formats for the top 30 rows), so its title rows, two-row headers, stacked
tables and subtotal rows reach the engine as they would. Then the same in-process /scan as adversarial/scan.py, at
the default strength, with the table's `calc` as `formulas` (only if any, as scan.scanRequest sends them).
Writes <outdir>/<book>__<sheet>.json: the scan answer + startRow, startCol, columns (to map flags back to cells), or
{"unread": true} where the pane finds no table.
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
        grid = json.dumps({k: s.get(k) for k in ("values", "formats", "formulas")})
        t = json.loads(subprocess.run(["node", str(GRID)], input=grid, capture_output=True, text=True,  # noqa: S603, S607 - our own script
                                      check=True).stdout)
        if t is None:
            res, said = {"unread": True}, "unread"
        else:
            body = {"columns": t["columns"], "rows": t["rows"], "limits": None, "order_by": None, "strength": 5,
                    "power_bi": False, "start_row": t["startRow"], "sheet": s["name"][:31], "decisions": None,
                    "formulas": t["calc"] if any(any(r) for r in t["calc"] or []) else None}
            r = client.post("/scan", json=body, headers={"Origin": "https://127.0.0.1:5055"})
            res = r.get_json() if r.status_code == 200 else {"error": r.status_code, "body": r.get_json()}
            res.update(startRow=t["startRow"], startCol=t["startCol"], columns=t["columns"])
            said = r.status_code if "error" in res else sum(x.get("severity") in ("High", "Medium") for x in res["rows"])
        res.update(book=book["name"], sheet=s["name"])
        (out / f"{book['name']}__{s['name']}.json").write_text(json.dumps(res))
        print(book["name"], "|", s["name"], said)
