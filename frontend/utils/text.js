export const n = (x) => x.toLocaleString("en-US");

// Pure: text safe inside HTML and inside "attribute values" (column headers come from the sheet)
export const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// ---- Limits: plain "flag below / flag above" per number column ----
// Pure: a saved limit as an input value - a number or nothing (a tampered workbook can't put markup in the page)
export const asNumber = (v) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? "" : Number(v));


// Pure (AH-228 P-31): /health's version ("v0.1.123 (2026-11-03)" from the exe build, "dev 843936a (2026-11-25)" from a
// checkout, nothing from an engine before 2026-10-15) in plain words for the footer
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function versionSaid(v) {
  if (!v) return "An old version: update Arcas";
  const m = /\((\d{4})-(\d{2})-(\d{2})\)\s*$/.exec(v), day = m ? ` (${+m[3]} ${MONTHS[m[2] - 1]} ${m[1]})` : "";
  return /^dev\b/.test(v) ? `Test version${day}` : `Version ${String(v).replace(/^v/, "").replace(/\s*\(.*$/, "")}${day}`;
}
