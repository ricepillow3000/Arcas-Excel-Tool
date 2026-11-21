// AH-212: one sheet as Find problems reads it (frontend/services/excel.js readSheet), with no Office. stdin: one sheet
// of a complex workbook, {values, formats, formulas, merged} from A1 (FORMAT.md). stdout: {tables, unread} as the pane's
// layout reader gives them, each table with `sent` (its rows and formulas as the engine gets them), or null. AH-213: and
// each table's `invalid`, the cells Excel would say break their drop-down list (the sheet's `validation`: a value outside
// its list, compared as Excel does, capitals aside; a blank cell is allowed), as readSheet reads them.
// AH-215: and `hints`, the /layout answer for this sheet (Read layout with AI), applied as the pane applies them: its rows
// sent blank among each table's layout rows.
// usage: node grid.mjs < sheet.json
import { readFileSync } from "node:fs";
import { maxCells } from "../../../frontend/utils/sheet.js";
import { areaOf, formatRows, invalidIn, sentOf, tablesFromGrid } from "../../../frontend/utils/layout.js";
import { hinted, hintsOf, keyOf } from "../../../frontend/utils/hints.js";

const { values, formats, formulas, merged, validation, hints } = JSON.parse(readFileSync(0, "utf8"));
const broken = [];
for (const { range, list } of validation || []) {
  const a = areaOf(range), ok = new Set(list.map((x) => String(x).toLowerCase()));
  for (let r = a.r1; r <= Math.min(a.r2, values.length - 1); r++) for (let c = a.c1; c <= a.c2; c++) {
    const v = values[r][c];
    if (v !== "" && v !== null && v !== undefined && !ok.has(String(v).toLowerCase())) broken.push({ r1: r, c1: c, r2: r, c2: c });
  }
}
const used = (r, c) => (values[r][c] !== "" && values[r][c] !== null) || !!formulas?.[r]?.[c];
// Excel's used range starts at its first used row and column, not at A1
const rows = values.map((_, r) => r).filter((r) => values[r].some((_, c) => used(r, c)));
const cols = (values[0] || []).map((_, c) => c).filter((c) => values.some((_, r) => used(r, c)));
let out = null;
if (rows.length) {
  const r0 = rows[0], c0 = cols[0], w = cols.at(-1) + 1 - c0;
  const total = Math.min(rows.at(-1) + 1 - r0, Math.floor(maxCells() / w));
  const cut = (grid, from, n) => grid.slice(r0 + from, r0 + from + n).map((r) => r.slice(c0, c0 + w));
  // readSheet loads number formats for the top 30 rows, then each lower table's first rows; a formula only where the
  // cell's R1C1 text starts with "="; the merged areas where Excel has ExcelApi 1.13
  const calc = cut(formulas || values.map((r) => r.map(() => null)), 0, total)
    .map((r) => r.map((f) => (typeof f === "string" && f.startsWith("=") ? f : null)));
  const vals = cut(values, 0, total), fmts = formats ? cut(formats, 0, Math.min(total, 30)) : null;
  const opts = { merged: merged || [] };
  let read = tablesFromGrid(vals, fmts, r0, c0, calc, opts);
  const more = fmts ? formatRows(read.tables, r0, fmts.length) : [];
  if (more.length) {
    for (const [k, n] of more) cut(formats, k, Math.min(n, total - k)).forEach((row, x) => (fmts[k + x] = row));
    read = tablesFromGrid(vals, fmts, r0, c0, calc, opts);
  }
  const book = hints ? hintsOf({ tables: read.tables }, hints) : {};
  if (read.tables.length) out = { tables: read.tables.map((t) => ({ ...t, sent: sentOf(hinted(t, book[keyOf(t)])), invalid: invalidIn(t, broken) })),
    unread: read.unread };
}
process.stdout.write(JSON.stringify(out));
