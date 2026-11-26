// The site has no server, so its two forms send nothing: each builds a prefilled GitHub "new issue" link.
// The person reads it on GitHub and presses its button there (public, needs a GitHub account), or, with Email John
// instead (AH-135), sends the same words from their own email app (a mailto link).
// The support form (support.html) shows its link; the contact form (the home page, AH-133) opens it in a new tab and
// then thanks the visitor inside the form, keeping the page and what they typed (AH-227 W-14, John: "Email first, keep
// message": thanks.html emptied the form, and Email John had nothing left to send). Each link opens one of the repo's issue forms
// (.github/ISSUE_TEMPLATE/support_request.yml, contact.yml), which adds its label and the public warning itself, and
// fills its fields by their ids: a labels= parameter needs triage rights askers lack.
// Every page loads it once (AH-73): it wires the forms of the page it finds, and again each time transition.js swaps
// a page in ("ah:page"); the old form's listener leaves with the old page.
(() => {
  const NEW = "https://github.com/ricepillow3000/Arcas-Excel-Tool/issues/new?template=";
  // Measured 2026-10-20: GitHub answers 414 past 8,190 characters, and a signed-out person's login page keeps the way
  // back only while the link still fits once encoded again (7,600 plain characters, 4,600 of emoji); past that, all
  // they typed is lost. So the long field is cut, at a whole character, until the encoded link fits with room to spare.
  const FITS = 7000;
  // one builder for both forms: the short fields as typed, the long one last, cut to fit
  function prefilled(template, fields, [key, long]) {
    const q = encodeURIComponent;
    const link = (text) => NEW + template + fields.map(([k, v]) => `&${k}=${q(v)}`).join("") + `&${key}=${q(text)}`;
    const all = [...long];
    let keep = all.length, url = link(long);
    while (q(url).length > FITS && keep) { keep = Math.floor(keep * 0.9); url = link(all.slice(0, keep).join("")); }
    return { url, cut: keep !== all.length };
  }

  // AH-135: a visitor with no GitHub account (most people) writes from their own email app instead. Some mail apps drop
  // a mailto link past about 2,000 characters, so the link is cut the same way as GitHub's, to 1,800
  const EMAIL = "john4000.nguyen@gmail.com", MAIL_FITS = 1800;
  function mailto(subject, lines, long) {
    const q = (t) => encodeURIComponent(t.replace(/\r?\n/g, "\r\n")); // a mail body breaks lines as CRLF (RFC 6068)
    const link = (text) => `mailto:${EMAIL}?subject=${q(subject)}&body=${q([...lines, "", text].join("\n"))}`;
    const all = [...long];
    let keep = all.length, url = link(long);
    while (url.length > MAIL_FITS && keep) { keep = Math.floor(keep * 0.9); url = link(all.slice(0, keep).join("")); }
    return { url, cut: keep !== all.length };
  }

  const FORMS = [
    { form: "ticket", missing: "missing", result: "result", ready: "ready", cut: "cut", open: "open", thanks: "thanks",
      needed: [["summary", "write a short summary"], ["details", "say what happened"], ["clean", "tick the box that says it has no key or private data"]],
      link: (v) => prefilled("support_request.yml", [["title", "[Support]: " + v("summary")], ["category", v("topic")], ["version", v("version")]], ["details", v("details")]),
      email: "email", mailCut: "mail-cut",
      mail: (v) => mailto("[Support]: " + v("summary"), [`Topic: ${v("topic")}`, `Engine version: ${v("version")}`], v("details")) },
    { form: "note", missing: "c-missing", result: "c-result", ready: "c-ready", cut: "c-cut", open: "c-open", thanks: "c-thanks", opens: true,
      // AH-192: an issue's title is what GitHub's lists and search engines show, so it names the topic, never the person.
      // AH-197: the name is optional, the one field that names a person in public (legal review item 7)
      needed: [["c-message", "write a message"], ["c-public", "tick the box that says it will be public"]],
      link: (v) => prefilled("contact.yml", [["title", `[Contact]: ${v("c-topic")}`], ["name", v("c-name")], ["topic", v("c-topic")]], ["message", v("c-message")]),
      email: "c-email", mailCut: "c-mail-cut",
      mail: (v) => mailto(`[Contact]: ${v("c-topic")}`, [v("c-name") && `Name: ${v("c-name")}`, `Topic: ${v("c-topic")}`].filter(Boolean), v("c-message")) },
  ];

  function wire(root, F) {
    const form = root.querySelector("#" + F.form);
    if (!form) return;
    const $ = (id) => root.querySelector("#" + id);
    const missing = $(F.missing);
    const v = (id) => { const s = $(id).value.trim(); return s.toWellFormed ? s.toWellFormed() : s; }; // a lone surrogate would make encodeURIComponent throw
    const empty = (id) => ($(id).type === "checkbox" ? !$(id).checked : !v(id));
    // AH-114: on a phone with its keyboard open (390 x 420) the message sat under the button, off the screen, focus stayed
    // on the button and no field said it was the one missing. Each missing field now says so and is described by the
    // message, which moves to just under the first of them, and that field takes focus; a field lets go once it is filled
    const mark = (id, bad) => { const el = $(id);
      if (bad) { el.setAttribute("aria-invalid", "true"); el.setAttribute("aria-describedby", F.missing); }
      else { el.removeAttribute("aria-invalid"); el.removeAttribute("aria-describedby"); } };
    const recheck = () => {
      for (const [id] of F.needed) if ($(id).hasAttribute("aria-invalid") && !empty(id)) mark(id, false);
      if (!F.needed.some(([id]) => $(id).hasAttribute("aria-invalid"))) missing.hidden = true;
    };
    form.addEventListener("input", recheck);
    form.addEventListener("change", recheck);
    // AH-126: once the link to GitHub is followed, say what happens next (nothing reaches John until Submit is pressed on
    // GitHub), as a status a screen reader announces; preparing the question again takes it back
    const thanks = $(F.thanks);
    $(F.open).addEventListener("click", () => { thanks.hidden = false; });
    // the fields both ways need: each missing one marked, the message under the first, which takes focus -> all there?
    const complete = () => {
      const need = F.needed.filter(([id]) => empty(id));
      for (const [id] of F.needed) mark(id, need.some(([n]) => n === id));
      missing.hidden = !need.length;
      if (!need.length) return true;
      // AH-227 W-15: what to do, as a sentence ("Please add a message, the box that says..." read as a list of nouns)
      const say = need.map(([, w]) => w);
      missing.textContent = "Please " + (say.length > 1 ? say.slice(0, -1).join(", ") + " and " + say[say.length - 1] : say[0]) + ".";
      const first = $(need[0][0]);
      first.closest(".field, .confirm").after(missing);
      first.focus();
      missing.scrollIntoView({ block: "nearest" });
      return false;
    };
    // Email John instead: a mailto link the visitor's own email app opens, filled in here as the click goes through.
    // The page stays: no thank-you page, since nothing is sent until they press Send there
    $(F.email).addEventListener("click", (e) => {
      $(F.mailCut).hidden = true;
      $(F.result).hidden = true;
      thanks.hidden = true;
      if (!complete()) { e.preventDefault(); return; }
      const { url, cut } = F.mail(v);
      $(F.email).href = url;
      $(F.mailCut).hidden = !cut;
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      thanks.hidden = true;
      $(F.mailCut).hidden = true;
      $(F.result).hidden = true;
      if (!complete()) return;
      const { url, cut } = F.link(v);
      $(F.cut).hidden = !cut;
      // the link is described by what the box says above it, the cut note too when it shows (a hidden one would be read)
      $(F.open).setAttribute("aria-describedby", cut ? `${F.ready} ${F.cut}` : F.ready);
      $(F.open).href = url;
      // the contact form opens GitHub itself, in a new tab with no way back to this one, then says thanks where it is.
      // A cut message, or a browser that keeps the tab from opening, gets the link to press instead, as the support form
      if (F.opens && !cut) {
        const tab = window.open(url, "_blank");
        if (tab) { tab.opener = null; thanks.hidden = false; return; }
      }
      $(F.result).hidden = false;
      $(F.open).focus();
    });
  }

  const mount = (root) => { for (const F of FORMS) wire(root, F); };
  document.addEventListener("ah:page", (e) => mount((e.detail && e.detail.root) || document));
  mount(document);
})();
