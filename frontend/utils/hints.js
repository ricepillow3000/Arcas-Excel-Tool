import { colLetter } from "./sheet.js";
import { local } from "./layout.js";

// AH-215 (John, 2026-11-21: "the safe agent"): Read layout with AI. The engine sends the AI each table's layout alone,
// never a cell's value, and answers with hints: rows that are no records of their table (an input, a note, a rate worked
// out from other rows, a subtotal, a separator, a second header row). Kept in the pane's memory for this session only,
// for the sheet they were read on, they change that sheet's next Find problems and Check as you work: the rows go to the
// engine blank, as the layout reader's own layout rows do, and Find problems says so. No column ever sits out a check
// because of the AI (AH-215: hinted columns moved nothing on the bench). All pure: the bench runs them too.

// a table found again on the next read is the same table: where it sits and its headers (a row typed under it keeps it)
export const keyOf = (t) => JSON.stringify([t.startRow, t.startCol, t.columns]);

// Pure: a sheet as the pane holds it -> the /layout body: each table the layout reader found, its own rows as typed
export function layoutRequest(s) {
  return { tables: (s.tables || [s]).map(local).map((t) => ({ columns: t.columns, rows: t.rows,
    formulas: t.calc?.some((r) => r.some(Boolean)) ? t.calc : null, start_row: t.startRow, start_col: t.startCol })) };
}

// Pure: the engine's answer for these tables (sent in this order) -> {table key: {rows: [[first, last, kind, why]]}} for
// the tables the AI named
export function hintsOf(s, out) {
  const tabs = (s.tables || [s]).map(local), book = Object.create(null);
  const of = (k) => (book[keyOf(tabs[k])] ||= { rows: [] });
  for (const h of out.rows || []) if (tabs[h.table]) of(h.table).rows.push([h.first, h.last, h.kind, h.why]);
  return book;
}

// Pure: a table and its hints -> the table with the hinted rows among its layout rows (sentOf sends them blank)
export function hinted(t, hint) {
  if (!hint?.rows.length) return t;
  const rows = new Set(t.layout || []);
  for (const [a, b] of hint.rows) for (let i = a; i <= Math.min(b, t.rows.length - 1); i++) rows.add(i);
  return { ...t, layout: [...rows].sort((p, q) => p - q) };
}

const ROWS = { parameter: ["an input", "inputs"], note: ["a note", "notes"], ratio: ["a rate", "rates"], subtotal: ["a subtotal", "subtotals"],
  separator: ["a separator", "separators"], header: ["a header row", "header rows"] };

// Pure: sheet rows -> "4 to 6, 12 and 30"
function runsOf(rows) {
  const runs = [];
  for (const r of [...new Set(rows)].sort((a, b) => a - b)) (runs.length && runs.at(-1)[1] === r - 1 ? (runs.at(-1)[1] = r) : runs.push([r, r]));
  const said = runs.map(([a, b]) => (a === b ? `${a}` : `${a} to ${b}`));
  return said.length > 1 ? `${said.slice(0, -1).join(", ")} and ${said.at(-1)}` : said[0];
}

// Pure: what the hints changed on this sheet's tables, said after Find problems: one line a kind of row (its sheet rows).
// "The AI read rows 4 to 6 on Budget as rates: they were not checked."
export function hintsSaid(sheet, tabs, book) {
  const rows = {};
  for (const t of tabs) {
    const hint = book?.[keyOf(t)];
    for (const [a, b, kind] of hint?.rows || []) for (let i = a; i <= Math.min(b, t.rows.length - 1); i++) (rows[kind] ||= []).push(t.startRow + 2 + i);
  }
  return Object.keys(ROWS).filter((k) => rows[k]).map((k) => { const one = new Set(rows[k]).size === 1;
    return `The AI read row${one ? "" : "s"} ${runsOf(rows[k])} on ${sheet} as ${ROWS[k][one ? 0 : 1]}: ${one ? "it was" : "they were"} not checked.`; });
}

// Pure: what /layout found, as lines under its button, the AI's why as text (never markup), at most cap lines
export function layoutLines(s, out, cap) {
  const tabs = (s.tables || [s]).map(local), lines = [];
  const where = (t) => `${colLetter(t.startCol)}${t.startRow + 1}`;
  (out.sent || []).forEach((n, k) => n < tabs[k].rows.length && lines.push(`Only the first ${n} of ${tabs[k].rows.length} rows of the table at ${where(tabs[k])} were sent.`));
  const k = out.sent?.length;
  if (k < tabs.length) lines.push(k === 1 ? `Only the first of ${tabs.length} tables was sent.` : `Only the first ${k} of ${tabs.length} tables were sent.`);
  for (const h of out.rows || []) {
    const t = tabs[h.table], a = t.startRow + 2 + h.first, b = t.startRow + 2 + h.last;
    lines.push(`${a === b ? `Row ${a}` : `Rows ${a} to ${b}`}: ${ROWS[h.kind][a === b ? 0 : 1]}. The AI says: ${h.why}`);
  }
  lines.push(out.rows?.length ? "Find problems leaves these out of its next check of this sheet, and says so."
    : "The AI found nothing to leave out.");
  return lines.length > cap ? [...lines.slice(0, cap), `+ ${lines.length - cap} more lines.`] : lines;
}
