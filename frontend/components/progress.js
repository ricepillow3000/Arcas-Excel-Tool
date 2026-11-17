import { $, show } from "../utils/dom.js";

// AH-184: with doneOf's words comes the share of the list done, drawn as a gold line over the foot bar (styles
// #status::before). Any other words take it away; it keeps its width meanwhile, so the next decision grows it from there
export function notice(msg, done = null) {
  $("notice").textContent = msg || "";
  $("status").toggleAttribute("data-done", !!msg && done !== null);
  if (done !== null) $("status").style.setProperty("--done", done);
}

// Progress line under the button. pct = 0..1 for real progress, null while the engine works (no fake numbers).
export function busy(text, pct = null) {
  show("busy", !!text);
  $("busy-text").textContent = text || "";
  $("busy-secs").textContent = "";
  $("busy-bar").classList.toggle("unknown", pct === null);
  $("busy-bar").style.width = pct === null ? "" : `${Math.round(pct * 100)}%`;
}

// While the engine checks there is no fraction to show (AH-149): the seconds it has taken, counted beside the words, once
// a second. Hidden from screen readers: the status line would read every second out. It stops by itself once the line
// says something else (the next step, or nothing when the action ends, however it ends), or a newer count begins
let latest = 0;
export function counting() {
  const t0 = Date.now(), words = $("busy-text").textContent, me = ++latest;
  const tick = setInterval(() => {
    if (me !== latest || $("busy").hidden || $("busy-text").textContent !== words) return clearInterval(tick);
    $("busy-secs").textContent = ` ${Math.round((Date.now() - t0) / 1000)} s`;
  }, 1000);
}
