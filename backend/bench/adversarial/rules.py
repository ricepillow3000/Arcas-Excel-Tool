"""AH-202 rules step: POST every episode sheet to the real engine's /rules (the AI reads the headers, the engine checks
each rule on every row) and write a merged scan where each row a rule flags that the scan did not is Medium on the rule's
cells, beside the scan's own rows. judge.py then scores the merged files unchanged.
usage: GEMINI_API_KEY=... python -I rules.py <repo> <sheets_dir> <scan_dir> <out_dir>
Your own Google key only, never the relay (CLAUDE.md: measured with your own key). Each run starts with an empty AI
answer cache (unless LOCALAPPDATA is set), so two runs show the AI's own noise; the rules and the calls made go to <out_dir>/_rules.json.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

repo, sheets, scans, out = (Path(a) for a in sys.argv[1:5])
# a fresh answer cache unless LOCALAPPDATA names one: a kept answer would hide the noise between two runs
os.environ.setdefault("LOCALAPPDATA", tempfile.mkdtemp())
sys.path.insert(0, str(repo / "backend"))
from anomaly_hunter.ai import client  # noqa: E402
from anomaly_hunter.engine.load import load_from_records  # noqa: E402
from anomaly_hunter.server import create_app  # noqa: E402

if client.provider() != "gemini":
    sys.exit("Set GEMINI_API_KEY: the rules step is measured with your own Google key, never the relay.")
calls, ask = [], client._call
client._call = lambda *a, **k: (calls.append(1), ask(*a, **k))[1]
app = create_app().test_client()
out.mkdir(parents=True, exist_ok=True)
log = {}
for f in sorted(sheets.glob("*.json")):
    s = json.loads(f.read_text())
    r = app.post("/rules", json={"columns": s["columns"], "rows": s["rows"]}, headers={"Origin": "https://127.0.0.1:5055"})
    got = r.get_json()
    if r.status_code != 200:
        sys.exit(f"{f.name}: /rules answered {r.status_code} {got}")
    names = list(load_from_records(s["columns"], [])[0].columns)  # the scan's names for its cells
    scan = json.loads((scans / f.name).read_text())
    for hit in got["rows"]:
        row = scan["rows"][hit["row"]]
        # what the rules step adds: a row the scan already calls wrong keeps the scan's own cells (the pane shows the
        # rule's line apart, under its button, and colours nothing for it); a row it did not becomes Medium on the
        # rule's cells, never a Low row's own
        if row.get("severity") not in ("High", "Medium"):
            row["severity"], row["cells"] = "Medium", [names[j] for j in hit["cells"]]
            row["reason"] = "; ".join(filter(None, [row.get("reason"), hit["reason"]]))
    (out / f.name).write_text(json.dumps(scan))
    log[f.stem] = {"sent": got["sent"], "headers": got["headers"], "flagged": len(got["rows"]),
                   "rules": [{"said": x["said"], "held": x["held"], "total": x["total"], "holds": x["holds"], "why": x["why"]}
                             for x in got["rules"]]}
    print(f.stem, f"{got['sent']}/{got['headers']} headers sent, {len(got['rows'])} rows flagged")
    for x in got["rules"]:
        print(f"  {'HOLDS' if x['holds'] else 'no   '} {x['held']}/{x['total']}  {x['said']}")
(out / "_rules.json").write_text(json.dumps({"ai_calls": len(calls), "sheets": log}, indent=1))
print("AI calls:", len(calls))
