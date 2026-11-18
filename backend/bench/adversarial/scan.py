"""AH-198 scanner: POST every episode sheet to the real engine's /scan exactly as the pane does (strength 5).
usage: python -I scan.py <repo> <sheets_dir> <out_dir>
Sheet file: {"name", "columns": [...], "rows": [[...]], "formulas": [[R1C1 or null]] or null}
"""
import json, sys
from pathlib import Path
repo, sheets, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(repo / "backend"))
from anomaly_hunter.server import create_app  # noqa: E402
client = create_app().test_client()
out.mkdir(parents=True, exist_ok=True)
for f in sorted(sheets.glob("*.json")):
    s = json.loads(f.read_text())
    body = {"columns": s["columns"], "rows": s["rows"], "limits": None, "order_by": None, "strength": 5,
            "power_bi": False, "start_row": 0, "sheet": s["name"][:31], "decisions": None, "formulas": s.get("formulas")}
    r = client.post("/scan", json=body, headers={"Origin": "https://127.0.0.1:5055"})
    res = r.get_json()
    if r.status_code != 200:
        res = {"error": r.status_code, "body": res}
    (out / f.name).write_text(json.dumps(res))
    print(f.name, r.status_code, sum(1 for x in res.get("rows", []) if x.get("severity") in ("High", "Medium")) if r.status_code == 200 else res)
