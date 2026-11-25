import { ACCEPTED_KEY, IGNORED_KEY } from "../constants/index.js";
import { hash } from "./decisions.js";

// AH-205 (John, 2026-11-19: "learn really fast so the tool can fully help the user in one session"): a Dismiss teaches
// the sheet at once, and "Stop checking ..." mutes one kind of check in one column. Both live in the workbook (its
// document settings, like the decisions), cleared by Forget, and go with every /scan this sheet sends: Find problems and
// Check as you work build it in one place (scan.scanRequest). Nothing of it leaves the PC.
// Kept: {sheet: [[column, code of a value]]} for what a Dismiss taught, a code never the value (decisions.js's hash), and
// {sheet: [[kind, column]]} for the checks stopped, newest last, capped per sheet and SHEETS sheets.
export const PER_SHEET = 2000;
export const SHEETS = 8;
export const SENT = 500; // the engine takes at most this many of each (server.LEARNED)...
export const TEXT = 200; // ...each column and value at most this long (server.LEARNED_TEXT): a longer one is never learned
// the engine's checks of one cell's own value (pipeline.ONE_CELL): a value dismissed there is fine in that column. Never
// a sum, an order, a duplicate, a blank or a formula: the same value is wrong in the next row
export const ONE_CELL = new Set(["limits", "spelling", "type", "code", "far_date", "date_form", "lost_zero", "placeholder",
  "gene_date", "fraction", "whole_number", "named_bound", "shifted", "validation", "scale"]);
// each kind the engine names (pipeline.KINDS), in the words "Stop checking ... in Units" says it
export const KIND_WORDS = { duplicate: "duplicates", type: "text in numbers", blank: "blanks", placeholder: "placeholders",
  code: "codes for no value", far_date: "dates far off", sum: "totals", spelling: "spelling", lost_zero: "leading zeros",
  date_form: "how dates are written", formula: "formulas", order: "which value is higher", gene_date: "gene names as dates",
  date_order: "which date comes first", record: "records", balance: "balances", scale: "sizes", key: "values against their code",
  own_scale: "sizes", shifted: "values in the wrong column", fraction: "percentages", whole_number: "decimals",
  named_bound: "what the column name allows", repeated_column: "copied columns", limits: "the usual range", series: "jumps",
  combination: "unusual mixes", subtotal: "subtotals", validation: "drop-down lists",
  group: "which group a row is under", rule: "subject rules" };
const CODE = /^[0-9a-z]{1,11}$/;
const text = (x) => typeof x === "string" && x.length <= TEXT;

// Pure: whatever the workbook holds -> a clean book of pairs. A crafted workbook can carry anything here: only pairs whose
// first passes `first` and whose second is a code (codes) or a column (kinds). Null-prototype: a sheet may be "__proto__"
export function asLearned(v, first, second) {
  const book = Object.create(null);
  if (!v || typeof v !== "object" || Array.isArray(v)) return book;
  for (const [sheet, pairs] of Object.entries(v).slice(-SHEETS)) {
    if (!Array.isArray(pairs)) continue;
    const kept = pairs.slice(-PER_SHEET).filter((p) => Array.isArray(p) && p.length === 2 && first(p[0]) && second(p[1])).map((p) => [p[0], p[1]]);
    if (kept.length) book[sheet] = kept;
  }
  return book;
}
const asCodes = (v) => asLearned(v, text, (c) => typeof c === "string" && CODE.test(c));
const asKinds = (v) => asLearned(v, (k) => Object.hasOwn(KIND_WORDS, k), text);

// Pure: the book with these pairs added (once each, newest last) or, with `drop`, taken out; capped
export function learnIn(book, sheet, pairs, drop = false) {
  const key = (p) => JSON.stringify(p), gone = new Set(pairs.map(key));
  const added = drop ? [] : [...new Map(pairs.map((p) => [key(p), p])).values()];
  const rows = [...(book[sheet] || []).filter((p) => !gone.has(key(p))), ...added].slice(-PER_SHEET);
  const out = Object.assign(Object.create(null), book);
  delete out[sheet]; // this sheet becomes the newest
  if (rows.length) out[sheet] = rows;
  const sheets = Object.keys(out);
  sheets.slice(0, Math.max(0, sheets.length - SHEETS)).forEach((s) => delete out[s]);
  return out;
}

// Pure: what a Dismiss of this row teaches: [column, code] for each one-cell check of its value (kinds: the engine's
// [kind, column] pairs), the cell as the scan read it. A blank, a too-long text or a column the sheet no longer has: nothing
export function taught(kinds, columns, row) {
  const out = [];
  for (const [kind, col] of Array.isArray(kinds) ? kinds : []) {
    const j = columns.indexOf(col), v = row[j];
    if (!ONE_CELL.has(kind) || j < 0 || !text(col) || v === "" || v === null || v === undefined || !text(String(v))) continue;
    const pair = [col, hash(String(v))];
    if (!out.some((p) => p[0] === pair[0] && p[1] === pair[1])) out.push(pair);
  }
  return out;
}

// Pure: the row's first check the card can stop: [kind, column], or null
export const stoppable = (kinds) => (Array.isArray(kinds) ? kinds : []).find(([k, c]) => Object.hasOwn(KIND_WORDS, k) && text(c)) || null;

// Pure: a sheet as read and what it learned -> the /scan's `learned`, or null: each accepted code turned back into the
// [column, value] it was made from by hashing that column's values (only a value still in the sheet can match), at most
// SENT of each
export function learnedOf(s, codes = [], kinds = []) {
  const accept = [], want = new Map();
  for (const [col, code] of codes) want.set(col, (want.get(col) || new Set()).add(code));
  for (const [col, wanted] of want) {
    const j = s.columns.indexOf(col);
    if (j < 0) continue;
    const seen = new Set();
    for (const row of s.rows) {
      const v = row[j], t = v === null || v === undefined ? "" : String(v);
      if (t === "" || seen.has(t) || !text(t)) continue;
      seen.add(t);
      if (wanted.has(hash(t))) accept.push([col, t]);
    }
  }
  const ignore = kinds.filter(([, col]) => s.columns.includes(col));
  return accept.length || ignore.length ? { accept: accept.slice(-SENT), ignore: ignore.slice(-SENT) } : null;
}

const settings = () => Office.context.document.settings;

// This sheet's learned values and stopped checks, as the workbook holds them now -> the /scan's `learned`
export const learnedFor = (s) => learnedOf(s, asCodes(settings().get(ACCEPTED_KEY))[s.sheet], asKinds(settings().get(IGNORED_KEY))[s.sheet]);

// Set, never saved here: the Dismiss that learns saves the workbook's settings once, with its decision. -> the pairs that
// were new, so a Dismiss put back takes out only what it taught, never what an earlier one did. Each key set by its own
// name: selfcheck holds every key the pane sets to Forget's list
function learn(book, sheet, pairs, drop, set) {
  const had = new Set((book[sheet] || []).map((p) => JSON.stringify(p)));
  const fresh = drop ? pairs : pairs.filter((p) => !had.has(JSON.stringify(p)));
  if (fresh.length) set(learnIn(book, sheet, fresh, drop));
  return fresh;
}
export const teach = (sheet, pairs, drop = false) =>
  learn(asCodes(settings().get(ACCEPTED_KEY)), sheet, pairs, drop, (book) => settings().set(ACCEPTED_KEY, book));
export const stopKind = (sheet, pairs, drop = false) =>
  learn(asKinds(settings().get(IGNORED_KEY)), sheet, pairs, drop, (book) => settings().set(IGNORED_KEY, book));
