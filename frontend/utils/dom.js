import { VIEWS } from "../constants/index.js";
import { state } from "../hooks/use-state.js";

export const $ = (id) => document.getElementById(id);
export const show = (id, on = true) => ($(id).hidden = !on);
export const only = (id) => ((state.view = id), VIEWS.forEach((v) => show(v, v === id))); // switch page
// Buttons turned back on show their own colours at once (AH-149 review r2): they faded back from their off colours over
// the hover's .3 s, so Find problems read as still off once the results were in. The colours are taken with no
// transition (styles: [data-turning-on]); a hover or a press still eases as before
export function turnOn(buttons) {
  const root = document.documentElement;
  root.setAttribute("data-turning-on", "");
  buttons.forEach((b) => (b.disabled = false));
  void root.offsetWidth; // the style is worked out here, while transitions are off
  root.removeAttribute("data-turning-on");
}

// AH-170: a reason's text with each ISO date kept on one line ("2026-01-" / "26" was split at its hyphen at 320 px). The
// text is the same: only spans are added, each date set as text
export const dated = (text) => String(text).split(/(\d{4}-\d{2}-\d{2})/)
  .map((t, k) => (k % 2 ? Object.assign(document.createElement("span"), { className: "iso-date", textContent: t }) : t));
