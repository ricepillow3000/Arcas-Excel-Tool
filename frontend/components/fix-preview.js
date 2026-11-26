import { SEV } from "../constants/index.js";
import { state } from "../hooks/use-state.js";
import { $, show } from "../utils/dom.js";
import { readCells } from "../services/excel.js";
import { shownAs } from "../utils/sheet.js";
import { place } from "../utils/layout.js";

// Preview a fix as cell: old -> new. Nothing is written until Apply.
export async function showFix(f, label, out) {
  const olds = await readCells(f.sheet, out.changes.map((c) => c.cell));
  if (state.fix !== f) return;
  if (state.undos[f.i]) return void ($("fix-status").textContent = "AI answered, but a fix is already applied. Click Undo, then Ask AI again.");
  f.changes = out.changes;
  f.label = label;
  f.said = shownAs(out.explanation, state.lastScan?.names); // "Units (column E)", never "Units.1"
  f.recheck = !out.changes.length; // AH-228 P-08: no fix to write: "I fixed it" reads the row again instead
  $("fix-label").textContent = label;
  $("fix-explanation").textContent = f.said;
  $("fix-changes").replaceChildren(...changeItems(out.changes, olds));
  show("fix-apply");
  $("fix-dismiss").textContent = out.changes.length ? "Dismiss" : "Looks right"; // no fix offered: the only question left
  setApplied(!!state.undos[f.i]);
}

// A row whose fix was accepted, opened again: what changed (old -> new) and Undo
export function showAccepted(f, u) {
  f.changes = u.changes;
  f.label = "Suggested fix"; // undone, the card offers this fix again (setApplied says it as accepted meanwhile)
  f.said = "";
  $("fix-changes").replaceChildren(...changeItems(u.changes, u.writes.map((w) => w.value)));
  show("fix-apply");
  setApplied(true);
}

// Pure (AH-228 P-09): a value's leading spaces, the rest, its trailing spaces: a fix that only takes off a space read
// "D46: Meals → Meals", no change in sight
export const spaceParts = (v) => { const t = String(v ?? ""), core = t.trim(); return core ? [t.slice(0, t.indexOf(core)), core, t.slice(t.indexOf(core) + core.length)] : ["", t, ""]; };
// Pure: where the spaces a fix takes off (or adds) were, in words, or "" when the fix changes more than spaces
export function spaceNote(old, nw) {
  const [a, core, b] = spaceParts(old), [c, core2, d] = spaceParts(nw);
  if (core !== core2 || (a === c && b === d)) return "";
  const start = a !== c, end = b !== d;
  return start && end ? "(spaces at both ends)" : start ? "(a space at the start)" : "(a space at the end)";
}

// One value, each space at its ends drawn as a dot a screen reader says as "space"
function valueEl(cls, v) {
  const span = Object.assign(document.createElement("span"), { className: cls }), [a, core, b] = spaceParts(v);
  const dots = (s) => [...s].map(() => {
    const dot = Object.assign(document.createElement("span"), { className: "space", textContent: "·" });
    dot.setAttribute("role", "img");
    dot.setAttribute("aria-label", "space");
    return dot;
  });
  span.replaceChildren(...dots(a), core, ...dots(b));
  return span;
}

// Built as nodes, every value as text: "D46: Meals· → Meals (a space at the end)"
const changeItems = (changes, olds) => changes.map((c, k) => {
  const li = document.createElement("li"), note = spaceNote(olds[k], c.new);
  li.append(Object.assign(document.createElement("b"), { textContent: c.cell }), ": ", valueEl("old", olds[k]), " → ", valueEl("new", c.new), note ? ` ${note}` : "");
  return li;
});

// An accepted fix must be undone before another one is accepted, so Undo always gets back to the original.
// The card's buttons: Accept / Dismiss before, Undo / Next row after.
export function setApplied(applied) {
  const f = state.fix;
  $("fix-apply").disabled = applied || state.working;
  $("fix-apply").textContent = applied ? "Accepted" : f?.recheck ? "I fixed it" : "Accept";
  show("fix-undo", applied);
  show("fix-dismiss", !applied);
  show("fix-next", applied);
  // AH-205: "Never check ..." only beside Dismiss, its line held either way (global.css #fix-mute)
  $("fix-mute").toggleAttribute("data-off", applied || !f?.stop);
  // AH-228 P-16: an accepted fix is said as one: the title and the words under the fix no longer say "probably wrong" or
  // "check it before you click Accept"; Undo brings back what the card said before
  if (!f || !state.lastScan) return;
  const r = state.lastRows?.[f.i];
  $("fix-title").textContent = `Row ${place(state.lastScan, f.i).startRow + f.i + 2}: ${applied ? "fixed" : SEV[r?.severity]?.toLowerCase() ?? "fixed"}`;
  if (f.label === undefined) return;
  $("fix-label").textContent = applied ? "Accepted fix" : f.label;
  $("fix-explanation").textContent = applied ? "Undo puts the old values back." : f.said;
}
