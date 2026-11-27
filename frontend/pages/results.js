import { SEV } from "../constants/index.js";
import { state } from "../hooks/use-state.js";
import { $, show, only } from "../utils/dom.js";
import { esc, n } from "../utils/text.js";
import { cutNote } from "../utils/sheet.js";
import { place } from "../utils/layout.js";
import { act } from "../hooks/use-action.js";
import { rowItem } from "../components/row-item.js";
import { fairnessNote, fairnessTests, flaggedRows, kindLabel, kindsOf, legendOf, listed, listOrder, shownCount, summaryOf, SHOWN_MAX, MORE } from "../features/scan.js";
import { openFix } from "./fix.js";
import { countUp, stagger, turnDone } from "../components/motion.js";

// Results show up: the summary, the color legend and the rows to check.
export function renderResults(rows, s, fair) {
  const flagged = flaggedRows(rows);
  state.order = listOrder(rows, state.decided); // the list keeps this order while rows get fixed or dismissed
  // each flagged number its own .count, so it can count up (AH-149); the rows' total ("of 300 rows") is itself from the
  // first frame: counted up too, it read "0 of 0 rows look wrong." (AH-149 review). Nothing found ends on a check mark
  const parts = summaryOf(rows).split(/(\d(?:[\d,]*\d)?)/);
  $("summary").replaceChildren(...parts.map((t, k) => (k % 2 && !parts[k + 1].startsWith(" row") ? Object.assign(document.createElement("span"), { className: "count", textContent: t }) : t)));
  $("summary").classList.toggle("tick", !flagged.length);
  countUp($("summary"));
  $("legend").replaceChildren(...legendOf(rows).map(([k, count]) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="swatch sev-${esc(k)}"></span>${esc(SEV[k])}: ${esc(n(count))}`;
    return li;
  }));
  const note = fairnessNote(fair);
  show("fairness-note", !!note);
  $("fairness-note").textContent = note;
  const tests = note ? fairnessTests(fair) : [];
  show("fairness-more", tests.length > 0);
  $("fairness-list").replaceChildren(...tests.map((t) => Object.assign(document.createElement("li"), { textContent: t.text })));
  show("cut-note", !!s.cut);
  if (s.cut) $("cut-note").textContent = cutNote(s.cut);
  $("status").style.removeProperty("--done"); // AH-184: a new list's finish line starts from nothing
  state.kind = null; // AH-228: a new list shows every kind, from its first 50 rows
  state.more = 0;
  listRows(true);
}

// The rows to check, worst first, each tagged once it is fixed or dismissed (like Grammarly's list of cards).
// fresh: drawn for another kind or more rows, so no row turns Fixed in front of you (it was not decided just now)
export function listRows(arrive = false, fresh = false) {
  only("results");
  const { order, lastRows, decided } = state;
  // Fixed / Dismissed come back after a reload too: kept in the workbook (features/decisions.js)
  const status = (i) => (decided[i] === "fixed" ? (SEV[lastRows[i].severity] ? "Fix accepted" : "Fixed")
    : decided[i] === "dismissed" ? "Dismissed" : null);
  const done = order.filter(status).length;
  // a sheet with nothing to list shows its summary alone: no "Worst first" hint over an empty framed list, and no Remove
  // highlights with nothing highlighted (AH-111). The next scan that flags rows brings them back
  for (const id of ["list-title", "list-hint", "flagged-list", "clear-highlights", "highlight-hint"]) show(id, order.length > 0);
  $("list-title").textContent = done ? `Rows to check (${n(done)} of ${n(order.length)} done)` : "Rows to check";
  $("list-title").classList.toggle("tick", done > 0 && done === order.length); // every row done: a check mark, once
  // AH-228 P-21: one kind of check at a time, when the list holds 2+ kinds ("Totals 7", "Spelling 4"); All shows them all
  const kinds = kindsOf(order, lastRows);
  if (!kinds.some(([k]) => k === state.kind)) state.kind = null;
  filters(kinds);
  const rows = listed(order, lastRows, state.kind), shown = shownCount(rows.length, state.more || 0);
  const before = new Map([...$("flagged-list").children].map((li) => [li.dataset.i, li])); // the rows as last drawn
  $("flagged-list").replaceChildren(...rows.slice(0, shown).map((i) => rowItem({ ...lastRows[i], i }, place(state.lastScan, i).startRow, act((b) => openFix(i, true, b)), status(i))));
  if (arrive) stagger($("flagged-list").children); // a new list arrives row by row; a redraw (Back, a fix) does not
  // AH-184: a row decided since the list was last drawn turns to its done look in front of you. A loop, never an arrow: a
  // closure over `before` shares this call's context with the rows' click handlers, and each list held the last one (7a)
  else if (!fresh) for (const li of $("flagged-list").children) if (li.className === "done" && before.get(li.dataset.i)?.className.startsWith("sev-")) turnDone(li, before.get(li.dataset.i));
  if (rows.length > shown) { // AH-228 P-20: the rows past the first 50 are a press away, 20 at a time, never past SHOWN_MAX
    const li = document.createElement("li");
    li.className = "more-rows";
    li.textContent = `+ ${n(rows.length - shown)} more, all highlighted in the sheet.` + (shown < SHOWN_MAX ? "" : " Fix these first, then click Find problems again.");
    if (shown < SHOWN_MAX) {
      const b = Object.assign(document.createElement("button"), { className: "secondary", textContent: `Show the next ${Math.min(MORE, rows.length - shown)}` });
      b.addEventListener("click", () => {
        state.more = (state.more || 0) + 1;
        listRows(false, true);
        $("flagged-list").children[shown]?.querySelector("button")?.focus({ preventScroll: true }); // the first row it brought
      });
      li.append(b);
    }
    $("flagged-list").appendChild(li);
  }
}

// The kind filter's buttons over the list, the one shown pressed; none when the list holds one kind
function filters(kinds) {
  const box = $("kind-filter"), all = state.order.length;
  show("kind-filter", kinds.length > 0);
  box.replaceChildren(...(kinds.length ? [[null, all], ...kinds] : []).map(([k, count]) => {
    const b = Object.assign(document.createElement("button"), { className: "try", textContent: `${k ? kindLabel(k) : "All"} ${n(count)}` });
    b.setAttribute("aria-pressed", String(state.kind === k));
    b.addEventListener("click", () => {
      state.kind = k;
      state.more = 0;
      listRows(false, true);
      [...$("kind-filter").children].find((x) => x.getAttribute("aria-pressed") === "true")?.focus({ preventScroll: true });
    });
    return b;
  }));
}
