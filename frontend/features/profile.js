import { $, show } from "../utils/dom.js";
import { esc } from "../utils/text.js";
import { post } from "../services/api.js";
import { readSheet } from "../services/excel.js";

// AH-169 (John, 2026-11-16, "on the PC only"): before Find problems, what the sheet looks like and what the scan will
// check, worked out by the engine on this PC (/profile: no AI, no network). It reads the header and the first 500 rows
// only: enough to tell what kind of sheet it is, and quick on any sheet, where the scan reads it whole. It paints nothing
// and saves nothing, in the workbook or on this PC; on any failure it says nothing (Find problems still works).
const ROWS = 500, TOP = 10; // tableFromGrid looks for the header in the first 10 rows
let asked = 0; // only the newest ask lands; a scan begun since wins over it

export async function sayProfile() {
  const me = ++asked, box = $("before-scan"), lines = $("before-scan-lines");
  box.toggleAttribute("data-reading", true);
  lines.textContent = "Reading your sheet…"; // nothing waits in silence (AH-157)
  show("before-scan");
  try {
    const s = await readSheet(() => {}, ROWS + TOP);
    if (!s) throw new Error("no table");
    const { lines: said } = await post("/profile", { columns: s.columns, rows: s.rows.slice(0, ROWS) }, 30);
    if (me !== asked) return;
    lines.innerHTML = said.map((line) => `<p>${esc(line)}</p>`).join("");
    box.toggleAttribute("data-reading", false);
  } catch {
    if (me === asked) hideProfile();
  }
}

export function hideProfile() {
  asked++;
  show("before-scan", false);
  $("before-scan").toggleAttribute("data-reading", false);
}
