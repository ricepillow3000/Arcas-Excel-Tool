import { LIVE_KEY, SOUND_KEY, SEV } from "../constants/index.js";
import { state } from "../hooks/use-state.js";
import { $, show } from "../utils/dom.js";
import { notice } from "../components/progress.js";
import { n } from "../utils/text.js";
import { cellAt, colLetter, spots } from "../utils/sheet.js";
import { post } from "../services/api.js";
import { readSheet, showCell } from "../services/excel.js";
import { flaggedRows, plainReason, scanRequest } from "./scan.js";
import { copiedSaid, dropTab, newPairs } from "./tabs.js";

// AH-181 (John, 2026-11-17): check alongside the user as they type, on any tab, and say at once when a cell they changed
// looks wrong: a note in the pane with our crest, a short chime, and "Show me". Office.js cannot draw near the pointer or
// over the grid, so the note lives in the pane. It all runs on this PC, while the pane is open: without a shared runtime
// the pane's code stops when the pane closes.
// QUIET: a sheet is checked this long after its last edit, so typing a column of numbers is one check, not one a cell.
// LIVE_ROWS: a bigger sheet would make every edit wait for a full scan; Find problems still checks it
export const QUIET = 1500, LIVE_ROWS = 20000;

export const liveOn = () => { try { return localStorage.getItem(LIVE_KEY) !== "0"; } catch { return true; } };
export const soundOn = () => { try { return localStorage.getItem(SOUND_KEY) !== "0"; } catch { return true; } };
const setOn = (key, on) => { try { localStorage.setItem(key, on ? "1" : "0"); } catch { /* private mode: stays on */ } };

// Pure: an edit never checked: our own write (Accept, Undo, auto-fix: Excel names its trigger from 1.14), a co-author's
// edit coming in, or anything while a scan or an action of ours runs (an Excel older than 1.14 names no trigger)
export const ignored = (e, busy) => busy || e.source === "Remote" || e.triggerSource === "ThisLocalAddin";
// Pure: a sheet of this many used rows is checked as you type
export const liveable = (rows) => rows <= LIVE_ROWS;

// Pure: is an A1 cell inside an address Excel gave ("B12", "B2:B41", "Sheet!$B$2", "C:C", "5:7", "A1:B2, D4")?
const colOf = (letters) => [...letters.toUpperCase()].reduce((k, ch) => k * 26 + ch.charCodeAt(0) - 64, 0) - 1;
export function inRange(address, cell) {
  const at = cellAt(cell);
  if (!at || typeof address !== "string") return false;
  const within = (v, x, y) => v >= Math.min(x, y) && v <= Math.max(x, y);
  return address.split(",").some((area) => {
    const ends = area.trim().replace(/^.*!/, "").replace(/\$/g, "").split(":").map((x) => /^([A-Z]*)(\d*)$/i.exec(x));
    if (!area.trim() || ends.some((m) => !m)) return false;
    const [a, b = a] = ends;
    return (!a[1] || within(at.col, colOf(a[1]), colOf(b[1] || a[1]))) && (!a[2] || within(at.row, +a[2], +(b[2] || a[2])));
  });
}

// Pure: the cells a flagged row's reasons name, as highlight.js colours them; and every "cell|reason" a check found
const cellOf = (r, s, j) => colLetter(s.startCol + j) + (s.startRow + 2 + r.i);
const cellsOf = (r, s) => spots(r, s.columns).map((j) => cellOf(r, s, j));
export const findingKeys = (rows, s) => new Set(flaggedRows(rows).flatMap((r) => cellsOf(r, s).map((c) => `${c}|${r.reason}`)));

// Pure: the rows a check flagged in a cell that was changed (edited: Excel's addresses) and not found there before for the
// same reason, never one fixed or dismissed: surest first, then biggest, each with that cell
export function newFindings(rows, s, decided = {}, edited = [], before = new Set()) {
  return flaggedRows(rows).filter((r) => !decided[r.i]).flatMap((r) => {
    const k = spots(r, s.columns).find((j) => { const c = cellOf(r, s, j); return edited.some((a) => inRange(a, c)) && !before.has(`${c}|${r.reason}`); });
    return k === undefined ? [] : [{ ...r, cell: cellOf(r, s, k), column: s.columns[k] }];
  });
}

// Pure: the note's sentence: where, how sure, the reason as the list says it (its line about the changed cell's column, else
// its first: a typed 77777 broke its row's Total too, and "Total 103.48 does not add up" came first), and how many more
export function noteSaid(sheet, f, more, names = {}) {
  const lines = plainReason(f.reason, names).split("\n"), col = names[f.column] || f.column;
  const why = lines.find((l) => col && l.startsWith(`${col} `)) || lines[0];
  return `Sheet "${sheet}", cell ${f.cell}: ${SEV[f.severity]}. ${why}${/[.!?]$/.test(why) ? "" : "."}${more ? ` And ${n(more)} more in what you changed.` : ""}`;
}

// Pure: a quiet word that the changed cells were checked and nothing there looks wrong (John, AH-181: the user sees Arcas
// checked), each address once, at most 3 named
export function checkedSaid(sheet, addresses) {
  const at = [...new Set(addresses.filter(Boolean))], named = at.slice(0, 3).join(", ");
  return `Checked ${at.length > 3 ? `${named} and ${n(at.length - 3)} more` : named} on "${sheet}": nothing unusual.`;
}

const edits = new Map(); // tab id -> the addresses changed since its last check
const big = new Set(); // tabs said too big to check as you type, once each
let timer = 0, running = false, tries = 0, audio = null, target = null;

function heard(e) {
  if (!liveOn() || ignored(e, state.working)) return;
  dropTab(e.worksheetId); // its numbers changed: read again for the copied tabs
  edits.set(e.worksheetId, [...(edits.get(e.worksheetId) || []), e.address]);
  clearTimeout(timer);
  timer = setTimeout(checkAll, QUIET);
}

// One check at a time, one sheet after another; edits made during a check wait for the next one
async function checkAll() {
  if (running) return;
  if (state.working) return void (timer = setTimeout(checkAll, QUIET)); // a scan or an action of ours first
  running = true;
  try {
    const now = [...edits];
    edits.clear();
    for (const [id, cells] of now) await check(id, cells).catch((e) => console.warn("check as you work", e));
  } finally {
    running = false;
    if (edits.size) timer = setTimeout(checkAll, QUIET);
  }
}

// The same /scan a Find problems sends, quietly: no skeleton, no list, no highlight, no progress
async function check(id, cells) {
  const s = await readSheet(() => {}, Infinity, id, liveable);
  if (!s) return;
  if (s.big) {
    if (!big.has(s.sheet)) say([`Sheet "${s.sheet}" has more than ${n(LIVE_ROWS)} rows, too many to check as you type. Find problems still checks it.`], { sheet: s.sheet }, false);
    big.add(s.sheet);
    return;
  }
  big.delete(s.sheet);
  const { decided, request } = await scanRequest(s, false);
  const body = await post("/scan", request, 300);
  const found = newFindings(body.rows, s, decided, cells, state.found[s.sheet]);
  state.found[s.sheet] = findingKeys(body.rows, s);
  const pairs = await newPairs(s.sheet).catch(() => []);
  const lines = [found.length ? noteSaid(s.sheet, found[0], found.length - 1, s.names) : "", ...pairs.map(copiedSaid)].filter(Boolean);
  if (lines.length) say(lines, found.length ? { sheet: s.sheet, cell: found[0].cell } : { sheet: pairs[0].sheet });
  // nothing flagged at all in the changed cells: said in the notice, with no sound, never over a note still showing
  else if (!newFindings(body.rows, s, decided, cells).length && $("live-note").hidden) notice(checkedSaid(s.sheet, cells));
}

// The note stays until it is closed or a newer one takes its place
function say(lines, where, ring = true) {
  target = where;
  $("live-text").replaceChildren(...lines.map((t) => Object.assign(document.createElement("p"), { textContent: t })));
  show("live-note");
  if (ring) chime();
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
      await ctx.sync();
    });
  } catch {
    if (++tries < 12) setTimeout(listen, 5000);
  }
}

export function initLive() {
  $("live").checked = liveOn();
  $("live-sound").checked = soundOn();
  $("live").addEventListener("change", () => setOn(LIVE_KEY, $("live").checked));
  $("live-sound").addEventListener("change", () => setOn(SOUND_KEY, $("live-sound").checked));
  for (const type of ["pointerdown", "keydown"]) document.addEventListener(type, wake, { capture: true });
  $("live-show").addEventListener("click", () => { if (target) showCell(target.sheet, target.cell).catch(() => {}); });
  $("live-close").addEventListener("click", () => show("live-note", false));
  listen();
}
