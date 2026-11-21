import { n } from "../utils/text.js";
import { readTabs } from "../services/excel.js";
import { unreadSaid } from "../utils/layout.js";

// AH-180 (John, 2026-11-17): a neuroscience student copied three data series onto three tabs, one per tab, and pasted
// series 2 again on the third without noticing. Each tab's measures are compared as number sequences, headers ignored on
// purpose: the third tab had its own header over series 2's numbers.
export const MIN_NUMBERS = 10, MIN_DISTINCT = 5;

const rising = (a) => a.every((v, k) => !k || v >= a[k - 1]);

// Pure: a table as utils/sheet.js tableFromGrid gives it -> each column's numbers in row order (blanks and text skipped),
// only a column that measures something: 10+ numbers, 5+ different values (a code or a flag repeats), never rising or
// falling all the way (a time axis or an ID is the same on every tab of a series) and at most half of them formulas (a tab
// built by =Series2!B2 is a copy by design)
export function measures(t) {
  return t.columns.flatMap((_, j) => {
    const nums = [];
    let made = 0;
    t.rows.forEach((r, i) => {
      if (typeof r[j] !== "number") return;
      nums.push(r[j]);
      if (t.calc?.[i]?.[j]) made++;
    });
    const monotone = rising(nums) || rising(nums.map((v) => -v));
    return nums.length >= MIN_NUMBERS && new Set(nums).size >= MIN_DISTINCT && !monotone && 2 * made <= nums.length ? [nums] : [];
  });
}

// Pure: tables [{sheet, columns, rows, calc}] (or {sheet, measured} read before) in workbook order -> each later tab whose
// measures, as a set of number sequences in any column order, are exactly an earlier tab's: {sheet, other, columns, count}
// (the later tab is `sheet`, paired with the first tab it copies)
export function copiedTabs(tables) {
  const keyed = tables.map((t) => {
    const m = t.measured ?? measures(t);
    return { sheet: t.sheet, key: m.map((a) => a.join(",")).sort().join("|"), columns: m.length, count: m.reduce((k, a) => k + a.length, 0) };
  });
  return keyed.flatMap((t, j) => {
    const first = t.columns && keyed.slice(0, j).find((o) => o.key === t.key);
    return first ? [{ sheet: t.sheet, other: first.sheet, columns: t.columns, count: t.count }] : [];
  });
}

// Pure: a copied pair in one plain sentence
export const copiedSaid = (p) => `"${p.sheet}" holds the same ${n(p.count)} numbers as "${p.other}"${p.columns > 1 ? `, in ${n(p.columns)} columns` : ""}, in the same order. ` +
  "If you meant to paste a different series there, the same one went in twice.";

// Pure: the sheet's last used row (1-based) -> a line when it is Excel's last row. A file bigger than Excel holds opens
// cut at that row, with no word: UK health officials lost 15,841 COVID cases in 2020 when a results file reached the
// 65,536 rows of the old .xls format
export const lastRowSaid = (last) => (last === 65536 || last === 1048576
  ? `This sheet's data reaches Excel's last row (${n(last)}). If it came from a bigger file, the rows past it were cut off when it opened.` : "");

// Each tab's measures, kept by its id until that tab changes (features/live.js drops it), so a check as you work reads
// only the tabs it has not read yet; and the pairs said last, so a pair is said once until it goes and comes back
const cache = new Map();
let said = new Set();
const key = (p) => `${p.sheet}\u0000${p.other}`;
export const dropTab = (id) => cache.delete(id);

async function pairsNow() {
  const tabs = await readTabs((id) => cache.has(id));
  for (const t of tabs) if (t.table !== undefined) cache.set(t.id, t.table ? measures(t.table) : []);
  return copiedTabs(tabs.map((t) => ({ sheet: t.sheet, measured: cache.get(t.id) || [] })));
}

// Find problems: every tab read again, and the lines said under the results: the cells no table holds, the cut-off row,
// then the copied pairs (at most 3, the scanned sheet's first). A failure to read the tabs says nothing: the scan has its results
export async function bookNotes(s) {
  // AH-212: what the layout reader could not read on the scanned sheet comes first, said once
  const lines = [unreadSaid(s.unread), lastRowSaid(s.last)].filter(Boolean);
  try {
    cache.clear();
    const pairs = await pairsNow();
    said = new Set(pairs.map(key));
    const mine = (p) => p.sheet === s.sheet || p.other === s.sheet;
    lines.push(...[...pairs.filter(mine), ...pairs.filter((p) => !mine(p))].slice(0, 3).map(copiedSaid));
  } catch { /* the tabs could not be read: nothing said */ }
  return lines;
}

// Check as you work: a pair with the edited tab that was not there at the last look
export async function newPairs(sheet) {
  const pairs = await pairsNow(), fresh = pairs.filter((p) => (p.sheet === sheet || p.other === sheet) && !said.has(key(p)));
  said = new Set(pairs.map(key));
  return fresh;
}
