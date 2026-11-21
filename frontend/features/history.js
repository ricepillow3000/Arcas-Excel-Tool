import { state } from "../hooks/use-state.js";
import { $, turnOn } from "../utils/dom.js";
import { plainError } from "../utils/errors.js";
import { readCells, writeCells } from "../services/excel.js";
import { forgetUndo, kept } from "./undo-store.js";
import { saveDecisions } from "./decisions.js";
import { forget } from "./memory.js";
import { undoFix } from "./fix.js";
import { listRows } from "../pages/results.js";

// AH-218 (John's master spec): every fix Accept wrote in this workbook, newest first, each with its own Undo, from the
// Undo records the workbook already keeps (features/undo-store.js, AH-118): nothing new is stored, and the list outlives
// a reload as they do. A card's Undo reached only the row it was open on, after a scan found that row again.

const cut = (v) => { const t = String(v ?? ""); return t.length > 40 ? `${t.slice(0, 39)}…` : t; };

// Pure: the kept records -> the list, newest first: {sheet, code, cells: [[cell, old, new as typed]]}
export const historyOf = (records) => [...records].reverse()
  .map((r) => ({ sheet: r.sheet, code: r.code, cells: r.cells.map(([cell, old, , nw]) => [cell, cut(old), cut(nw)]) }));

// Pure: its cells in words, for the Undo button's name and the foot bar ("C11 and D11 on Sales")
export const cellsSaid = (h) => {
  const at = h.cells.map((c) => c[0]);
  return `${at.length > 1 ? `${at.slice(0, -1).join(", ")} and ${at.at(-1)}` : at[0]} on ${h.sheet}`;
};

// One row of the list, as the card shows a change: "Sales  C11: -5 → 5". Built as text nodes: no value is read as HTML
function rowOf(h) {
  const li = document.createElement("li"), what = document.createElement("span");
  what.className = "what";
  what.append(Object.assign(document.createElement("span"), { className: "where", textContent: h.sheet }));
  for (const [cell, old, nw] of h.cells) {
    const line = document.createElement("span");
    line.append(Object.assign(document.createElement("b"), { textContent: cell }), ": ",
      Object.assign(document.createElement("span"), { className: "old", textContent: old }), " → ",
      Object.assign(document.createElement("span"), { className: "new", textContent: nw }));
    what.append(line);
  }
  const undo = Object.assign(document.createElement("button"), { className: "secondary", textContent: "Undo" });
  undo.setAttribute("aria-label", `Undo ${cellsSaid(h)}`);
  undo.addEventListener("click", () => run(() => undoChange(h, undo)));
  li.append(what, undo);
  return li;
}

export function drawHistory() {
  const list = historyOf(kept());
  $("history-list").replaceChildren(...list.map(rowOf));
  $("history-empty").hidden = list.length > 0;
  $("history-state").hidden = !list.length;
  say("");
}

// What an Undo here did is said in the fold's own line, held at its height (styles #history-state), under the list: in the
// foot bar's notice, which lies in the page's flow outside a card, it pushed the fold 57 px down under the pointer (AH-218)
const say = (t) => void ($("history-state").textContent = t);

// One action at a time, as act() keeps it (state.working), turning off only this list's buttons; act() itself is not used:
// it clears and holds the foot bar's notice, which moves the page
async function run(fn) {
  if (state.working) return;
  state.working = true;
  const off = [...$("history-list").querySelectorAll("button:not(:disabled)")];
  off.forEach((b) => (b.disabled = true));
  try {
    await fn();
  } finally {
    state.working = false;
    turnOn(off.filter((b) => b.isConnected));
  }
}

// Undo one record, the card's safe way: read first, write only where each fixed cell still holds exactly what the fix
// made of it, and say why not in words. A row a scan holds goes through the card's own Undo (its list, highlight and
// verdict follow); after a reload, before any scan, the record alone does
async function undoChange(h, button) {
  const r = kept().find((x) => x.sheet === h.sheet && x.code === h.code);
  if (!r) return drawHistory(), say("That change was undone already.");
  say("Putting the old values back…"); // AH-157: said in the frame of the press
  const at = Object.keys(state.undos).find((i) => state.undos[i].sheet === r.sheet && state.undos[i].code === r.code);
  let why;
  try {
    if (at !== undefined) why = await undoFix(state.fix?.i === +at ? state.fix : { i: +at }, false);
    else why = await undoRecord(r);
  } catch (e) {
    why = plainError(e, "Undo failed");
  }
  if (why) return say(why);
  if (at !== undefined && state.view === "results") listRows(); // the row's tag says what its cells hold again
  // the row keeps its place, its Undo turned to a word, so nothing under it moves (AH-149); the next look redraws it
  const done = Object.assign(document.createElement("button"), { className: "secondary", textContent: "Undone", disabled: true });
  button.replaceWith(done);
  say(`Undone. ${cellsSaid(h)} ${h.cells.length > 1 ? "are" : "is"} back to what ${h.cells.length > 1 ? "they were" : "it was"}.`);
}

async function undoRecord(r) {
  const cells = r.cells.map((c) => c[0]), now = await readCells(r.sheet, cells);
  const edited = cells.filter((c, k) => now[k] !== r.cells[k][4]);
  if (edited.length) return `${edited.join(", ")} changed after the fix, so Undo left ${edited.length > 1 ? "them" : "it"} alone.`;
  await writeCells(r.sheet, r.cells.map(([cell, value, format]) => ({ cell, value, format })));
  forgetUndo(r.sheet, r.code);
  saveDecisions(r.sheet, [[r.code, null], [r.before, r.was || null]]); // the Fixed goes; a Dismiss before it comes back
  for (const [, old, , nw] of r.cells) forget(null, old, nw); // Ask AI's memory of it too, as the card's Undo does
  return "";
}

export function initHistory() {
  $("history-box").addEventListener("toggle", () => { if ($("history-box").open) drawHistory(); });
}
