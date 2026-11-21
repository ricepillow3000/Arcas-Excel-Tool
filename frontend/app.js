// Arcas task pane - entry point. Plain JS modules, no build. Talks to the local back end at the same origin.
// Workflow: Home -> Find problems (Agent 1 in the engine) -> highlight -> results (Agent 2) -> a row's card: Accept / Dismiss / Ask AI
// -> Agent 3 in the engine checks AI fixes before they show, and every accepted fix after it is written.
import { state } from "./hooks/use-state.js";
import { $, show, only } from "./utils/dom.js";
import { act, oneClickEach } from "./hooks/use-action.js";
import { getHealth } from "./services/api.js";
import { activeSheet, saveLimits } from "./services/excel.js";
import { powerBiOn, runScan, sayLastScan, setPowerBi } from "./features/scan.js";
import { clearHighlights } from "./features/highlight.js";
import { applyFix, undoFix } from "./features/fix.js";
import { setAi, askFix, checkWords, checkRules, readLayout } from "./features/ai.js";
import { openLimitsEditor, saveLimitsAndRescan } from "./pages/limits.js";
import { backToList, dismissFix, muteFix, nextFix } from "./pages/fix.js";
import { initStrength } from "./pages/strength.js";
import { autoOn, setAuto, autoUndo, undoAutoFix } from "./features/autofix.js";
import { notice } from "./components/progress.js";
import { n } from "./utils/text.js";
import { initSettings } from "./pages/settings.js";
import { initMotion } from "./components/motion.js";
import { plainError } from "./utils/errors.js";
import { sayProfile } from "./features/profile.js";
import { initLive } from "./features/live.js";

const CARD = "#fix-view"; // what a card does turns off only the card's buttons (AH-149)
// AH-170: focus goes to the button that took the pressed one's place (Accept's Undo, Undo's Accept): the pressed one was
// hidden or turned off, and focus fell to the page, so the keyboard had to start again at the top. Comments in this file
// avoid the words ZAP's baseline scan reads as suspicious (its rule 10027, CI's zap job)
const thenFocus = (fn, to) => async () => {
  await fn();
  const b = to();
  if (b && !b.hidden && !b.disabled) b.focus({ preventScroll: true });
};
const fixDone = () => state.fix && state.undos[state.fix.i];

// AH-193: the pane opens on its own header and start-up skeleton while Office gets ready; it said "Open this inside
// Excel." on bare paper to a person already in Excel, then moved 14 px when the main view came. Only outside Excel is it said
const away = () => { show("app-body", false); show("sideload-msg"); };
if (typeof Office === "undefined") away();
else {
  Office.onReady((info) => {
    if (info.host !== Office.HostType.Excel) return away();
    initMotion();
    oneClickEach();
    $("scan").onclick = act(() => runScan(true, true)); // held: the skeleton stays long enough to be seen
    $("retry-health").onclick = () => checkHealth();
    $("clear-highlights").onclick = act(clearHighlights);
    $("edit-limits").onclick = act(openLimitsEditor); // AH-170: like every action, it clears the last one's notice
    $("cancel-limits").onclick = () => only(state.lastScan ? "results" : "empty-state");
    $("save-limits").onclick = act(saveLimitsAndRescan);
    $("auto-limits").onclick = act(async () => (saveLimits(null), await runScan()));
    $("fix-back").onclick = () => { backToList().catch((e) => notice(plainError(e))); };
    $("fix-apply").onclick = thenFocus(act(() => state.fix && applyFix(state.fix, state.fix.changes, state.fix.sheet), CARD), () => fixDone() && $("fix-undo"));
    $("fix-undo").onclick = thenFocus(act(() => state.fix && undoFix(state.fix), CARD), () => state.fix && !fixDone() && $("fix-apply"));
    $("fix-dismiss").onclick = act(() => dismissFix(), CARD);
    $("fix-mute").onclick = act(muteFix, CARD); // AH-205
    $("fix-next").onclick = act(nextFix, CARD);
    $("fix-ask").onclick = askFix;
    // AH-149: a starter request fills the box and sends nothing; Ask AI sends it
    for (const b of document.querySelectorAll("#fix-tries .try")) b.addEventListener("click", () => { $("fix-intent").value = b.textContent; $("fix-intent").focus(); });
    $("odd-check").onclick = act(checkWords);
    $("rules-check").onclick = act(checkRules);
    $("layout-check").onclick = act(readLayout); // AH-215
    // only Ctrl+Enter (Cmd+Enter on a Mac) is ours; every other key types, Enter makes a new line. The old DOM0
    // `onkeydown = (e) => e.key === "Enter" && e.ctrlKey && askFix()` returned false for every other key, and a DOM0
    // handler returning false cancels the key: nothing could be typed in this box (2026-10-20)
    $("fix-intent").addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || !(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      askFix();
    });
    initSettings();
    initStrength(act(runScan));
    $("auto-fix").checked = autoOn(); // off unless turned on, on this PC
    $("auto-fix").onchange = () => setAuto($("auto-fix").checked);
    $("power-bi").checked = powerBiOn(); // off unless turned on: no copy of the sheet is kept
    $("power-bi").onchange = () => setPowerBi($("power-bi").checked);
    $("undo-auto").onclick = act(async () => {
      const [back, left] = await undoAutoFix();
      await runScan(false); // checked again, but never auto-fixed again right away
      notice(`Put back ${n(back)} auto-fixed cell${back === 1 ? "" : "s"}` + (left ? `; ${n(left)} that changed since (edited or sorted) ${left === 1 ? "was" : "were"} left alone.` : "."));
    });
    show("undo-auto", !!autoUndo());
    activeSheet().then((name) => { $("sheet-name").textContent = name; }).catch(() => {}); // Excel refuses while a cell is being typed in: the name stays blank until the first scan (AH-58)
    initLive(); // AH-181: check as you work
    only("empty-state");
    sayLastScan(); // AH-157: the workbook's last check, there the moment the pane shows
    checkHealth();
  });
}

// AH-157: while Arcas has stopped the pane asks again by itself every AGAIN ms for FOR ms, one request at a time, and opens
// when the engine answers (it waited for a press). Try again asks at once, the start-up skeleton standing in while it
// waits (global.css #skeleton): it showed nothing new for up to 10 s. Only the newest ask's answer counts
const AGAIN = 5000, FOR = 120000;
let asked = 0, again = 0, until = 0;
async function checkHealth(auto = false) {
  const me = ++asked, pressed = document.activeElement === $("retry-health"); // AH-170: hidden below, its focus is moved
  const moveTo = (id) => pressed && $(id).focus({ preventScroll: true });
  clearTimeout(again);
  if (!auto) {
    until = Date.now() + FOR;
    show("server-down", false);
  }
  try {
    const h = await getHealth();
    if (me !== asked) return;
    setAi(h.ai_available, h.ai_provider);
    // which engine answers: an old one gave 2 of 279 on a credit sheet and looked just like a new one (2026-10-15)
    $("engine-version").textContent = `Engine ${h.version || "from before 2026-10-15: update it"}`;
    // AH-169: what a scan will check, before it. The main view waits for its lines, a second at most, the start-up
    // skeleton standing in, so they land with it: shown first, a 300-row sheet's lines grew the box 33 px under the
    // options and the footer (CLS 0.0156, AH-193 fix round). Past the second it says "Reading your sheet…", held
    if (state.view === "empty-state" && !state.lastScan) await Promise.race([sayProfile(), new Promise((go) => setTimeout(go, 1000))]);
    if (me !== asked) return;
    show("main-ui");
    show("server-down", false);
    moveTo("scan");
  } catch {
    if (me !== asked) return;
    show("main-ui", false);
    show("server-down");
    moveTo("retry-health");
    if (Date.now() < until) again = setTimeout(() => checkHealth(true), AGAIN);
  }
}
