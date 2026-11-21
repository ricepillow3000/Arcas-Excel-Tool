// AH-212: one sheet as Find problems reads it (frontend/services/excel.js readSheet), with no Office. stdin: one sheet
// of a complex workbook, {values, formats, formulas} from A1 (FORMAT.md). stdout: tableFromGrid's table, or null.
// usage: node grid.mjs < sheet.json
import { readFileSync } from "node:fs";
import { maxCells, tableFromGrid } from "../../../frontend/utils/sheet.js";

const { values, formats, formulas } = JSON.parse(readFileSync(0, "utf8"));
const used = (r, c) => (values[r][c] !== "" && values[r][c] !== null) || !!formulas?.[r]?.[c];
// Excel's used range starts at its first used row and column, not at A1, and the header is looked for in its first 10 rows
const rows = values.map((_, r) => r).filter((r) => values[r].some((_, c) => used(r, c)));
const cols = (values[0] || []).map((_, c) => c).filter((c) => values.some((_, r) => used(r, c)));
let table = null;
if (rows.length) {
  const r0 = rows[0], c0 = cols[0], w = cols.at(-1) + 1 - c0;
  const total = Math.min(rows.at(-1) + 1 - r0, Math.floor(maxCells() / w));
  const cut = (grid, n) => grid.slice(r0, r0 + n).map((r) => r.slice(c0, c0 + w));
  // readSheet loads number formats for the top 30 rows only, and a formula only where the cell's R1C1 text starts with "="
  const calc = cut(formulas || values.map((r) => r.map(() => null)), total)
    .map((r) => r.map((f) => (typeof f === "string" && f.startsWith("=") ? f : null)));
  table = tableFromGrid(cut(values, total), formats ? cut(formats, Math.min(total, 30)) : null, r0, c0, calc);
}
process.stdout.write(JSON.stringify(table));
