import { LIVE_KEY, SOUND_KEY } from "../constants/index.js";
import { state } from "../hooks/use-state.js";
import { $, show } from "../utils/dom.js";
import { notice } from "../components/progress.js";
import { n } from "../utils/text.js";
import { cellAt, colIndex, colLetter, spots } from "../utils/sheet.js";
import { readSheet, showCell } from "../services/excel.js";
import { flaggedRows, plainReason, runScan, scanAll, scanRequest } from "./scan.js";
import { act } from "../hooks/use-action.js";
import { openFix } from "../pages/fix.js";
import { place } from "../utils/layout.js";
import { copiedSaid, dropTab, newPairs } from "./tabs.js";

// AH-181 (John, 2026-11-17): check alongside the user as they type, on any tab, and say at once when a cell they changed
// looks wrong: a note in the pane with our crest, a short chime, and "Show me". Office.js cannot draw near the pointer or
// over the grid, so the note lives in the pane. It all runs on this PC.
// AH-220 (John, 2026-11-25: "runs continuously from open until Excel closes, even with the task pane closed"): with Office's
// shared runtime (manifest Runtimes, lifetime="long", SharedRuntime 1.1) this page and its listeners outlive a closed pane,
// and a finding brings the pane back to show its note. Arcas never asks Office to start it with a workbook: only a
// workbook whose pane was opened has a page to listen. Without SharedRuntime 1.1 the page stops with the pane, as before
// QUIET: a sheet is checked this long after its last edit, so typing a column of numbers is one check, not one a cell.
// LIVE_ROWS: a bigger sheet would make every edit wait for a full scan; Find problems still checks it
export const QUIET = 1500, LIVE_ROWS = 20000;

export const liveOn = () => { try { return localStorage.getItem(LIVE_KEY) !== "0"; } catch { return true; } };
export const soundOn = () => { try { return localStorage.getItem(SOUND_KEY) !== "0"; } catch { return true; } };
// AH-220: a pane closed this soon after Arcas brought it back means "leave me be": Arcas does not bring it back again
// until the person opens it and closes it themselves
export const NOT_AGAIN = 60000;
const setOn = (key, on) => { try { localStorage.setItem(key, on ? "1" : "0"); } catch { /* private mode: stays on */ } };

// Pure: an edit never checked: our own write (Accept, Undo, auto-fix: Excel names its trigger from 1.14), a co-author's
// edit coming in, or anything while a scan or an action of ours runs (an Excel older than 1.14 names no trigger)
export const ignored = (e, busy) => busy || e.source === "Remote" || e.triggerSource === "ThisLocalAddin";
// Pure: a sheet of this many used rows is checked as you type
export const liveable = (rows) => rows <= LIVE_ROWS;

// Pure: is an A1 cell inside an address Excel gave ("B12", "B2:B41", "Sheet!$B$2", "C:C", "5:7", "A1:B2, D4")?
export function inRange(address, cell) {
  const at = cellAt(cell);
  if (!at || typeof address !== "string") return false;
  const within = (v, x, y) => v >= Math.min(x, y) && v <= Math.max(x, y);
  return address.split(",").some((area) => {
    const ends = area.trim().replace(/^.*!/, "").replace(/\$/g, "").split(":").map((x) => /^([A-Z]*)(\d*)$/i.exec(x));
    if (!area.trim() || ends.some((m) => !m)) return false;
    const [a, b = a] = ends;
    return (!a[1] || within(at.col, colIndex(a[1]), colIndex(b[1] || a[1]))) && (!a[2] || within(at.row, +a[2], +(b[2] || a[2])));
  });
}

// Pure (AH-220): bring the closed pane back for this note? Only for a finding (a note that rings, never "nothing unusual"
// or a sheet too big), with Check as you work on, a shared runtime, the pane closed, not left alone, once an edit burst
export const reopens = (p) => p.shared && p.hidden && p.on && p.ring && !p.alone && p.burst !== p.last;
// Pure (AH-220): closed within NOT_AGAIN of Arcas bringing it back (shownAt 0: the person opened it)
export const leftAlone = (shownAt, closedAt) => shownAt > 0 && closedAt - shownAt < NOT_AGAIN;

// Pure: a cell a flagged row's reasons name, as highlight.js colours it (s: the row's own table, utils/layout.js place)
const cellOf = (r, s, j) => colLetter(s.startCol + j) + (s.startRow + 2 + r.i);

// Pure: the rows a check flagged in a cell that was changed (edited: Excel's addresses), never one fixed or dismissed:
// surest first, then biggest, each with that cell. One already flagged before the edit counts too: John (2026-11-17)
// wants every change answered, wrong or "nothing unusual", and a cell retyped still wrong said nothing at all
export function findingsAt(rows, s, decided = {}, edited = []) {
  return flaggedRows(rows).filter((r) => !decided[r.i]).flatMap((r) => {
    const t = place(s, r.i), at = spots(r, t.columns), k = at.find((j) => edited.some((a) => inRange(a, cellOf(r, t, j))));
    // spots: every cell the row's reasons name, [column, cell], so the note can name the wrong one (AH-228 P-13)
    return k === undefined ? [] : [{ ...r, cell: cellOf(r, t, k), column: t.columns[k], spots: at.map((j) => [t.columns[j], cellOf(r, t, j)]) }];
  });
}

// Pure: the reason as the list says it (its line about the changed cell's column, else its first: a typed 77777 broke its
// row's Total too, and "Total 103.48 does not add up" came first), and the cell that line is about. AH-228 P-13: the note
// named the cell changed ("cell D40: ... Units 99999" where Units is C40)
export function wrongAt(f, names = {}) {
  const shown = (c) => String(names[c] || c), lines = plainReason(f.reason, names).split("\n"), col = shown(f.column);
  const why = lines.find((l) => col && l.startsWith(`${col} `)) || lines[0];
  const at = (f.spots || []).filter(([c]) => why.startsWith(`${shown(c)} `)).sort((a, b) => shown(b[0]).length - shown(a[0]).length)[0];
  return [why, at ? at[1] : f.cell];
}

// Pure: the note's sentence: the cell changed, the cell that looks wrong, the reason, and how many more
export function noteSaid(sheet, f, more, names = {}) {
  const [why, wrong] = wrongAt(f, names), look = f.severity === "Low" ? "is worth a check" : "looks wrong";
  const head = wrong === f.cell ? `You changed ${f.cell} on ${sheet}. It ${look}` : `You changed ${f.cell}. ${wrong} on ${sheet} ${look}`;
  return `${head}: ${why}${/[.!?]$/.test(why) ? "" : "."}${more ? ` And ${n(more)} more in what you changed.` : ""}`;
}

// AH-218 (John's master spec: no nagging on the row being typed): a finding only about a row's whole (a blank not filled
// yet, a total whose parts are still coming, a record's lines, a duplicate, a label's columns) waits while the selected
// cell is still on that row of that sheet, and is said the moment the selection leaves it, or after HOLD: delayed, never
// dropped ("every change is answered", John 2026-11-17). A slip in one cell's own value (a typo, a spelling, a value past
// its limits) is said at once. AH-217's rule: a row against a subject rule the sheet kept (Net = Debit - Credit) is the row's
// arithmetic, half typed until its last cell is
export const ROW_KINDS = new Set(["blank", "sum", "record", "balance", "subtotal", "duplicate", "group", "rule"]), HOLD = 20000;

// Pure: is sheet row `row` inside a selection's address, on any column? ("C12", "$B$11:$D$13", "12:12", "Sheet!C12")
export const onRow = (address, row) => typeof address === "string"
  && inRange(address.replace(/\$/g, "").replace(/(^|[!:,\s])[A-Z]+(?=\d)/gi, "$1"), `A${row}`);

// Pure: hold this check's note back? Every finding is only about its row's whole, each on the row the selection is on,
// on this sheet (sel: the last selection heard, {id, address})
export const heldBack = (found, sel, id) => found.length > 0 && sel?.id === id
  && found.every((f) => f.kinds?.length && f.kinds.every(([k]) => ROW_KINDS.has(k)) && onRow(sel.address, cellAt(f.cell)?.row));

// Pure: a quiet word that the changed cells were checked and nothing there looks wrong (John, AH-181: the user sees Arcas
// checked), each address once, at most 3 named
export function checkedSaid(sheet, addresses) {
  const at = [...new Set(addresses.filter(Boolean))], named = at.slice(0, 3).join(", ");
  return `Checked ${at.length > 3 ? `${named} and ${n(at.length - 3)} more` : named} on "${sheet}": nothing unusual.`;
}

const edits = new Map(); // tab id -> the addresses changed since its last check
const big = new Set(); // tabs said too big to check as you type, once each
const waiting = new Map(); // AH-218: tab id -> a note held back while its row is being typed: {cells, rows, lines, b, where, timer}
let timer = 0, running = false, tries = 0, audio = null, target = null, selected = null;
// AH-220: the pane's state as Office tells it, and each edit burst (the edits one check takes together) numbered
let shared = false, hidden = false, alone = false, shownAt = 0, burst = 0, lastBurst = -1;

function heard(e) {
  if (!liveOn() || ignored(e, state.working)) return;
  dropTab(e.worksheetId); // its numbers changed: read again for the copied tabs
  const held = waiting.get(e.worksheetId); // AH-218: a held note's cells are judged again with this edit, never lost
  if (held) clearTimeout(held.timer), waiting.delete(e.worksheetId);
  edits.set(e.worksheetId, [...(held?.cells || []), ...(edits.get(e.worksheetId) || []), e.address]);
  clearTimeout(timer);
  timer = setTimeout(checkAll, QUIET);
}

// AH-218: the selection moved (any tab): a note held for a row it left is said now
function picked(e) {
  selected = { id: e.worksheetId, address: e.address };
  for (const [id, w] of waiting) if (!(id === selected.id && w.rows.every((r) => onRow(selected.address, r)))) release(id);
}

function release(id) {
  const w = waiting.get(id);
  if (!w) return;
  clearTimeout(w.timer);
  waiting.delete(id);
  say(w.lines, w.where, true, w.b);
}

// One check at a time, one sheet after another; edits made during a check wait for the next one
async function checkAll() {
  if (running) return;
  if (state.working) return void (timer = setTimeout(checkAll, QUIET)); // a scan or an action of ours first
  running = true;
  try {
    const now = [...edits], b = ++burst;
    edits.clear();
    for (const [id, cells] of now) await check(id, cells, b).catch((e) => console.warn("check as you work", e));
  } finally {
    running = false;
    if (edits.size) timer = setTimeout(checkAll, QUIET);
  }
}

// The same /scan a Find problems sends, quietly: no skeleton, no list, no highlight, no progress
async function check(id, cells, b) {
  const s = await readSheet(() => {}, Infinity, id, liveable);
  if (!s) return;
  if (s.big) {
    if (!big.has(s.sheet)) say([`Sheet "${s.sheet}" has more than ${n(LIVE_ROWS)} rows, too many to check as you type. Find problems still checks it.`], { sheet: s.sheet }, false);
    big.add(s.sheet);
    return;
  }
  big.delete(s.sheet);
  const { decided, requests } = await scanRequest(s, false);
  const body = await scanAll(s, requests);
  const found = findingsAt(body.rows, s, decided, cells);
  const pairs = await newPairs(s.sheet).catch(() => []);
  const lines = [found.length ? noteSaid(s.sheet, found[0], found.length - 1, s.names) : "", ...pairs.map(copiedSaid)].filter(Boolean);
  if (!pairs.length && heldBack(found, selected, id)) { // AH-218: the row is still being typed: said when it is left
    const rows = found.map((f) => cellAt(f.cell).row);
    waiting.set(id, { cells, rows, lines, b, where: whereOf(s, found[0]), timer: setTimeout(() => release(id), HOLD) });
  } else if (lines.length) say(lines, found.length ? whereOf(s, found[0]) : { sheet: pairs[0].sheet }, true, b);
  // nothing flagged in the changed cells: said in the notice, with no sound, never over a note still showing
  else if ($("live-note").hidden) notice(checkedSaid(s.sheet, cells));
}

// Show me selects the cell that looks wrong; i and rows: the finding's row and the sheet's size, to find its card (P-14)
const whereOf = (s, f) => ({ sheet: s.sheet, cell: wrongAt(f, s.names)[1], i: f.i, rows: s.rows.length });

// Pure (AH-228 P-14): the list holds this row when it was made on this sheet as it is now sized, and lists that row
export const inList = (where, scan) => where?.i !== undefined && scan.sheet === where.sheet && scan.rows === where.rows && !!scan.order?.includes(where.i);

const listed = () => ({ sheet: state.lastScan?.sheet, rows: state.lastScan?.rows.length, order: state.order });

// The note stays until it is closed or a newer one takes its place
function say(lines, where, ring = true, b = burst) {
  target = where;
  $("live-text").replaceChildren(...lines.map((t) => Object.assign(document.createElement("p"), { textContent: t })));
  // AH-228 P-14: the next step after Show me: the row's card, as a list row opens it, or else a check of the whole sheet
  $("live-more").textContent = inList(where, listed()) ? "Open its card" : "Check the whole sheet";
  show("live-note");
  if (ring) chime();
  if (reopens({ shared, hidden, on: liveOn(), ring, alone, burst: b, last: lastBurst })) bringBack(b);
}

// AH-220: the pane comes back with the note already in it, as it shows today. A refusal leaves the note for the next open
async function bringBack(b) {
  lastBurst = b;
  try {
    await Office.addin.showAsTaskpane();
    shownAt = Date.now();
  } catch { /* the note waits in the pane */ }
}

// AH-220: Office says when the pane is closed or opened. Closed soon after Arcas brought it back: left alone, until the
// person opens it and closes it again themselves
function seen(e) {
  hidden = e.visibilityMode === "Hidden";
  if (hidden) alone = leftAlone(shownAt, Date.now()), shownAt = 0;
}

// Browsers let a page make sound only after a press in it: the first press or key in the pane opens the audio
function wake() {
  try {
    audio ||= new (globalThis.AudioContext || globalThis.webkitAudioContext)();
    if (audio.state === "suspended") audio.resume().catch(() => {});
  } catch {
    audio = null; // no audio here: the note says it all
  }
}

// A soft two-note chime of about 150 ms, made here: no sound file to load
function chime() {
  if (!soundOn() || !audio) return;
  try {
    const t = audio.currentTime;
    for (const [hz, at] of [[784, 0], [1047, 0.07]]) {
      const o = audio.createOscillator(), g = audio.createGain();
      o.type = "sine";
      o.frequency.value = hz;
      g.gain.setValueAtTime(0.0001, t + at);
      g.gain.exponentialRampToValueAtTime(0.08, t + at + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + at + 0.08);
      o.connect(g).connect(audio.destination);
      o.start(t + at);
      o.stop(t + at + 0.09);
    }
  } catch { /* no sound: the note says it all */ }
}

// Excel tells the pane every edit on every tab, new tabs included (ExcelApi 1.9). Refused while a cell is being typed in
// (AH-58): asked again a few times
async function listen() {
  if (Office.context.requirements?.isSetSupported?.("ExcelApi", "1.9") === false) {
    for (const id of ["live", "live-sound"]) $(id).closest("label").hidden = true;
    $("live-hint").textContent = "This version of Excel is too old to check as you work. Find problems still checks any sheet.";
    return;
  }
  try {
    await Excel.run(async (ctx) => {
      ctx.workbook.worksheets.onChanged.add(heard);
      ctx.workbook.worksheets.onSelectionChanged.add(picked); // AH-218 (ExcelApi 1.9, as onChanged)
      await ctx.sync();
    });
  } catch {
    if (++tries < 12) setTimeout(listen, 5000);
  }
}

export function initLive() {
  shared = Office.context.requirements?.isSetSupported?.("SharedRuntime", "1.1") === true;
  if (shared) Promise.resolve().then(() => Office.addin.onVisibilityModeChanged(seen)).catch(() => {});
  else $("live-closed").textContent = "This Excel checks your edits only while Arcas is open.";
  $("live").checked = liveOn();
  $("live-sound").checked = soundOn();
  // AH-228 P-29: Play a sound is off, drawn off, while Check the cells I change is
  const sound = () => { $("live-sound").disabled = !$("live").checked; };
  sound();
  $("live").addEventListener("change", () => { setOn(LIVE_KEY, $("live").checked); sound(); });
  $("live-sound").addEventListener("change", () => setOn(SOUND_KEY, $("live-sound").checked));
  for (const type of ["pointerdown", "keydown"]) document.addEventListener(type, wake, { capture: true });
  $("live-show").addEventListener("click", () => { if (target) showCell(target.sheet, target.cell).catch(() => {}); });
  $("live-close").addEventListener("click", () => show("live-note", false));
  $("live-more").addEventListener("click", act(async () => {
    const to = target;
    show("live-note", false);
    if (inList(to, listed())) return openFix(to.i, true, null, true);
    if (to?.cell) await showCell(to.sheet, to.cell).catch(() => {}); // the tab in front is the one Find problems checks
    await runScan(true, true);
  }));
  listen();
}
