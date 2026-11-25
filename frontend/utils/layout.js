import { EXCEL_ERRORS } from "../constants/index.js";
import { colLetter, excelDate, headerAt, isDateFormat, rowFromAddress, tableAt, tableFromGrid } from "./sheet.js";

// AH-212: a power user's sheet is seldom one table. tableFromGrid read the used range as one, so a two-row header's
// second row (Jan, Feb under a merged Q1) was data, two stacked tables were one, a label merged down its group was blank
// on every row but the first, and subtotal and notes rows were checked as records (an independent planter's 12 complex
// workbooks, ep1-4: 339 false alarms, 54 of them on subtotal and notes rows). The reader below finds each table, and says
// what it could not read.

const blank = (v) => v === "" || v === null || v === undefined;

// Pure: "B6:B17", "Sheet1!$A$1:$F$1" or "C7" -> {r1, c1, r2, c2}, 0-based sheet rows and columns, or null
export function areaOf(a) {
  const m = /^\$?([A-Z]{1,3})\$?(\d{1,7})(?::\$?([A-Z]{1,3})\$?(\d{1,7}))?$/.exec(String(a).replace(/^.*!/, "").trim());
  if (!m) return null;
  const col = (s) => [...s].reduce((k, ch) => k * 26 + ch.charCodeAt(0) - 64, 0) - 1;
  const [r1, c1, r2, c2] = [+m[2] - 1, col(m[1]), +(m[4] || m[2]) - 1, col(m[3] || m[1])];
  return { r1: Math.min(r1, r2), c1: Math.min(c1, c2), r2: Math.max(r1, r2), c2: Math.max(c1, c2) };
}

// Pure: 0-based {r1, c1, r2, c2} -> "A18:B23" (one cell: "A25")
export const a1Of = (b) => `${colLetter(b.c1)}${b.r1 + 1}${b.r1 === b.r2 && b.c1 === b.c2 ? "" : `:${colLetter(b.c2)}${b.r2 + 1}`}`;

// Pure: the runs of indexes from..to where on(k) holds -> [[first, last]]
function runs(from, to, on) {
  const out = [];
  for (let k = from; k <= to; k++) if (on(k)) (out.length && out.at(-1)[1] === k - 1 ? (out.at(-1)[1] = k) : out.push([k, k]));
  return out;
}

// Pure: the used cells cut into blocks at fully blank rows and columns, again inside each part (rows first: a side table
// ends above a longer one's notes), top to bottom then left to right
function blocks(used, H, W) {
  const out = [], todo = H && W ? [[0, H - 1, 0, W - 1]] : [];
  while (todo.length) {
    const [a, b, c, d] = todo.pop();
    const rows = runs(a, b, (r) => { for (let j = c; j <= d; j++) if (used(r, j)) return true; return false; });
    if (rows.length !== 1) { rows.forEach(([x, y]) => todo.push([x, y, c, d])); continue; }
    const [x, y] = rows[0], cols = runs(c, d, (j) => { for (let r = x; r <= y; r++) if (used(r, j)) return true; return false; });
    if (cols.length > 1) cols.forEach(([p, q]) => todo.push([x, y, p, q]));
    else out.push({ r1: x, r2: y, c1: cols[0][0], c2: cols[0][1] });
  }
  return out.sort((p, q) => p.r1 - q.r1 || p.c1 - q.c1);
}

// a summary formula: SUM, SUBTOTAL, AVERAGE... of the rows above it in its own column (R1C1)
const SUMMED = /\b(?:SUM|SUBTOTAL|AGGREGATE|AVERAGE|COUNTA?|MIN|MAX|MEDIAN)\((?:\d+,\s*)*R\[-\d+\]C:R\[-\d+\]C\)/i;
const TOTAL = /\b(?:sub-?\s?totals?|grand\s+total|totals?)\b/i;
const NOTE = /^\s*(?:notes?\b|source\b|n\.\s?b\.|\*)/i;

// Pure: the used range's values (formats, formulas: the same shape; formats may hold only some rows), its top-left cell
// (r0, c0, 0-based) and its merged areas (A1 strings) -> {tables, unread}. Each table is tableFromGrid's shape, at its own
// sheet row and column, with `fills` ([i, j, value]: a label merged down its rows, for the scan only, never written back)
// and `layout` (its data rows that are subtotals or notes, sent blank: the engine's own summary_rows skips a blank row).
// unread: the A1 blocks that hold numbers or formulas but no table. errors (AH-218): [A1, error] of each cell no table
// holds that shows an Excel error (#REF!...), in sheet order. A sheet of one block reads as tableFromGrid reads it.
export function tablesFromGrid(values, formats, r0, c0, formulas, { merged = [] } = {}) {
  const H = values.length, W = H ? values[0].length : 0;
  const fx = (r, c) => formulas?.[r]?.[c] || null;
  const used = (r, c) => !blank(values[r][c]) || !!fx(r, c);
  const merges = merged.map(areaOf).filter(Boolean).map((m) => ({ r1: m.r1 - r0, r2: m.r2 - r0, c1: m.c1 - c0, c2: m.c2 - c0 }))
    .filter((m) => m.r1 >= 0 && m.c1 >= 0 && m.r2 < H && m.c2 < W && (m.r2 > m.r1 || m.c2 > m.c1));
  // a block of titles or notes alone (one cell a row, no number) is no part of the layout: "Sales summary" over a table
  const words = (b) => { for (let r = b.r1; r <= b.r2; r++) { let k = 0; for (let c = b.c1; c <= b.c2; c++) if (used(r, c) && (++k > 1 || typeof values[r][c] === "number" || fx(r, c))) return false; } return true; };
  const parts = blocks(used, H, W).filter((b) => !words(b));
  const label = (r, c) => typeof values[r][c] === "string" || (typeof values[r][c] === "number" && (isDateFormat(formats?.[r]?.[c] ?? "")
    || (Number.isInteger(values[r][c]) && values[r][c] >= 1900 && values[r][c] <= 2100)));
  const across = (r, c) => merges.find((m) => m.r1 === r && m.c1 <= c && c <= m.c2 && m.c2 > m.c1); // a group label spans c
  const tables = [], taken = [];

  // a block's header row: its first row (of the first 10 that fill 2+ cells) whose cells are all labels and cover 60% of
  // its width, merged spans counted. -1: none (a list of labels and values, a tile, a note)
  const headerIn = (b) => {
    const width = b.c2 - b.c1 + 1;
    let tried = 0;
    for (let r = b.r1; r <= b.r2 && tried < 10; r++) {
      const cols = []; // filled columns of the row
      for (let c = b.c1; c <= b.c2; c++) if (used(r, c)) cols.push(c);
      if (cols.length < 2) continue;
      tried++;
      const covered = cols.reduce((k, c) => k + (across(r, c) ? across(r, c).c2 - c + 1 : 1), 0);
      if (r < b.r2 && covered >= 0.6 * width && cols.every((c) => label(r, c))) return r;
    }
    return -1;
  };
  // the row under the header names its columns too (Jan, Feb under a merged Q1; Original, Revised under Budget): half its
  // cells or more sit under a group label merged across (a month of one week has no merge), or with no merge, its cells
  // are words where the header is blank beside a group's label and the data below is numbers; it is blank under at least
  // one header of its own
  const subUnder = (h, b) => {
    if (h + 2 > b.r2) return false;
    const cols = [], own = [];
    for (let c = b.c1; c <= b.c2; c++) if (used(h + 1, c)) cols.push(c);
    for (let c = b.c1; c <= b.c2; c++) if (used(h, c) && !across(h, c) && !used(h + 1, c)) own.push(c);
    if (cols.length < 2 || !own.length) return false;
    if (2 * cols.filter((c) => merges.some((m) => m.r1 === h && m.c1 <= c && c <= m.c2 && m.c2 > m.c1)).length >= cols.length) return true;
    const numeric = (c) => { const seen = []; for (let r = h + 2; r <= Math.min(b.r2, h + 21); r++) if (!blank(values[r][c])) seen.push(values[r][c]); return 2 * seen.filter((v) => typeof v === "number").length > seen.length; };
    return cols.every((c) => typeof values[h + 1][c] === "string") && cols.some((c) => !used(h, c)) && cols.some(numeric);
  };
  // a column under a header of two rows is named from both: "Q1 Jan", "Budget Revised"; a header merged down its two rows once
  const nameOf = (h, c, b) => {
    const m = across(h, c);
    let top = m ? values[h][m.c1] : values[h][c];
    if (blank(top) && used(h + 1, c)) for (let k = c - 1; k >= b.c1 && blank(top) && used(h + 1, k); k--) top = values[h][k];
    let low = values[h + 1][c];
    if (typeof low === "number" && isDateFormat(formats?.[h + 1]?.[c] ?? "")) low = excelDate(low);
    const said = [top, low].filter((v) => !blank(v)).map((v) => String(v).trim());
    return said.length === 2 && said[0] === said[1] ? said[0] : said.join(" ");
  };
  // a block of data rows under a table: below it with 1-2 blank rows between, inside its columns, its rows 3/4 as full or
  // more (a label and its number under a table of 4 columns is no row of it)
  const fill = (r, b) => { let k = 0; for (let c = b.c1; c <= b.c2; c++) k += used(r, c) ? 1 : 0; return k; };
  const median = (xs) => [...xs].sort((p, q) => p - q)[Math.floor(xs.length / 2)] || 0;

  // one block with no merged areas is the sheet tableFromGrid always read, read as it read it; merged areas mark a header
  // of two rows, whose second row its rule would take for the header (Jan..Dec filled, Q1 alone in its merge)
  const one = parts.length === 1, plain = one && !merges.length && headerAt(values) >= 0;
  for (const b of parts) {
    const t = tables.findLast((x) => x.c1 <= b.c1 && b.c2 <= x.c2 && x.r2 < b.r1 && b.r1 - x.r2 <= 3);
    if (!one && headerIn(b) < 0 && t) {
      const was = [];
      for (let r = t.h + 1; r <= t.r2; r++) was.push(fill(r, t));
      const now = [];
      for (let r = b.r1; r <= b.r2; r++) now.push(fill(r, t));
      if (4 * median(now) >= 3 * median(was)) { t.r2 = b.r2; continue; }
    }
    // one block whose header holds a number that is no year or date (weeks 1, 2, 3) is still read as tableFromGrid reads it
    const whole = plain || (one && headerIn(b) < 0 && headerAt(values) >= 0), h = whole ? headerAt(values) : headerIn(b);
    if (h < 0 || h + 1 > b.r2) { taken.push({ b, read: false }); continue; }
    const box = whole ? { r1: 0, r2: H - 1, c1: 0, c2: W - 1 } : b; // tableFromGrid's own cut
    tables.push({ ...box, h, sub: subUnder(h, box) });
    taken.push({ b, read: true });
  }

  const out = tables.map((t) => {
    if (plain && !t.sub) return { ...tableFromGrid(values, formats, r0, c0, formulas), fills: [], layout: [] };
    const first = t.h + (t.sub ? 2 : 1), cols = (row) => row.slice(t.c1, t.c2 + 1);
    const rows = values.slice(first, t.r2 + 1).map(cols);
    const calc = formulas ? formulas.slice(first, t.r2 + 1).map(cols) : formulas;
    const fmts = formats ? Array.from({ length: Math.max(0, Math.min(formats.length, t.r2 + 1) - first) }, (_, k) => formats[first + k] && cols(formats[first + k])) : formats;
    const header = Array.from({ length: t.c2 - t.c1 + 1 }, (_, j) => (t.sub ? nameOf(t.h, t.c1 + j, t) : values[t.h][t.c1 + j]));
    const table = tableAt(header, rows, fmts, r0 + first - 1, c0 + t.c1, calc);
    // a label merged down its rows: Excel gives its value to the top cell alone
    table.fills = merges.filter((m) => m.r2 > m.r1 && m.r2 >= first && m.r1 <= t.r2 && m.c1 >= t.c1 && m.c2 <= t.c2 && !blank(values[m.r1][m.c1]))
      .flatMap((m) => { const cells = [];
        for (let r = Math.max(m.r1, first); r <= Math.min(m.r2, t.r2); r++) for (let c = m.c1; c <= m.c2; c++) if ((r !== m.r1 || c !== m.c1) && blank(values[r][c])) cells.push([r - first, c - t.c1, table.rows[m.r1 - first]?.[m.c1 - t.c1] ?? values[m.r1][m.c1]]);
        return cells; });
    // subtotals and notes are no records. A summary formula counts only where the column does not write it on most rows
    // (a rolling 3-row average is a column of its own); a total's label only on a row sparser than most. A plain sheet
    // keeps its rows as the engine always got them (above): its own summary_rows reads a "Total" line (a journal's entry
    // totals on every adversarial bench table read the same, and the complex bench moved not at all without them)
    const n = rows.length, filled = rows.map((r, i) => r.reduce((k, v, j) => k + (blank(v) && !calc?.[i]?.[j] ? 0 : 1), 0));
    const usual = median(filled.filter(Boolean)), seen = new Map();
    calc?.forEach((r) => r.forEach((f, j) => f && SUMMED.test(f) && seen.set(`${j}\u0000${f}`, (seen.get(`${j}\u0000${f}`) || 0) + 1)));
    table.layout = rows.flatMap((r, i) => {
      const words = r.filter((v) => typeof v === "string" && v.trim());
      const summed = calc?.[i]?.some((f, j) => f && SUMMED.test(f) && seen.get(`${j}\u0000${f}`) <= Math.max(2, 0.25 * n));
      const total = filled[i] < usual && words.some((v) => TOTAL.test(v));
      const note = filled[i] === 1 && words.length === 1 && r.length >= 3 && (words[0].length >= 25 || NOTE.test(words[0]));
      return summed || total || note ? [i] : [];
    });
    // under the last subtotal, up to 3 rows worked out from the rows above alone (a Cumulative row, a total converted)
    // are more of the summary, never records
    const last = table.layout.at(-1) ?? n, tail = rows.slice(last + 1);
    if (last < n - 1 && tail.length <= 3 && tail.every((r, k) => r.every((v, j) => typeof v !== "number" || calc?.[last + 1 + k]?.[j])
      && (r.every(blank) || calc?.[last + 1 + k]?.some((f) => f && /R\[-\d+\]/.test(f))))) table.layout.push(...tail.map((_, k) => last + 1 + k));
    return table;
  });
  const unread = taken.filter((x) => !x.read).map((x) => x.b).filter((b) => {
    // AH-218: a formula showing an Excel error is said as that error below, once
    for (let r = b.r1; r <= b.r2; r++) for (let c = b.c1; c <= b.c2; c++) if (typeof values[r][c] === "number" || (fx(r, c) && !Object.hasOwn(EXCEL_ERRORS, values[r][c]))) return true;
    return false;
  }).map((b) => a1Of({ r1: b.r1 + r0, r2: b.r2 + r0, c1: b.c1 + c0, c2: b.c2 + c0 }));
  // AH-218: an Excel error outside every table: a #REF! on a summary block was only "not checked", or, alone on its row,
  // not said at all. One inside a table is the scan's to say
  const errors = [];
  for (let r = 0; r < H; r++) for (let c = 0; c < W; c++)
    if (Object.hasOwn(EXCEL_ERRORS, values[r][c]) && !tables.some((t) => t.r1 <= r && r <= t.r2 && t.c1 <= c && c <= t.c2)) errors.push([a1Of({ r1: r + r0, r2: r + r0, c1: c + c0, c2: c + c0 }), values[r][c]]);
  return { tables: out, unread, errors };
}

// Pure: a table as the engine reads it: each merged label filled down, each subtotal or notes row blank -> {rows, calc}
export function sentOf(t) {
  if (!t.fills?.length && !t.layout?.length) return { rows: t.rows, calc: t.calc };
  const rows = t.rows.map((r) => [...r]), calc = t.calc && t.calc.map((r) => [...r]);
  for (const [i, j, v] of t.fills || []) rows[i][j] = v;
  for (const i of t.layout || []) rows[i] = rows[i].map(() => "");
  return { rows, calc };
}

// AH-213: the cells Excel itself says break their data validation (a value outside its drop-down list), as areas of the
// sheet (areaOf) -> [[i, j]]: row i and column j of a table as the engine reads it (local), at most INVALID
export const INVALID = 1000; // the engine takes at most this many a table (server.INVALID)
export function invalidIn(t, areas) {
  const out = [], top = t.startRow + 1, last = top + t.rows.length - 1, right = t.startCol + t.columns.length - 1;
  for (const a of areas || []) for (let r = Math.max(a.r1, top); r <= Math.min(a.r2, last); r++)
    for (let c = Math.max(a.c1, t.startCol); c <= Math.min(a.c2, right); c++) {
      if (out.length === INVALID) return out;
      out.push([r - top, c - t.startCol]);
    }
  return out;
}

// Pure: what the reader could not read, said once: "Cells A18:B23 and A25 on this sheet were not checked: they hold no
// table Arcas can read." At most 3 named
export function unreadSaid(unread) {
  if (!unread?.length) return "";
  const named = unread.slice(0, 3), more = unread.length - named.length, cell = unread.length === 1 && !named[0].includes(":");
  const list = more ? `${named.join(", ")} and ${more} more` : named.length > 1 ? `${named.slice(0, -1).join(", ")} and ${named.at(-1)}` : named[0];
  return cell ? `Cell ${list} on this sheet was not checked: it holds no table Arcas can read.`
    : `Cells ${list} on this sheet were not checked: they hold no table Arcas can read.`;
}

// Pure: AH-218: the Excel errors no table holds ([A1, error]), said once, at most 3 named
export function errorsSaid(errors) {
  if (!errors?.length) return "";
  if (errors.length === 1) return `Cell ${errors[0][0]} on this sheet shows ${errors[0][1]}, outside any table Arcas checks: ${EXCEL_ERRORS[errors[0][1]]}.`;
  const named = errors.slice(0, 3).map(([a, e]) => `${a} (${e})`), more = errors.length - named.length;
  const list = more ? `${named.join(", ")} and ${more} more` : `${named.slice(0, -1).join(", ")} and ${named.at(-1)}`;
  return `Cells ${list} on this sheet show Excel errors, outside any table Arcas checks.`;
}

// Pure: the rows (0-based in the used range, [first, count]) whose number formats a table needs that were not read: its
// header's two rows and first 20 data rows, where a table starts below the top `have` rows read (tableAt tells a date
// column by its first 20 filled cells' formats)
export function formatRows(tables, r0, have) {
  return tables.map((t) => [Math.max(have, t.startRow - r0 - 1), t.startRow - r0 + 21]).filter(([a, b]) => b > a)
    .map(([a, b]) => [a, b - a]);
}

// The pane reads a sheet of several tables as one object: its rows one after another (row g), each table a view of them
// at an offset o, so that its startRow + 2 + g is still row g's sheet row and every place the pane turns a row into a cell
// stays as it was. A sheet of one table is that table itself, unchanged.
// Pure: tables -> the sheet as the pane holds it
export function asSheet(tables, extra = {}) {
  if (tables.length === 1) return { ...tables[0], ...extra };
  const rows = [], calc = [], views = [];
  for (const t of tables) {
    const o = rows.length;
    views.push({ ...t, sheet: extra.sheet, startRow: t.startRow - o, o, n: t.rows.length, rows, calc });
    rows.push(...t.rows);
    calc.push(...(t.calc || t.rows.map((r) => r.map(() => null))));
  }
  return { ...extra, tables: views, rows, calc, names: Object.assign({}, ...tables.map((t) => t.names)) };
}

// Pure: the table that holds row g of a sheet as the pane holds it (one table: the sheet)
export const place = (s, g) => (s?.tables ? s.tables.find((t) => g >= t.o && g < t.o + t.n) || s.tables[0] : s);

// Pure: a table as the engine reads it: its own rows only, at its real startRow (row g of the sheet is its row g - o)
export const local = (t) => (t.o === undefined ? t
  : { ...t, rows: t.rows.slice(t.o, t.o + t.n), calc: t.calc.slice(t.o, t.o + t.n), startRow: t.startRow + t.o, o: undefined, n: undefined });

// Pure: the biggest table, the one the AI checks of a whole table read (Check words, Check subject rules, Before you scan)
export const biggest = (s) => local(s?.tables ? [...s.tables].sort((a, b) => b.n - a.n)[0] : s);

// Pure: a cell or a one-row range Excel gave ("C7", "B7:D7", "Sheet1!C7") -> the sheet's row g whose table holds it, or null
export function rowAt(s, address) {
  if (!s?.tables) return rowFromAddress(address, s.startRow);
  const m = /^(?:.*!)?\$?([A-Z]*)\$?(\d+)(?::\$?[A-Z]*\$?(\d+))?$/i.exec(String(address));
  if (!m || (m[3] && m[3] !== m[2])) return null;
  const col = m[1] ? [...m[1].toUpperCase()].reduce((k, ch) => k * 26 + ch.charCodeAt(0) - 64, 0) - 1 : null;
  const t = s.tables.find((v) => { const g = +m[2] - v.startRow - 2; return g >= v.o && g < v.o + v.n && (col === null || (col >= v.startCol && col < v.startCol + v.columns.length)); });
  return t ? +m[2] - t.startRow - 2 : null;
}
