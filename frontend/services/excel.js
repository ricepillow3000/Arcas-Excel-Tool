import { KEY, READ_CELLS } from "../constants/index.js";
import { state } from "../hooks/use-state.js";
import { maxCells, tableFromGrid } from "../utils/sheet.js";
import { areaOf, asSheet, formatRows, tablesFromGrid } from "../utils/layout.js";

// Talking to Excel (Office.js): read and write the sheet, workbook settings, clicks in the sheet.
export const getLimits = () =>
  new Promise((ok) => Office.context.document.settings.refreshAsync(() => ok(Office.context.document.settings.get(KEY) || null)));

export function saveLimits(limits) {
  if (limits) Office.context.document.settings.set(KEY, limits);
  else Office.context.document.settings.remove(KEY);
  Office.context.document.settings.saveAsync();
}

// The name of the sheet a scan would read now
export async function activeSheet() {
  return Excel.run(async (ctx) => {
    const sheet = ctx.workbook.worksheets.getActiveWorksheet().load("name");
    await ctx.sync();
    return sheet.name;
  });
}

// Values and formulas, in slices (number formats only for the top 30 rows, where the header and the first 20 data rows
// are: utils/sheet.js tells a date column by them). This was 3x the data in one call - the freeze on big sheets. AH-152:
// each cell's R1C1 formula (null where it holds none) goes to the engine too, so a typed 250 among a column's
// =RC[-2]*RC[-1] is seen; half the rows a slice keep each call the size it was. most: the rows read from the top at most
// (AH-169: what the pane says before a scan reads only the header and the first 500 rows). AH-181: `sheetKey` (a name or
// an id) reads that tab instead of the active one, and a sheet whose used rows `fits` refuses is not read: {sheet, big: true}.
// AH-212: a sheet of several tables comes back as one object, its rows one after another (utils/layout.js asSheet)
export async function readSheet(onSlice, most = Infinity, sheetKey = null, fits = () => true) {
  return Excel.run(async (ctx) => {
    const sheet = (sheetKey ? ctx.workbook.worksheets.getItem(sheetKey) : ctx.workbook.worksheets.getActiveWorksheet()).load("name");
    const used = sheet.getUsedRange().load("rowIndex, columnIndex, rowCount, columnCount");
    await ctx.sync();
    if (!fits(used.rowCount)) return { sheet: sheet.name, big: true };
    const { rowIndex: r0, columnIndex: c0, columnCount: w } = used;
    const total = Math.min(used.rowCount, Math.floor(maxCells() / w), most);
    const top = sheet.getRangeByIndexes(r0, c0, Math.min(total, 30), w).load("numberFormat");
    // AH-212: the merged areas tell a header of two rows and a label merged down its group (ExcelApi 1.13; an older
    // Excel reads the sheet without them)
    const areas = Office.context.requirements?.isSetSupported?.("ExcelApi", "1.13")
      ? sheet.getRangeByIndexes(r0, c0, total, w).getMergedAreasOrNullObject().load("isNullObject, address") : null;
    // AH-213: the cells Excel itself says break their data validation (a value outside its drop-down list), in one call
    // (ExcelApi 1.9; an older Excel reads the sheet without them)
    const broken = Office.context.requirements?.isSetSupported?.("ExcelApi", "1.9")
      ? sheet.getRangeByIndexes(r0, c0, total, w).getDataValidationInvalidCellsOrNullObject().load("isNullObject, address") : null;
    const step = Math.max(1, Math.floor(READ_CELLS / (2 * w))), values = [], formulas = [];
    for (let k = 0; k < total; k += step) {
      const part = sheet.getRangeByIndexes(r0 + k, c0, Math.min(step, total - k), w).load("values, formulasR1C1");
      await ctx.sync();
      for (const row of part.values) values.push(row);
      for (const row of part.formulasR1C1) formulas.push(row.map((f) => (typeof f === "string" && f.startsWith("=") ? f : null)));
      onSlice(values.length / total);
    }
    await ctx.sync();
    // AH-212: every table on the sheet (utils/layout.js), and the number formats of a table that starts below the top 30
    // rows, read then: its dates go to the engine as dates
    const merged = areas && !areas.isNullObject ? String(areas.address).split(",") : [], formats = [...top.numberFormat];
    let read = tablesFromGrid(values, formats, r0, c0, formulas, { merged });
    const more = formatRows(read.tables, r0, formats.length);
    if (more.length) {
      const parts = more.map(([k, n]) => sheet.getRangeByIndexes(r0 + k, c0, Math.min(n, total - k), w).load("numberFormat"));
      await ctx.sync();
      parts.forEach((p, m) => p.numberFormat.forEach((row, x) => (formats[more[m][0] + x] = row)));
      read = tablesFromGrid(values, formats, r0, c0, formulas, { merged });
    }
    // last: the sheet's last used row, 1-based (AH-180: one on Excel's last row was likely cut off when it opened)
    return read.tables.length ? asSheet(read.tables, { sheet: sheet.name, cut: total < used.rowCount && [r0 + total, r0 + used.rowCount],
      last: r0 + used.rowCount, unread: read.unread,
      invalid: broken && !broken.isNullObject ? String(broken.address).split(",").map(areaOf).filter(Boolean) : [] }) : null;
  });
}

// AH-180: every tab (at most TABS), in workbook order, as [{id, sheet, table}]: its first TAB_ROWS rows read as readSheet
// reads them (null when it holds no table). skip(id): a tab read before, given without `table`. One call for the list and
// the used ranges, then one per tab read. A workbook of one tab reads nothing
const TABS = 20, TAB_ROWS = 5000;
export async function readTabs(skip = () => false) {
  return Excel.run(async (ctx) => {
    const list = ctx.workbook.worksheets.load("items/name, items/id");
    await ctx.sync();
    if (list.items.length < 2) return [];
    const items = list.items.slice(0, TABS);
    const used = items.map((ws) => !skip(ws.id) && ws.getUsedRangeOrNullObject(true).load("isNullObject, rowIndex, columnIndex, rowCount, columnCount"));
    await ctx.sync();
    const tabs = [];
    for (const [k, ws] of items.entries()) {
      const u = used[k], t = { id: ws.id, sheet: ws.name };
      tabs.push(t);
      if (!u) continue;
      if (u.isNullObject) { t.table = null; continue; }
      const w = u.columnCount, rows = Math.min(u.rowCount, TAB_ROWS, Math.max(1, Math.floor(READ_CELLS / (2 * w))));
      const part = ws.getRangeByIndexes(u.rowIndex, u.columnIndex, rows, w).load("values, formulasR1C1");
      const top = ws.getRangeByIndexes(u.rowIndex, u.columnIndex, Math.min(rows, 30), w).load("numberFormat");
      await ctx.sync();
      const formulas = part.formulasR1C1.map((row) => row.map((f) => (typeof f === "string" && f.startsWith("=") ? f : null)));
      t.table = tableFromGrid(part.values, top.numberFormat, u.rowIndex, u.columnIndex, formulas);
    }
    return tabs;
  });
}

// AH-181: "Show me": that tab in front and the cell selected (a tab alone when no cell is named)
export async function showCell(sheetName, cell) {
  await Excel.run(async (ctx) => {
    const ws = ctx.workbook.worksheets.getItem(sheetName);
    ws.activate();
    if (cell) ws.getRange(cell).select();
    await ctx.sync();
  });
}

// One property of each cell: "formulas" (what was typed) or "numberFormat" (how it shows)
export async function readCells(sheetName, cells, prop = "formulas") {
  return Excel.run(async (ctx) => {
    const sheet = ctx.workbook.worksheets.getItem(sheetName);
    const ranges = cells.map((c) => sheet.getRange(c).load(prop));
    await ctx.sync();
    return ranges.map((r) => r[prop][0][0]);
  });
}

// Some rows as they are now, to check nothing moved since the scan or the fix. spans: [{row (0-based), col, width}]
// -> [{values, calc}] - calc[j] = that cell is a formula (its value changes on its own, so it proves nothing)
export async function readRows(sheetName, spans) {
  return Excel.run(async (ctx) => {
    const sheet = ctx.workbook.worksheets.getItem(sheetName);
    const ranges = spans.map((s) => sheet.getRangeByIndexes(s.row, s.col, 1, s.width).load("values, formulas"));
    await ctx.sync();
    return ranges.map((r) => ({ values: r.values[0], calc: r.formulas[0].map((f) => typeof f === "string" && f.startsWith("=")) }));
  });
}

// Writes as if typed: "=..." becomes a formula, "42" a number. Old contents kept for Undo. A write with a `format`
// puts that number format back too (typing "12%" makes a cell a percent; Undo must undo that as well). A write with
// `r1c1` is a column's own formula (AH-152): Excel turns it into this cell's A1 form itself.
export async function writeCells(sheetName, writes) {
  await Excel.run(async (ctx) => {
    const sheet = ctx.workbook.worksheets.getItem(sheetName);
    writes.forEach((w) => {
      const r = sheet.getRange(w.cell);
      if (w.r1c1) r.formulasR1C1 = [[w.r1c1]];
      else r.formulas = [[w.value]];
      if (w.format !== undefined) r.numberFormat = [[w.format]];
    });
    await ctx.sync();
  });
}

// Clicking a highlighted row in the sheet calls `handler` (only one watcher, on the last checked sheet).
export async function watchSelection(sheetName, handler) {
  if (state.picker && state.picker.sheet === sheetName) return;
  const old = state.picker;
  state.picker = null;
  if (old) await Excel.run(old.handle.context, async (ctx) => (old.handle.remove(), ctx.sync())).catch(() => {}); // old sheet gone: nothing to remove
  try {
    await Excel.run(async (ctx) => {
      const handle = ctx.workbook.worksheets.getItem(sheetName).onSelectionChanged.add(handler);
      await ctx.sync();
      state.picker = { sheet: sheetName, handle };
    });
  } catch (e) {
    console.error("could not watch selection", e); // list clicks still work
  }
}
