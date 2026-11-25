import { RULES_KEY } from "../constants/index.js";

// AH-217 (John, 2026-11-21: "AI proposes, the no-AI engine verifies, then enforces locally for free"): a rule Check
// subject rules found holding on the sheet is kept in the workbook (its kind and the headers it names, never a cell and
// never the AI's words), and every /scan of that sheet sends it back (scan.scanRequest: Find problems and Check as you
// work), where the engine judges it again on that scan's rows. No AI call, nothing leaves the PC. Cleared by Forget.
// Kept: {sheet: [rule]}, each press of Check subject rules replacing its sheet's, at most MAX a sheet and SHEETS sheets.
export const MAX = 20; // rules a sheet keeps: the engine takes at most this many (client.MAX_RULES)
export const SHEETS = 8;
export const HEADER = 100; // characters of a header (rules.HEADER): the AI was never sent a longer one
const LIST = 200; // headers a rule's list names: /rules sends at most this many (client.SENT)
const NAMES = ["target", "first", "then", "value", "when", "after", "id", "parent"], LISTS = ["plus", "minus", "factors"];
const KINDS = new Set(["sum", "product", "order", "zero_after", "rollup"]);
const head = (h) => typeof h === "string" && h.length <= HEADER;

// Pure: a rule as /rules answered it, or as a workbook holds it -> {kind, and the headers it names}, or null. A crafted
// workbook can carry anything here: nothing else is kept (never "why", "said" or a count)
export function ruleOf(r) {
  if (!r || typeof r !== "object" || !KINDS.has(r.kind)) return null;
  const out = { kind: r.kind };
  for (const k of NAMES) {
    if (r[k] === null || r[k] === undefined) continue;
    if (!head(r[k])) return null;
    out[k] = r[k];
  }
  for (const k of LISTS) {
    if (r[k] === null || r[k] === undefined) continue;
    if (!Array.isArray(r[k]) || r[k].length > LIST || !r[k].every(head)) return null;
    if (r[k].length) out[k] = [...r[k]];
  }
  return out;
}

// Pure: what /rules answered -> the rules that held on the sheet, as kept. One that did not hold, or had too few rows to
// tell, is never kept
export const heldOf = (out) => (Array.isArray(out?.rules) ? out.rules : []).filter((r) => r?.holds === true).map(ruleOf).filter(Boolean).slice(0, MAX);

// Pure: whatever the workbook holds -> a clean book {sheet: [rule]}. Null-prototype: a sheet may be named "__proto__"
export function asRules(v) {
  const book = Object.create(null);
  if (!v || typeof v !== "object" || Array.isArray(v)) return book;
  for (const [sheet, list] of Object.entries(v).slice(-SHEETS)) {
    const kept = Array.isArray(list) ? list.slice(0, MAX).map(ruleOf).filter(Boolean) : [];
    if (kept.length) book[sheet] = kept;
  }
  return book;
}

// Pure: the book with this sheet's rules replaced (none: the sheet taken out), the sheet newest, at most SHEETS sheets
export function keepIn(book, sheet, rules) {
  const out = Object.assign(Object.create(null), book);
  delete out[sheet];
  if (rules.length) out[sheet] = rules.slice(0, MAX);
  const sheets = Object.keys(out);
  sheets.slice(0, Math.max(0, sheets.length - SHEETS)).forEach((s) => delete out[s]);
  return out;
}

const settings = () => Office.context.document.settings;

// This sheet's kept rules, as the workbook holds them now -> the /scan's `rules`
export const rulesFor = (sheet) => asRules(settings().get(RULES_KEY))[sheet] || [];

// Keep the rules that held on this press for this sheet, in place of the ones before, and save the workbook's settings
export function keepRules(sheet, rules) {
  settings().set(RULES_KEY, keepIn(asRules(settings().get(RULES_KEY)), sheet, rules));
  settings().saveAsync();
}
