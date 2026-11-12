// Kleine Helfer für die Oberfläche: Elemente bauen, Icons, Zahlenformate, Dialoge, Meldungen.

export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "value" || k === "checked" || k === "disabled" || k === "selected") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  add(el, kids);
  return el;
}
function add(el, kids) {
  for (const k of kids) {
    if (k == null || k === false) continue;
    if (Array.isArray(k)) add(el, k);
    else el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
}
export const clear = (el, ...kids) => { el.replaceChildren(); add(el, kids); return el; };

const ICONS = {
  cockpit: '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4-6"/><circle cx="12" cy="18" r="1.3"/>',
  film: '<rect x="3.5" y="4.5" width="17" height="15" rx="3"/><path d="M8 4.5v15M16 4.5v15M3.5 9.5H8M3.5 14.5H8M16 9.5h4.5M16 14.5h4.5"/>',
  kanban: '<rect x="3.5" y="4" width="4.6" height="16" rx="1.6"/><rect x="9.7" y="4" width="4.6" height="10.5" rx="1.6"/><rect x="15.9" y="4" width="4.6" height="13" rx="1.6"/>',
  coins: '<ellipse cx="9.5" cy="7.5" rx="5.5" ry="2.6"/><path d="M4 7.5v4.2c0 1.4 2.5 2.6 5.5 2.6M4 11.7v4.2c0 1.4 2.5 2.6 5.5 2.6"/><ellipse cx="15" cy="13" rx="5" ry="2.4"/><path d="M10 13v4c0 1.3 2.2 2.4 5 2.4s5-1.1 5-2.4v-4"/>',
  target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>',
  sliders: '<path d="M4 7h9M18 7h2M4 17h3M12 17h8"/><circle cx="15.5" cy="7" r="2.3"/><circle cx="9.5" cy="17" r="2.3"/>',
  upload: '<path d="M12 15.5V4.5M7.5 9 12 4.5 16.5 9M5 19.5h14"/>',
  download: '<path d="M12 4.5v11M7.5 11l4.5 4.5 4.5-4.5M5 19.5h14"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  play: '<path d="M8 5.5v13l10.5-6.5z" fill="currentColor"/>',
  pause: '<path d="M8.5 5.5v13M15.5 5.5v13" stroke-width="3"/>',
  restart: '<path d="M4.5 12a7.5 7.5 0 1 0 2.4-5.5"/><path d="M4.5 4.5v4.2h4.2"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4.5 7h15M9.5 7V4.8h5V7M6.5 7l.8 12.2h9.4L17.5 7M10 11v5M14 11v5"/>',
  folder: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.3h7a2 2 0 0 1 2 2v7.7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="2.2"/><path d="M15.5 8.5V6.2a1.7 1.7 0 0 0-1.7-1.7H6.2a1.7 1.7 0 0 0-1.7 1.7v7.6a1.7 1.7 0 0 0 1.7 1.7h2.3"/>',
  refresh: '<path d="M19.5 12a7.5 7.5 0 0 1-13 5.1M4.5 12a7.5 7.5 0 0 1 13-5.1"/><path d="M17.5 3v4h-4M6.5 21v-4h4"/>',
  flame: '<path d="M12 3c.5 3.5 5 5.5 5 10.5a5 5 0 0 1-10 0c0-2 1-3.2 2-4.2.2 1.6 1 2.5 1.8 2.7C10 9 10.200 5.5 12 3z"/>',
  trophy: '<path d="M8 4.5h8v5a4 4 0 0 1-8 0zM8 6H5v1.5A3 3 0 0 0 8 10.500M16 6h3v1.5a3 3 0 0 1-3 3M12 13.500V17M8.500 19.5h7M10 17h4"/>',
  bolt: '<path d="M13 3 5.500 13.500H11L10 21l8-10.500h-5.500z"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.8"/>',
  euro: '<path d="M17.5 6.5a7 7 0 1 0 0 11"/><path d="M4 10.200h9M4 13.800h9"/>',
  scissors: '<circle cx="6" cy="6.500" r="2.800"/><circle cx="6" cy="17.500" r="2.800"/><path d="M8.300 8.300 20 19M8.300 15.700 20 5"/>',
  clock: '<circle cx="12" cy="12" r="8.500"/><path d="M12 7.500V12l3 2"/>',
  spark: '<path d="M12 3.500l1.700 5 5 1.700-5 1.700-1.700 5-1.700-5-5-1.700 5-1.700zM18.500 15.500l.800 2.200 2.200.800-2.200.800-.800 2.200-.800-2.200-2.200-.800 2.200-.800z"/>',
  alert: '<path d="M12 4 21 19.500H3Z"/><path d="M12 10v4.200M12 17v.100"/>',
  octagon: '<path d="M8.300 3.500h7.400l4.800 4.800v7.400l-4.800 4.800H8.300l-4.800-4.800V8.300Z"/><path d="M12 8v5M12 16.200v.100"/>',
  ok: '<circle cx="12" cy="12" r="8.500"/><path d="m8.200 12.300 2.600 2.600 5-5.400"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  back: '<path d="M15 6l-6 6 6 6"/>',
  pip: '<rect x="3.500" y="5" width="17" height="14" rx="2.500"/><rect x="12" y="11.500" width="6" height="5" rx="1" fill="currentColor"/>',
  minus: '<path d="M6 12h12"/>',
  external: '<path d="M14 5h5v5M19 5l-8 8M17 14v4a1.500 1.500 0 0 1-1.500 1.500h-9A1.500 1.500 0 0 1 5 18V8.500A1.500 1.500 0 0 1 6.500 7H10"/>',
  key: '<circle cx="8" cy="15" r="3.500"/><path d="M10.500 12.500 19 4M15.500 7.500l2.500 2.500M13 10l2 2"/>',
  mic: '<rect x="9" y="3.500" width="6" height="10" rx="3"/><path d="M5.500 11.500a6.500 6.500 0 0 0 13 0M12 18v2.500"/>',
  chart: '<path d="M4 4v16h16"/><path d="m7.500 14.500 3.500-4 3 2.500 4.500-6"/>',
  flag: '<path d="M5.500 21V4M5.500 4.500h11l-2 4 2 4h-11"/>',
  wand: '<path d="M5 19 16 8M14 6l4 4M18.500 3.500v2.500M17.200 4.800h2.600M6 5.500V8M4.700 6.700h2.600"/>',
  post: '<path d="M21 3.500 10.500 14M21 3.500l-6.500 17-4-6.500-6.500-4z"/>',
};
export function icon(name, cls = "") {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "ic " + cls); s.setAttribute("aria-hidden", "true");
  s.innerHTML = ICONS[name] || ICONS.ok;          // feste, eigene Zeichnungen – keine Nutzerdaten
  return s;
}

const nf0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const num = v => nf0.format(Math.round(v || 0));
export const eur = (v, exact) => (exact || Math.abs(v || 0) < 100 ? nf2.format(v || 0) : nf0.format(Math.round(v || 0))) + " €";
export const compact = v => v >= 1e6 ? nf2.format(v / 1e6).replace(/,?0+$/, "") + " Mio." : v >= 10000 ? nf0.format(Math.round(v / 1000)) + " Tsd." : num(v);
export function clock(sec, tenths) {
  sec = Math.max(0, sec || 0);
  const hh = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  const ss = tenths ? s.toFixed(1).padStart(4, "0") : String(Math.floor(s)).padStart(2, "0");
  return (hh ? hh + ":" + String(m).padStart(2, "0") : m) + ":" + ss;
}
export const dateDE = iso => iso ? new Date(iso.length === 10 ? iso + "T12:00" : iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) : "";
export const dayShort = iso => new Date(iso + "T12:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
export const todayISO = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };

export function toast(text, kind = "ok", ms = 3600) {
  let box = document.getElementById("toasts");
  if (!box) { box = h("div", { id: "toasts", role: "status", "aria-live": "polite" }); document.body.append(box); }
  const t = h("div", { class: "toast " + kind }, icon(kind === "err" ? "octagon" : "ok"), text);
  box.append(t);
  setTimeout(() => t.remove(), kind === "err" ? 6500 : ms);
}

// Dialog. content: Element | (close) => Element. Gibt eine Funktion zum Schließen zurück.
export function modal(title, lead, content, actions) {
  const close = () => { back.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = e => { if (e.key === "Escape") close(); };
  const box = h("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-label": title },
    h("h2", {}, title), lead ? h("div", { class: "lead" }, lead) : null,
    typeof content === "function" ? content(close) : content,
    h("div", { class: "actions" }, (actions || []).map(a => h("button", {
      class: "btn " + (a.class || ""), type: "button",
      onclick: async e => {
        const btn = e.currentTarget;            // nach einem „await“ ist e.currentTarget leer – deshalb vorher merken
        if (a.onclick) { btn.disabled = true; try { if (await a.onclick() === false) return; } finally { btn.disabled = false; } }
        close();
      },
    }, a.icon ? icon(a.icon) : null, a.label))));
  const back = h("div", { class: "modal-back", onmousedown: e => { if (e.target === back) close(); } }, box);
  document.body.append(back);
  document.addEventListener("keydown", onKey);
  (box.querySelector("input,select,textarea") || box.querySelector("button"))?.focus();
  return close;
}
export const confirmBox = (title, text, label, onYes, danger) =>
  modal(title, text, null, [{ label: "Abbrechen", class: "ghost" }, { label, class: danger ? "danger" : "primary", onclick: onYes }]);

export function field(label, input, hint) {
  return h("label", { class: "field" }, label, input, hint ? h("small", {}, hint) : null);
}
export function select(options, value, attrs = {}) {
  return h("select", attrs, options.map(o => h("option", { value: o.value, selected: String(o.value) === String(value ?? "") }, o.label)));
}
export function switchEl(checked, onchange, label) {
  return h("span", { class: "switch" }, h("input", { type: "checkbox", checked, onchange: e => onchange(e.target.checked), "aria-label": label }), h("i"));
}

// Ring-Anzeige (Tagesquest, Scores)
export function ring(value, max, size, stroke, cls, center) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, frac = max > 0 ? Math.min(1, value / max) : 0;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", size); svg.setAttribute("height", size);
  svg.innerHTML = `<circle class="trk" cx="${size / 2}" cy="${size / 2}" r="${r}" stroke-width="${stroke}"/>
    <circle class="val" cx="${size / 2}" cy="${size / 2}" r="${r}" stroke-width="${stroke}" stroke-dasharray="${c}" stroke-dashoffset="${c}"/>`;
  requestAnimationFrame(() => requestAnimationFrame(() => svg.querySelector(".val").setAttribute("stroke-dashoffset", c * (1 - frac))));
  return h("div", { class: "ring " + (cls || ""), style: { width: size + "px", height: size + "px" } }, svg, h("div", { class: "mid" }, h("div", {}, center)));
}
export function scoreBadge(score) {
  const cls = score >= 75 ? "hi" : score >= 50 ? "mid" : "lo";
  const r = 19, c = 2 * Math.PI * r;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", 46); svg.setAttribute("height", 46);
  svg.innerHTML = `<circle class="trk" cx="23" cy="23" r="${r}"/><circle class="val" cx="23" cy="23" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - score / 100)}"/>`;
  return h("div", { class: "score " + cls, title: "Viral-Score" }, svg, h("b", {}, score));
}

export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast("Kopiert"); }
  catch { toast("Kopieren nicht möglich – bitte Text markieren und Strg+C drücken", "err"); }
}

export const STATUS = { candidate: "Kandidat", editing: "In Bearbeitung", done: "Fertig", posted: "Gepostet", rejected: "Verworfen" };
export const STATUS_CHIP = { candidate: "", editing: "accent", done: "good", posted: "gold", rejected: "crit" };
export const PLATFORMS = ["TikTok", "YouTube Shorts", "Instagram Reels", "Andere"];
export const engineLabel = (e, models) => !e ? "" : e === "local" ? "Lokale Analyse (ohne KI)" :
  "KI: " + ((models || []).find(m => "claude:" + m.id === e)?.label.split(" – ")[0] || e.replace("claude:", ""));
